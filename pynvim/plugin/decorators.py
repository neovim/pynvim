"""Decorators used by python host plugin system."""

from __future__ import annotations

import inspect
import logging
import sys
from functools import partial
from typing import (TYPE_CHECKING, Any, Callable, Dict, Optional, Type,
                    TypeVar, Union, cast, overload)

if sys.version_info < (3, 8):
    from typing_extensions import Literal, Protocol, TypedDict
else:
    from typing import Literal, Protocol, TypedDict

if sys.version_info < (3, 10):
    from typing_extensions import ParamSpec
else:
    from typing import ParamSpec

from pynvim.api.common import TDecodeMode
from pynvim.compat import unicode_errors_default

logger = logging.getLogger(__name__)
debug, info, warn = (
    logger.debug,
    logger.info,
    logger.warning,
)
__all__ = ('plugin', 'rpc_export', 'command', 'autocmd', 'function',
           'encoding', 'decode', 'shutdown_hook')

T = TypeVar('T')

if TYPE_CHECKING:

    class RpcSpec(TypedDict):
        type: Literal['command', 'autocmd', 'function']
        name: str
        sync: Union[bool, Literal['urgent']]
        opts: Any
else:
    RpcSpec = dict

# type variables for Handler, to represent Callable: P -> R
P = ParamSpec('P')
R = TypeVar('R')


class Handler(Protocol[P, R]):
    """An interface to pynvim-decorated RPC handler.

    Handler is basically a callable (method) that is decorated by pynvim.
    It will have some private fields (prefixed with `_nvim_`), set by
    decorators that follow below. This generic type allows stronger, static
    typing for all the private attributes (see `host.Host` for the usage).

    Note: Any valid Handler that is created by pynvim's decorator is guaranteed
    to have *all* of the following `_nvim_*` attributes defined as per the
    "Protocol", so there is NO need to check `hasattr(handler, "_nvim_...")`.
    Exception is _nvim_decode; this is an optional attribute orthgonally set by
    the decorator `@decode()`.
    """
    __call__: Callable[P, R]

    _nvim_rpc_method_name: str
    _nvim_rpc_sync: bool
    _nvim_bind: bool
    _nvim_prefix_plugin_path: bool
    _nvim_rpc_spec: Optional[RpcSpec]
    _nvim_shutdown_hook: bool

    _nvim_registered_name: Optional[str]  # set later by host when discovered

    @classmethod
    def wrap(cls, fn: Callable[P, R]) -> Handler[P, R]:
        fn = cast(Handler[P, R], partial(fn))
        fn._nvim_bind = False
        fn._nvim_rpc_method_name = None  # type: ignore
        fn._nvim_rpc_sync = None  # type: ignore
        fn._nvim_prefix_plugin_path = False
        fn._nvim_rpc_spec = None
        fn._nvim_shutdown_hook = False
        fn._nvim_registered_name = None
        return fn


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
    predicate = lambda fn: getattr(fn, '_nvim_bind', False)
    for _, fn in inspect.getmembers(cls, predicate):
        fn._nvim_bind = False
    return cls


