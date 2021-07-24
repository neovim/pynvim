"""Event loop abstraction subpackage.

Tries to use pyuv as a backend, falling back to the asyncio implementation.
"""

from pynvim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop as EventLoop


__all__ = ['EventLoop']
