"""Decorators used by python host plugin system."""

import inspect
import logging
import sys
from typing import Any, Callable, Dict, Optional, TypeVar, Union

from pynvim.compat import unicode_errors_default

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)
__all__ = ('plugin', 'rpc_export', 'command', 'autocmd', 'function',
           'encoding', 'decode', 'shutdown_hook')

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


def plugin(cls: T) -> T:
    """Tag a class as a plugin.

    This decorator is required to make the class methods discoverable by the
    plugin_load method of the host.
    """
    cls._nvim_plugin = True  # type: ignore[attr-defined]
    # the _nvim_bind attribute is set to True by default, meaning that
    # decorated functions have a bound Nvim instance as first argument.
    # For methods in a plugin-decorated class this is not required, because
    # the class initializer will already receive the nvim object.
    predicate = lambda fn: hasattr(fn, '_nvim_bind')
    for _, fn in inspect.getmembers(cls, predicate):
        fn._nvim_bind = False
    return cls


def rpc_export(rpc_method_name: str, sync: bool = False) -> Callable[[F], F]:
    """Export a function or plugin method as a msgpack-rpc request handler."""
    def dec(f: F) -> F:
        f._nvim_rpc_method_name = rpc_method_name  # type: ignore[attr-defined]
        f._nvim_rpc_sync = sync  # type: ignore[attr-defined]
        f._nvim_bind = True  # type: ignore[attr-defined]
        f._nvim_prefix_plugin_path = False  # type: ignore[attr-defined]
        return f
    return dec


def command(
    name: str,
    nargs: Union[str, int] = 0,
    complete: Optional[str] = None,
    range: Optional[Union[str, int]] = None,
    count: Optional[int] = None,
    bang: bool = False,
    register: bool = False,
    sync: bool = False,
    allow_nested: bool = False,
    eval: Optional[str] = None
) -> Callable[[F], F]:
    """Tag a function or plugin method as a Nvim command handler."""
    def dec(f: F) -> F:
        f._nvim_rpc_method_name = (  # type: ignore[attr-defined]
            'command:{}'.format(name)
        )
        f._nvim_rpc_sync = sync  # type: ignore[attr-defined]
        f._nvim_bind = True  # type: ignore[attr-defined]
        f._nvim_prefix_plugin_path = True  # type: ignore[attr-defined]

        opts: Dict[str, Any] = {}

        if range is not None:
            opts['range'] = '' if range is True else str(range)
        elif count is not None:
            opts['count'] = count

        if bang:
            opts['bang'] = ''

        if register:
            opts['register'] = ''

        if nargs:
            opts['nargs'] = nargs

        if complete:
            opts['complete'] = complete

        if eval:
            opts['eval'] = eval

        if not sync and allow_nested:
            rpc_sync: Union[bool, Literal['urgent']] = "urgent"
        else:
            rpc_sync = sync

        f._nvim_rpc_spec = {  # type: ignore[attr-defined]
            'type': 'command',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        return f
    return dec


def autocmd(
    name: str,
    pattern: str = '*',
    sync: bool = False,
    allow_nested: bool = False,
    eval: Optional[str] = None
) -> Callable[[F], F]:
    """Tag a function or plugin method as a Nvim autocommand handler."""
    def dec(f: F) -> F:
        f._nvim_rpc_method_name = (  # type: ignore[attr-defined]
            'autocmd:{}:{}'.format(name, pattern)
        )
        f._nvim_rpc_sync = sync  # type: ignore[attr-defined]
        f._nvim_bind = True  # type: ignore[attr-defined]
        f._nvim_prefix_plugin_path = True  # type: ignore[attr-defined]

        opts = {
            'pattern': pattern
        }

        if eval:
            opts['eval'] = eval

        if not sync and allow_nested:
            rpc_sync: Union[bool, Literal['urgent']] = "urgent"
        else:
            rpc_sync = sync

        f._nvim_rpc_spec = {  # type: ignore[attr-defined]
            'type': 'autocmd',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        return f
    return dec


def function(
    name: str,
    range: Union[bool, str, int] = False,
    sync: bool = False,
    allow_nested: bool = False,
    eval: Optional[str] = None
) -> Callable[[F], F]:
    """Tag a function or plugin method as a Nvim function handler."""
    def dec(f: F) -> F:
        f._nvim_rpc_method_name = (  # type: ignore[attr-defined]
            'function:{}'.format(name)
        )
        f._nvim_rpc_sync = sync  # type: ignore[attr-defined]
        f._nvim_bind = True  # type: ignore[attr-defined]
        f._nvim_prefix_plugin_path = True  # type: ignore[attr-defined]

        opts = {}

        if range:
            opts['range'] = '' if range is True else str(range)

        if eval:
            opts['eval'] = eval

        if not sync and allow_nested:
            rpc_sync: Union[bool, Literal['urgent']] = "urgent"
        else:
            rpc_sync = sync

        f._nvim_rpc_spec = {  # type: ignore[attr-defined]
            'type': 'function',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        return f
    return dec


def shutdown_hook(f: F) -> F:
    """Tag a function or method as a shutdown hook."""
    f._nvim_shutdown_hook = True  # type: ignore[attr-defined]
    f._nvim_bind = True  # type: ignore[attr-defined]
    return f


def decode(mode: str = unicode_errors_default) -> Callable[[F], F]:
    """Configure automatic encoding/decoding of strings."""
    def dec(f: F) -> F:
        f._nvim_decode = mode  # type: ignore[attr-defined]
        return f
    return dec


def encoding(encoding: Union[bool, str] = True) -> Callable[[F], F]:
    """DEPRECATED: use pynvim.decode()."""
    if isinstance(encoding, str):
        encoding = True

    def dec(f: F) -> F:
        f._nvim_decode = encoding  # type: ignore[attr-defined]
        return f
    return dec