def rpc_export(
    rpc_method_name: str,
    sync: bool = False,
) -> Callable[[Callable[P, R]], Handler[P, R]]:
    """Export a function or plugin method as a msgpack-rpc request handler."""

    def dec(f: Callable[P, R]) -> Handler[P, R]:
        f = cast(Handler[P, R], f)
        f._nvim_rpc_method_name = rpc_method_name
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = False
        f._nvim_rpc_spec = None  # not used
        f._nvim_shutdown_hook = False  # not used
        f._nvim_registered_name = None  # TBD
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
) -> Callable[[Callable[P, R]], Handler[P, R]]:
    """Tag a function or plugin method as a Nvim command handler."""

    def dec(f: Callable[P, R]) -> Handler[P, R]:
        f = cast(Handler[P, R], f)
        f._nvim_rpc_method_name = ('command:{}'.format(name))
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

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

        f._nvim_rpc_spec = {
            'type': 'command',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        f._nvim_shutdown_hook = False
        f._nvim_registered_name = None  # TBD
        return f

    return dec


def autocmd(
    name: str,
    pattern: str = '*',
    sync: bool = False,
    allow_nested: bool = False,
    eval: Optional[str] = None
) -> Callable[[Callable[P, R]], Handler[P, R]]:
    """Tag a function or plugin method as a Nvim autocommand handler."""

    def dec(f: Callable[P, R]) -> Handler[P, R]:
        f = cast(Handler[P, R], f)
        f._nvim_rpc_method_name = ('autocmd:{}:{}'.format(name, pattern))
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

        opts = {'pattern': pattern}

        if eval:
            opts['eval'] = eval

        if not sync and allow_nested:
            rpc_sync: Union[bool, Literal['urgent']] = "urgent"
        else:
            rpc_sync = sync

        f._nvim_rpc_spec = {
            'type': 'autocmd',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        f._nvim_shutdown_hook = False
        f._nvim_registered_name = None  # TBD
        return f

    return dec


def function(
    name: str,
    range: Union[bool, str, int] = False,
    sync: bool = False,
    allow_nested: bool = False,
    eval: Optional[str] = None
) -> Callable[[Callable[P, R]], Handler[P, R]]:
    """Tag a function or plugin method as a Nvim function handler."""

    def dec(f: Callable[P, R]) -> Handler[P, R]:
        f = cast(Handler[P, R], f)
        f._nvim_rpc_method_name = ('function:{}'.format(name))
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

        opts = {}

        if range:
            opts['range'] = '' if range is True else str(range)

        if eval:
            opts['eval'] = eval

        if not sync and allow_nested:
            rpc_sync: Union[bool, Literal['urgent']] = "urgent"
        else:
            rpc_sync = sync

        f._nvim_rpc_spec = {
            'type': 'function',
            'name': name,
            'sync': rpc_sync,
            'opts': opts
        }
        f._nvim_shutdown_hook = False  # not used
        f._nvim_registered_name = None  # TBD
        return f

    return dec


def shutdown_hook(f: Callable[P, R]) -> Handler[P, R]:
    """Tag a function or method as a shutdown hook."""
    f = cast(Handler[P, R], f)
    f._nvim_rpc_method_name = ''  # Falsy value, not used
    f._nvim_rpc_sync = True  # not used
    f._nvim_prefix_plugin_path = False  # not used
    f._nvim_rpc_spec = None  # not used

    f._nvim_shutdown_hook = True
    f._nvim_bind = True
    f._nvim_registered_name = None  # TBD
    return f


T_Decode = Union[Type, Handler[P, R]]


def decode(
    mode: TDecodeMode = unicode_errors_default,
) -> Callable[[T_Decode], T_Decode]:
    """Configure automatic encoding/decoding of strings.

    This decorator can be put around an individual Handler (@rpc_export,
    @autocmd, @function, @command, or @shutdown_hook), or around a class
    (@plugin, has an effect on all the methods unless overridden).

    The argument `mode` will be passed as an argument to:
        bytes.decode("utf-8", errors=mode)
    when decoding bytestream Nvim RPC responses.

    See https://docs.python.org/3/library/codecs.html#error-handlers for
    the list of valid modes (error handler values).

    See also:
        pynvim.api.Nvim.with_decode(mode)
        pynvim.api.common.decode_if_bytes(..., mode)
    """

    @overload
    def dec(f: Handler[P, R]) -> Handler[P, R]:
        ...  # decorator on method

    @overload
    def dec(f: Type[T]) -> Type[T]:
        ...  # decorator on class

    def dec(f):  # type: ignore
        f._nvim_decode = mode
        return f

    return dec  # type: ignore


def encoding(encoding: Union[bool, str] = True):  # type: ignore
    """DEPRECATED: use pynvim.decode()."""
    if isinstance(encoding, str):
        encoding = True

    def dec(f):  # type: ignore
        f._nvim_decode = encoding if encoding else None
        return f

    return dec
