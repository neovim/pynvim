"""Implements a Nvim host for python plugins."""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import os.path
import re
import sys
from functools import partial
from traceback import format_exc
from types import ModuleType
from typing import (Any, Callable, Dict, List, Optional, Sequence, Type,
                    TypeVar, Union, cast)

from pynvim.api import Nvim, decode_if_bytes, walk
from pynvim.api.common import TDecodeMode
from pynvim.msgpack_rpc import ErrorResponse
from pynvim.plugin import decorators, script_host
from pynvim.util import format_exc_skip, get_client_info

__all__ = ('Host',)

logger = logging.getLogger(__name__)
error, debug, info, warn = (logger.error, logger.debug, logger.info,
                            logger.warning,)

host_method_spec = {"poll": {}, "specs": {"nargs": 1}, "shutdown": {}}


T = TypeVar('T')

RpcSpec = decorators.RpcSpec
Handler = decorators.Handler


def _handle_import(path: str, name: str) -> ModuleType:
    """Import python module `name` from a known file path or module directory.

    The path should be the base directory from which the module can be imported.
    To support python 3.12, the use of `imp` should be avoided.
    @see https://docs.python.org/3.12/whatsnew/3.12.html#imp
    """
    if not name:
        raise ValueError("Missing module name.")

    sys.path.append(path)
    return importlib.import_module(name)


