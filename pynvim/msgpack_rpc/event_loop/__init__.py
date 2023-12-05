"""Event loop abstraction subpackage.

We use python's built-in asyncio as the backend.
"""

from pynvim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop as EventLoop
from pynvim.msgpack_rpc.event_loop.base import TTransportType


__all__ = ['EventLoop', 'TTransportType']
