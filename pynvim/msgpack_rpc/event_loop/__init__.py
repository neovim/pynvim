"""Event loop abstraction subpackage.

Tries to use pyuv as a backend, falling back to the asyncio implementation.
"""

from pynvim.compat import IS_PYTHON3

# on python3 we only support asyncio, as we expose it to plugins
if IS_PYTHON3:
    from pynvim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
    EventLoop = AsyncioEventLoop
else:
    try:
        # libuv is fully implemented in C, use it when available
        from pynvim.msgpack_rpc.event_loop.uv import UvEventLoop
        EventLoop = UvEventLoop
    except ImportError:
        # asyncio(trollius on python 2) is pure python and should be more
        # portable across python implementations
        from pynvim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
        EventLoop = AsyncioEventLoop


__all__ = ('EventLoop')
