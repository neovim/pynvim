"""Event loop implementation that uses the `asyncio` standard module.

The `asyncio` module was added to python standard library on 3.4, and it
provides a pure python implementation of an event loop library. It is used
as a fallback in case pyuv is not available(on python implementations other
than CPython).

"""
from __future__ import absolute_import

import asyncio
import logging
import os
import sys
from collections import deque
from signal import Signals
from typing import Any, Callable, Deque, List, Optional

from pynvim.msgpack_rpc.event_loop.base import BaseEventLoop

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)

loop_cls = asyncio.SelectorEventLoop
if os.name == 'nt':
    from asyncio.windows_utils import PipeHandle  # type: ignore[attr-defined]
    import msvcrt

    # On windows use ProactorEventLoop which support pipes and is backed by the
    # more powerful IOCP facility
    # NOTE: we override in the stdio case, because it doesn't work.
    loop_cls = asyncio.ProactorEventLoop  # type: ignore[attr-defined,misc]


class AsyncioEventLoop(BaseEventLoop, asyncio.Protocol,
                       asyncio.SubprocessProtocol):
    """`BaseEventLoop` subclass that uses `asyncio` as a backend."""

    _queued_data: Deque[bytes]
    if os.name != 'nt':
        _child_watcher: Optional['asyncio.AbstractChildWatcher']

    def connection_made(self, transport):
        """Used to signal `asyncio.Protocol` of a successful connection."""
        self._transport = transport
        self._raw_transport = transport
        if isinstance(transport, asyncio.SubprocessTransport):
            self._transport = transport.get_pipe_transport(0)

    def connection_lost(self, exc):
        """Used to signal `asyncio.Protocol` of a lost connection."""
        self._on_error(exc.args[0] if exc else 'EOF')

    def data_received(self, data: bytes) -> None:
        """Used to signal `asyncio.Protocol` of incoming data."""
        if self._on_data:
            self._on_data(data)
            return
        self._queued_data.append(data)

    def pipe_connection_lost(self, fd, exc):
        """Used to signal `asyncio.SubprocessProtocol` of a lost connection."""
        self._on_error(exc.args[0] if exc else 'EOF')

    def pipe_data_received(self, fd, data):
        """Used to signal `asyncio.SubprocessProtocol` of incoming data."""
        if fd == 2:  # stderr fd number
            self._on_stderr(data)
        elif self._on_data:
            self._on_data(data)
        else:
            self._queued_data.append(data)

    def process_exited(self) -> None:
        """Used to signal `asyncio.SubprocessProtocol` when the child exits."""
        self._on_error('EOF')

    def _init(self) -> None:
        self._loop = loop_cls()
        self._queued_data = deque()
        self._fact = lambda: self
        self._raw_transport = None
        self._child_watcher = None

    def _connect_tcp(self, address: str, port: int) -> None:
        coroutine = self._loop.create_connection(self._fact, address, port)
        self._loop.run_until_complete(coroutine)

    def _connect_socket(self, path: str) -> None:
        if os.name == 'nt':
            coroutine = self._loop.create_pipe_connection(  # type: ignore[attr-defined]
                self._fact, path
            )
        else:
            coroutine = self._loop.create_unix_connection(self._fact, path)
        self._loop.run_until_complete(coroutine)

    def _connect_stdio(self) -> None:
        if os.name == 'nt':
            pipe: Any = PipeHandle(
                msvcrt.get_osfhandle(sys.stdin.fileno())  # type: ignore[attr-defined]
            )
        else:
            pipe = sys.stdin
        coroutine = self._loop.connect_read_pipe(self._fact, pipe)
        self._loop.run_until_complete(coroutine)
        debug("native stdin connection successful")

        # Make sure subprocesses don't clobber stdout,
        # send the output to stderr instead.
        rename_stdout = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

        if os.name == 'nt':
            pipe = PipeHandle(
                msvcrt.get_osfhandle(rename_stdout)  # type: ignore[attr-defined]
            )
        else:
            pipe = os.fdopen(rename_stdout, 'wb')
        coroutine = self._loop.connect_write_pipe(self._fact, pipe)  # type: ignore[assignment]
        self._loop.run_until_complete(coroutine)
        debug("native stdout connection successful")

    def _connect_child(self, argv: List[str]) -> None:
        if os.name != 'nt':
            self._child_watcher = asyncio.get_child_watcher()
            self._child_watcher.attach_loop(self._loop)
        coroutine = self._loop.subprocess_exec(self._fact, *argv)
        self._loop.run_until_complete(coroutine)

    def _start_reading(self) -> None:
        pass

    def _send(self, data: bytes) -> None:
        self._transport.write(data)

    def _run(self) -> None:
        while self._queued_data:
            data = self._queued_data.popleft()
            if self._on_data is not None:
                self._on_data(data)
        self._loop.run_forever()

    def _stop(self) -> None:
        self._loop.stop()

    def _close(self) -> None:
        if self._raw_transport is not None:
            self._raw_transport.close()
        self._loop.close()
        if self._child_watcher is not None:
            self._child_watcher.close()
            self._child_watcher = None

    def _threadsafe_call(self, fn: Callable[[], Any]) -> None:
        self._loop.call_soon_threadsafe(fn)

    def _setup_signals(self, signals: List[Signals]) -> None:
        if os.name == 'nt':
            # add_signal_handler is not supported in win32
            self._signals = []
            return

        self._signals = list(signals)
        for signum in self._signals:
            self._loop.add_signal_handler(signum, self._on_signal, signum)

    def _teardown_signals(self) -> None:
        for signum in self._signals:
            self._loop.remove_signal_handler(signum)
