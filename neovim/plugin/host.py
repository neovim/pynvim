"""Implements a Nvim host for python plugins."""
import functools
import imp
import inspect
import logging
import os
import os.path
import re

from traceback import format_exc

from . import script_host
from ..api import decode_if_bytes, walk
from ..compat import IS_PYTHON3, find_module
from ..msgpack_rpc import ErrorResponse

__all__ = ('Host')

logger = logging.getLogger(__name__)
error, debug, info, warn = (logger.error, logger.debug, logger.info,
                            logger.warning,)


class Host(object):

    """Nvim host for python plugins.

    Takes care of loading/unloading plugins and routing msgpack-rpc
    requests/notifications to the appropriate handlers.
    """

    def __init__(self, nvim):
        """Set handlers for plugin_load/plugin_unload."""
        self.nvim = nvim
        self._specs = {}
        self._loaded = {}
        self._load_errors = {}
        self._notification_handlers = {}
        self._request_handlers = {
            'poll': lambda: 'ok',
            'specs': self._on_specs_request,
            'shutdown': self.shutdown
        }

        # Decode per default for Python3
        self._decode_default = IS_PYTHON3

    def _on_async_err(self, msg):
        self.nvim.err_write(msg, async=True)

    def start(self, plugins):
        """Start listening for msgpack-rpc requests and notifications."""
        self.nvim.run_loop(self._on_request,
                           self._on_notification,
                           lambda: self._load(plugins),
                           err_cb=self._on_async_err)

    def shutdown(self):
        """Shutdown the host."""
        self._unload()
        self.nvim.stop_loop()

    def _on_request(self, name, args):
        """Handle a msgpack-rpc request."""
        if IS_PYTHON3:
            name = decode_if_bytes(name)
        handler = self._request_handlers.get(name, None)
        if not handler:
            msg = self._missing_handler_error(name, 'request')
            error(msg)
            raise ErrorResponse(msg)

        debug('calling request handler for "%s", args: "%s"', name, args)
        rv = handler(*args)
        debug("request handler for '%s %s' returns: %s", name, args, rv)
        return rv

    def _on_notification(self, name, args):
        """Handle a msgpack-rpc notification."""
        if IS_PYTHON3:
            name = decode_if_bytes(name)
        handler = self._notification_handlers.get(name, None)
        if not handler:
            msg = self._missing_handler_error(name, 'notification')
            error(msg)
            self._on_async_err(msg + "\n")
            return

        debug('calling notification handler for "%s", args: "%s"', name, args)
        try:
            handler(*args)
        except Exception as err:
            msg = ("error caught in async handler '{} {}':\n{!r}\n{}\n"
                   .format(name, args, err, format_exc(5)))
            self._on_async_err(msg + "\n")
            raise

    def _missing_handler_error(self, name, kind):
        msg = 'no {} handler registered for "{}"'.format(kind, name)
        pathmatch = re.match(r'(.+):[^:]+:[^:]+', name)
        if pathmatch:
            loader_error = self._load_errors.get(pathmatch.group(1))
            if loader_error is not None:
                msg = msg + "\n" + loader_error
        return msg

    def _load(self, plugins):
        for path in plugins:
            err = None
            if path in self._loaded:
                error('{0} is already loaded'.format(path))
                continue
            try:
                if path == "script_host.py":
                    module = script_host
                else:
                    directory, name = os.path.split(os.path.splitext(path)[0])
                    file, pathname, descr = find_module(name, [directory])
                    module = imp.load_module(name, file, pathname, descr)
                handlers = []
                self._discover_classes(module, handlers, path)
                self._discover_functions(module, handlers, path)
                if not handlers:
                    error('{0} exports no handlers'.format(path))
                    continue
                self._loaded[path] = {'handlers': handlers, 'module': module}
            except Exception as e:
                err = ('Encountered {} loading plugin at {}: {}\n{}'
                       .format(type(e).__name__, path, e, format_exc(5)))
                error(err)
                self._load_errors[path] = err

    def _unload(self):
        for path, plugin in self._loaded.items():
            handlers = plugin['handlers']
            for handler in handlers:
                method_name = handler._nvim_rpc_method_name
                if hasattr(handler, '_nvim_shutdown_hook'):
                    handler()
                elif handler._nvim_rpc_sync:
                    del self._request_handlers[method_name]
                else:
                    del self._notification_handlers[method_name]
        self._specs = {}
        self._loaded = {}

    def _discover_classes(self, module, handlers, plugin_path):
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if getattr(cls, '_nvim_plugin', False):
                # create an instance of the plugin and pass the nvim object
                plugin = cls(self._configure_nvim_for(cls))
                # discover handlers in the plugin instance
                self._discover_functions(plugin, handlers, plugin_path)

    def _discover_functions(self, obj, handlers, plugin_path):
        def predicate(o):
            return hasattr(o, '_nvim_rpc_method_name')

        def decoder(fn, decode, *args):
            return fn(*walk(decode_if_bytes, args, decode))
        specs = []
        objdecode = getattr(obj, '_nvim_decode', self._decode_default)
        for _, fn in inspect.getmembers(obj, predicate):
            decode = getattr(fn, '_nvim_decode', objdecode)
            if fn._nvim_bind:
                # bind a nvim instance to the handler
                fn2 = functools.partial(fn, self._configure_nvim_for(fn))
                # copy _nvim_* attributes from the original function
                self._copy_attributes(fn, fn2)
                fn = fn2
            if decode:
                fn2 = functools.partial(decoder, fn, decode)
                self._copy_attributes(fn, fn2)
                fn = fn2

            # register in the rpc handler dict
            method = fn._nvim_rpc_method_name
            if fn._nvim_prefix_plugin_path:
                method = '{0}:{1}'.format(plugin_path, method)
            if fn._nvim_rpc_sync:
                if method in self._request_handlers:
                    raise Exception(('Request handler for "{0}" is ' +
                                    'already registered').format(method))
                self._request_handlers[method] = fn
            else:
                if method in self._notification_handlers:
                    raise Exception(('Notification handler for "{0}" is ' +
                                    'already registered').format(method))
                self._notification_handlers[method] = fn
            if hasattr(fn, '_nvim_rpc_spec'):
                specs.append(fn._nvim_rpc_spec)
            handlers.append(fn)
        if specs:
            self._specs[plugin_path] = specs

    def _copy_attributes(self, fn, fn2):
        # Copy _nvim_* attributes from the original function
        for attr in dir(fn):
            if attr.startswith('_nvim_'):
                setattr(fn2, attr, getattr(fn, attr))

    def _on_specs_request(self, path):
        if IS_PYTHON3:
            path = decode_if_bytes(path)
        if path in self._load_errors:
            self.nvim.out_write(self._load_errors[path] + '\n')
        return self._specs.get(path, 0)

    def _configure_nvim_for(self, obj):
        # Configure a nvim instance for obj (checks encoding configuration)
        nvim = self.nvim
        decode = getattr(obj, '_nvim_decode', self._decode_default)
        if decode:
            nvim = nvim.with_decode(decode)
        return nvim
