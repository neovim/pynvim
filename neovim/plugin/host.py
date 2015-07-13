"""Implements a Nvim host for python plugins."""
import functools
import imp
import inspect
import logging
import os
import os.path

from ..api import DecodeHook
from ..compat import IS_PYTHON3, find_module


__all__ = ('Host')

logger = logging.getLogger(__name__)
error, debug, info, warn = (logger.error, logger.debug, logger.info,
                            logger.warn,)


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
        self._notification_handlers = {}
        self._request_handlers = {
            'poll': lambda: 'ok',
            'specs': self._on_specs_request,
            'shutdown': self.shutdown
        }
        self._nvim_encoding = nvim.options['encoding']
        if IS_PYTHON3 and isinstance(self._nvim_encoding, bytes):
            self._nvim_encoding = self._nvim_encoding.decode('ascii')

    def start(self, plugins):
        """Start listening for msgpack-rpc requests and notifications."""
        self.nvim.session.run(self._on_request,
                              self._on_notification,
                              lambda: self._load(plugins))

    def shutdown(self):
        """Shutdown the host."""
        self._unload()
        self.nvim.session.stop()

    def _on_request(self, name, args):
        """Handle a msgpack-rpc request."""
        if IS_PYTHON3 and isinstance(name, bytes):
            name = name.decode(self._nvim_encoding)
        handler = self._request_handlers.get(name, None)
        if not handler:
            msg = 'no request handler registered for "%s"' % name
            warn(msg)
            raise Exception(msg)

        debug('calling request handler for "%s", args: "%s"', name, args)
        rv = handler(*args)
        debug("request handler for '%s %s' returns: %s", name, args, rv)
        return rv

    def _on_notification(self, name, args):
        """Handle a msgpack-rpc notification."""
        if IS_PYTHON3 and isinstance(name, bytes):
            name = name.decode(self._nvim_encoding)
        handler = self._notification_handlers.get(name, None)
        if not handler:
            warn('no notification handler registered for "%s"', name)
            return

        debug('calling notification handler for "%s", args: "%s"', name, args)
        handler(*args)

    def _load(self, plugins):
        for path in plugins:
            if path in self._loaded:
                error('{0} is already loaded'.format(path))
                continue
            directory, name = os.path.split(os.path.splitext(path)[0])
            file, pathname, description = find_module(name, [directory])
            handlers = []
            try:
                module = imp.load_module(name, file, pathname, description)
                self._discover_classes(module, handlers, path)
                self._discover_functions(module, handlers, path)
                if not handlers:
                    error('{0} exports no handlers'.format(path))
                    continue
                self._loaded[path] = {'handlers': handlers, 'module': module}
            except (ImportError, SyntaxError) as e:
                error(('Encountered import error loading '
                       'plugin at {0}: {1}').format(path, e))
            except Exception as e:
                error('Error loading plugin at {0} {1}: {2}'.format(
                    path, type(e).__name__, e))

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
        specs = []
        objenc = getattr(obj, '_nvim_encoding', None)
        for _, fn in inspect.getmembers(obj, predicate):
            enc = getattr(fn, '_nvim_encoding', objenc)
            if fn._nvim_bind:
                # bind a nvim instance to the handler
                fn2 = functools.partial(fn, self._configure_nvim_for(fn))
                # copy _nvim_* attributes from the original function
                self._copy_attributes(fn, fn2)
                fn = fn2
            decodehook = self._decodehook_for(enc)
            if decodehook is not None:
                decoder = lambda fn, hook, *args: fn(*hook.walk(args))
                fn2 = functools.partial(decoder, fn, decodehook)
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
        if IS_PYTHON3 and isinstance(path, bytes):
            path = path.decode(self._nvim_encoding)
        return self._specs.get(path, [])

    def _decodehook_for(self, encoding):
        if IS_PYTHON3 and encoding is None:
            encoding = True
        if encoding is True:
            encoding = self._nvim_encoding
        if encoding:
            return DecodeHook(encoding)

    def _configure_nvim_for(self, obj):
        # Configure a nvim instance for obj (checks encoding configuration)
        nvim = self.nvim
        encoding = getattr(obj, '_nvim_encoding', None)
        hook = self._decodehook_for(encoding)
        if hook is not None:
            nvim = nvim.with_hook(hook)
        return nvim
