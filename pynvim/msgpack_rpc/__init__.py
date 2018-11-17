"""Msgpack-rpc subpackage.

This package implements a msgpack-rpc client. While it was designed for
handling some Nvim particularities(server->client requests for example), the
code here should work with other msgpack-rpc servers.
"""
from .async_session import AsyncSession
from .event_loop import EventLoop
from .msgpack_stream import MsgpackStream
from .session import ErrorResponse, Session


__all__ = ('tcp_session', 'socket_session', 'stdio_session', 'child_session',
           'ErrorResponse')


def session(transport_type='stdio', *args, **kwargs):
    loop = EventLoop(transport_type, *args, **kwargs)
    msgpack_stream = MsgpackStream(loop)
    async_session = AsyncSession(msgpack_stream)
    session = Session(async_session)
    return session


def tcp_session(address, port=7450):
    """Create a msgpack-rpc session from a tcp address/port."""
    return session('tcp', address, port)


def socket_session(path):
    """Create a msgpack-rpc session from a unix domain socket."""
    return session('socket', path)


def stdio_session():
    """Create a msgpack-rpc session from stdin/stdout."""
    return session('stdio')


def child_session(argv):
    """Create a msgpack-rpc session from a new Nvim instance."""
    return session('child', argv)
