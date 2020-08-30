"""Msgpack-rpc subpackage.

This package implements a msgpack-rpc client. While it was designed for
handling some Nvim particularities(server->client requests for example), the
code here should work with other msgpack-rpc servers.
"""
from pynvim.msgpack_rpc.async_session import AsyncSession
from pynvim.msgpack_rpc.event_loop import EventLoop
from pynvim.msgpack_rpc.msgpack_stream import MsgpackStream
from pynvim.msgpack_rpc.session import ErrorResponse, Session
from pynvim.util import get_client_info


__all__ = ('tcp_session', 'socket_session', 'stdio_session', 'child_session',
           'ErrorResponse')


def session(transport_type='stdio', *args, **kwargs):
    loop = EventLoop(transport_type, *args, **kwargs)
    msgpack_stream = MsgpackStream(loop)
    async_session = AsyncSession(msgpack_stream)
    session = Session(async_session)
    session.request(b'nvim_set_client_info',
                    *get_client_info('client', 'remote', {}), async_=True)
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