class Host:
    """Nvim host for python plugins.

    Takes care of loading/unloading plugins and routing msgpack-rpc
    requests/notifications to the appropriate handlers.
    """
    _specs: Dict[str, list[RpcSpec]]  # path -> list[ rpc handler spec ]
    _loaded: Dict[str, dict]  # path -> {handlers: ..., modules: ...}
    _load_errors: Dict[str, str]  # path -> error message

    def __init__(self, nvim: Nvim):
        """Set handlers for plugin_load/plugin_unload."""
        self.nvim = nvim
        self._specs = {}
        self._loaded = {}
        self._load_errors = {}
        self._notification_handlers: Dict[str, Handler] = {
            'nvim_error_event': Handler.wrap(self._on_error_event),
        }
        self._request_handlers: Dict[str, Handler] = {
            'poll': Handler.wrap(lambda: 'ok'),
            'specs': Handler.wrap(self._on_specs_request),
            'shutdown': Handler.wrap(self.shutdown),
        }

        self._decode_default = True

    def _on_async_err(self, msg: str) -> None:
        # uncaught python exception
        self.nvim.err_write(msg, async_=True)

    def _on_error_event(self, kind: Any, msg: str) -> None:
        # error from nvim due to async request
        # like nvim.command(..., async_=True)
        errmsg = "{}: Async request caused an error:\n{}\n".format(
            self.name, decode_if_bytes(msg))
        self.nvim.err_write(errmsg, async_=True)

    def start(self, plugins: Sequence[str]) -> None:
        """Start listening for msgpack-rpc requests and notifications."""
        self.nvim.run_loop(self._on_request,
                           self._on_notification,
                           lambda: self._load(plugins),
                           err_cb=self._on_async_err)

    def shutdown(self) -> None:
        """Shutdown the host."""
        self._unload()
        self.nvim.stop_loop()

    def _wrap_delayed_function(
        self,
        cls: Type[T],  # a class type
        delayed_handlers: List[Handler],
        name: str,
        sync: bool,
        module_handlers: List[Handler],
        path: str,
        *args: Any,
    ) -> Any:
        # delete the delayed handlers to be sure
        for handler in delayed_handlers:
            method_name = handler._nvim_registered_name
            assert method_name is not None
            if handler._nvim_rpc_sync:
                del self._request_handlers[method_name]
            else:
                del self._notification_handlers[method_name]
        # create an instance of the plugin and pass the nvim object
        plugin: T = cls(self._configure_nvim_for(cls))  # type: ignore[call-arg]

        # discover handlers in the plugin instance
        self._discover_functions(plugin, module_handlers,
                                 plugin_path=path, delay=False)

        if sync:
            return self._request_handlers[name](*args)
        else:
            return self._notification_handlers[name](*args)

    def _wrap_function(
        self,
        fn: Callable,
        sync: bool,
        decode: TDecodeMode,
        nvim_bind: Optional[Nvim],
        name: str,
        *args: Any,
    ) -> Any:
        if decode:
            args = walk(decode_if_bytes, args, decode)
        if nvim_bind is not None:
            args = (nvim_bind, *args)
        try:
            return fn(*args)
        except Exception:
            if sync:
                msg = ("error caught in request handler '{} {}':\n{}"
                       .format(name, args, format_exc_skip(1)))
                raise ErrorResponse(msg)
            else:
                msg = ("error caught in async handler '{} {}'\n{}\n"
                       .format(name, args, format_exc_skip(1)))
                self._on_async_err(msg + "\n")

    def _on_request(self, name: str, args: Sequence[Any]) -> Any:
        """Handle a msgpack-rpc request."""
        name = decode_if_bytes(name)
        handler = self._request_handlers.get(name, None)
        if not handler:
            msg = self._missing_handler_error(name, kind='request')
            error(msg)
            raise ErrorResponse(msg)

        debug('calling request handler for "%s", args: "%s"', name, args)
        rv = handler(*args)
        debug("request handler for '%s %s' returns: %s", name, args, rv)
        return rv

    def _on_notification(self, name: str, args: Sequence[Any]) -> None:
        """Handle a msgpack-rpc notification."""
        name = decode_if_bytes(name)
        handler = self._notification_handlers.get(name, None)
        if not handler:
            msg = self._missing_handler_error(name, kind='notification')
            error(msg)
            self._on_async_err(msg + "\n")
            return

        debug('calling notification handler for "%s", args: "%s"', name, args)
        handler(*args)

    def _missing_handler_error(self, name: str, *, kind: str) -> str:
        msg = 'no {} handler registered for "{}"'.format(kind, name)
        pathmatch = re.match(r'(.+):[^:]+:[^:]+', name)
        if pathmatch:
            loader_error = self._load_errors.get(pathmatch.group(1))
            if loader_error is not None:
                msg = msg + "\n" + loader_error
        return msg

    def _load(self, plugins: Sequence[str]) -> None:
        """Load the remote plugins and register handlers defined in the plugins.

        Parameters
        ----------
        plugins: List of plugin paths to rplugin python modules registered by
            `remote#host#RegisterPlugin('python3', ...)`. Each element should
            be either:
            (1) "script_host.py": this is a special plugin for python3
                rplugin host. See $VIMRUNTIME/autoload/provider/python3.vim
                ; or
            (2) (absolute) path to the top-level plugin module directory;
                e.g., for a top-level python module `mymodule`: it would be
                `"/path/to/plugin/rplugin/python3/mymodule"`.
                See the generated ~/.local/share/nvim/rplugin.vim manifest
                for real examples.
        """
        # self.nvim.err_write("host init _load\n", async_=True)
        has_script = False
        for path in plugins:
            path = os.path.normpath(path)  # normalize path
            try:
                plugin_spec = self._load_plugin(path=path)
                if not plugin_spec:
                    continue
                if plugin_spec["path"] == "script_host.py":
                    has_script = True
            except Exception as e:
                errmsg: str = (
                    'Encountered {} loading plugin at {}: {}\n{}'.format(
                        type(e).__name__, path, e, format_exc(5)))
                error(errmsg)
                self._load_errors[path] = errmsg

        kind = ("script-host" if len(plugins) == 1 and has_script
                else "rplugin-host")
        info = get_client_info(kind, 'host', host_method_spec)
        self.name = info[0]
        self.nvim.api.set_client_info(*info, async_=True)

    def _load_plugin(
        self, path: str, *,
        module: Optional[ModuleType] = None,
    ) -> Union[Dict[str, Any], None]:
        # Note: path must be normalized.
        if path in self._loaded:
            warn('{} is already loaded'.format(path))
            return None

        if path == "script_host.py":
            module = script_host
        elif module is not None:
            pass  # Note: module is provided only when testing
        else:
            directory, module_name = os.path.split(os.path.splitext(path)[0])
            module = _handle_import(directory, module_name)
        handlers: List[Handler] = []
        self._discover_classes(module, handlers, path)
        self._discover_functions(module, handlers, path, delay=False)
        if not handlers:
            error('{} exports no handlers'.format(path))
            return None

        self._loaded[path] = {
            'handlers': handlers,
            'module': module,
            'path': path,
        }
        return self._loaded[path]

    def _unload(self) -> None:
        for path, plugin in self._loaded.items():
            handlers = plugin['handlers']
            for handler in handlers:
                method_name = handler._nvim_registered_name
                if handler._nvim_shutdown_hook:
                    handler()
                elif handler._nvim_rpc_sync:
                    del self._request_handlers[method_name]
                else:
                    del self._notification_handlers[method_name]
        self._specs = {}
        self._loaded = {}

    def _discover_classes(
        self,
        module: ModuleType,
        handlers: List[Handler],
        plugin_path: str,
    ) -> None:
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if getattr(cls, '_nvim_plugin', False):
                # discover handlers in the plugin instance
                self._discover_functions(cls, handlers, plugin_path, delay=True)

    def _discover_functions(
        self,
        obj: Union[Type, ModuleType, Any],  # class, module, or plugin instance
        handlers: List[Handler],
        plugin_path: str,
        delay: bool,
    ) -> None:
        def predicate(o: Any) -> bool:
            return bool(getattr(o, '_nvim_rpc_method_name', False))

        cls_handlers: List[Handler] = []
        specs: List[decorators.RpcSpec] = []
        obj_decode: TDecodeMode = cast(
            TDecodeMode, getattr(obj, '_nvim_decode', self._decode_default))
        for _, fn in inspect.getmembers(obj, predicate):
            fn = cast(Handler, fn)  # because hasattr(_nvim_rpc_method_name)
            method: str = fn._nvim_rpc_method_name
            if fn._nvim_prefix_plugin_path:
                method = '{}:{}'.format(plugin_path, method)
            sync: bool = fn._nvim_rpc_sync
            if delay:
                # TODO: Fix typing on obj. delay=True assumes obj is a class!
                assert isinstance(obj, type), "obj must be a class type"
                _fn_wrapped = partial(self._wrap_delayed_function, obj,
                                      cls_handlers, method, sync,
                                      handlers, plugin_path)
            else:
                decode: TDecodeMode = getattr(fn, '_nvim_decode', obj_decode)
                nvim_bind: Optional[Nvim] = None
                if fn._nvim_bind:
                    nvim_bind = self._configure_nvim_for(fn)

                _fn_wrapped = partial(self._wrap_function, fn,
                                      sync, decode, nvim_bind, method)
            self._copy_attributes(fn, _fn_wrapped)
            fn_wrapped: Handler = cast(Handler, _fn_wrapped)
            fn_wrapped._nvim_registered_name = method

            # register in the rpc handler dict
            if sync:
                if method in self._request_handlers:
                    raise Exception(f'Request handler for "{method}" '
                                    'is already registered')
                self._request_handlers[method] = fn_wrapped
            else:
                if method in self._notification_handlers:
                    raise Exception(f'Notification handler for "{method}" '
                                    'is already registered')
                self._notification_handlers[method] = fn_wrapped
            if fn._nvim_rpc_spec:
                specs.append(fn._nvim_rpc_spec)
            handlers.append(fn_wrapped)
            cls_handlers.append(fn_wrapped)
        if specs:
            self._specs[plugin_path] = specs

    def _copy_attributes(self, src: Any, dst: Any) -> None:
        # Copy _nvim_* attributes from the original function
        for attr in dir(src):
            if attr.startswith('_nvim_'):
                setattr(dst, attr, getattr(src, attr))

    def _on_specs_request(self, path: Union[str, bytes]
                          ) -> List[RpcSpec]:
        path = decode_if_bytes(path)
        assert isinstance(path, str)
        if path in self._load_errors:
            self.nvim.out_write(self._load_errors[path] + '\n')
        return self._specs.get(path, [])

    def _configure_nvim_for(self, obj: Any) -> Nvim:
        # Configure a nvim instance for obj (checks encoding configuration)
        nvim = self.nvim
        decode: TDecodeMode = cast(
            TDecodeMode, getattr(obj, '_nvim_decode', self._decode_default))
        if decode:
            nvim = nvim.with_decode(decode)
        return nvim
