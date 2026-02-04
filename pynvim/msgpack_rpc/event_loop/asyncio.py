"""Event loop implementation that uses the `asyncio` standard module."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import deque
from signal import Signals
from typing import Any, Callable, Deque, List, Optional, cast

if sys.version_info >= (3, 12):
    from typing import Final, override
else:
    from typing_extensions import Final, override

from pynvim.msgpack_rpc.event_loop.base import BaseEventLoop, TTransportType

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)

loop_cls = asyncio.SelectorEventLoop

if os.name == 'nt':
    import msvcrt  # pylint: disable=import-error
    from asyncio.windows_utils import PipeHandle  # type: ignore[attr-defined]

    # On windows use ProactorEventLoop which support pipes and is backed by the
    # more powerful IOCP facility
    # NOTE: we override in the stdio case, because it doesn't work.
    loop_cls = asyncio.ProactorEventLoop  # type: ignore[attr-defined,misc]


# pylint: disable=logging-fstring-interpolation

class Protocol(asyncio.Protocol, asyncio.SubprocessProtocol):
    """The protocol class used for asyncio-based RPC communication."""

    def __init__(self, on_data, on_error):
        """Initialize the Protocol object."""
        assert on_data is not None
        assert on_error is not None
        self._on_data = on_data
        self._on_error = on_error

    @override
    def connection_made(self, transport):
        """Used to signal `asyncio.Protocol` of a successful connection."""
        self._transport = transport

    @override
    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Used to signal `asyncio.Protocol` of a lost connection."""
        warn(f"connection_lost: exc = {exc}")

        self._on_error(exc if exc else EOFError("connection_lost"))

    @override
    def data_received(self, data: bytes) -> None:
        """Used to signal `asyncio.Protocol` of incoming data."""
        self._on_data(data)

    @override
    def pipe_connection_lost(self, fd: int, exc: Optional[Exception]) -> None:
        """Used to signal `asyncio.SubprocessProtocol` of a lost connection."""

        assert isinstance(self._transport, asyncio.SubprocessTransport)
        debug_info = {'fd': fd, 'exc': exc, 'pid': self._transport.get_pid()}
        warn(f"pipe_connection_lost {debug_info}")

        if os.name == 'nt' and fd == 2:  # stderr
            # On windows, ignore piped stderr being closed immediately (#505)
            return

        # pipe_connection_lost() *may* be called before process_exited() is
        # called, when a Nvim subprocess crashes (SIGABRT). Do not handle
        # errors here, as errors will be handled somewhere else
        # self._on_error(exc if exc else EOFError("pipe_connection_lost"))

    @override
    def pipe_data_received(self, fd, data):
        """Used to signal `asyncio.SubprocessProtocol` of incoming data."""
        if fd == 2:  # stderr fd number
            # Ignore stderr message, log only for debugging
            debug("stderr: %s", str(data))
        elif fd == 1:  # stdout
            self.data_received(data)

    @override
    def process_exited(self) -> None:
        """Used to signal `asyncio.SubprocessProtocol` when the child exits."""
        assert isinstance(self._transport, asyncio.SubprocessTransport)
        pid = self._transport.get_pid()
        return_code = self._transport.get_returncode()

        warn("process_exited, pid = %s, return_code = %s", pid, return_code)
        err = EOFError(f"process_exited: pid = {pid}, return_code = {return_code}")
        self._on_error(err)


class AsyncioEventLoop(BaseEventLoop):
    """`BaseEventLoop` subclass that uses core `asyncio` as a backend."""

    _protocol: Optional[Protocol]
    _transport: Optional[asyncio.WriteTransport]
    _signals: List[Signals]
    _data_buffer: Deque[bytes]
    if os.name != 'nt':
        _child_watcher: Optional[asyncio.AbstractChildWatcher]

    def __init__(self,
                 transport_type: TTransportType,
                 *args: Any, **kwargs: Any):
        """asyncio-specific initialization. see BaseEventLoop.__init__."""

        if sys.version_info >= (3, 12):
            self._loop: Final[asyncio.AbstractEventLoop] = asyncio.new_event_loop()
        else:
            self._loop: Final[asyncio.AbstractEventLoop] = loop_cls()

        # Handle messages from nvim that may arrive before run() starts.
        self._data_buffer = deque()

        def _on_data(data: bytes) -> None:
            if self._on_data is None:
                self._data_buffer.append(data)
                return
            self._on_data(data)

        # pylint: disable-next=unnecessary-lambda
        self._protocol_factory = lambda: Protocol(
            on_data=_on_data,
            on_error=self._on_error,
        )
        self._protocol = None

        # The communication channel (endpoint) created by _connect_*() methods,
        # where we write request messages to be sent to neovim
        self._transport = None
        self._to_close: List[asyncio.BaseTransport] = []
        self._child_watcher = None

        super().__init__(transport_type, *args, **kwargs)

    @override
    def _connect_tcp(self, address: str, port: int) -> None:
        async def connect_tcp():
            transport, protocol = await self._loop.create_connection(
                self._protocol_factory, address, port)
            debug(f"tcp connection successful: {address}:{port}")
            self._transport = transport
            self._protocol = protocol

        self._loop.run_until_complete(connect_tcp())

    @override
    def _connect_socket(self, path: str) -> None:
        async def connect_socket():
            if os.name == 'nt':
                _create_connection = self._loop.create_pipe_connection
            else:
                _create_connection = self._loop.create_unix_connection

            transport, protocol = await _create_connection(
                self._protocol_factory, path)
            debug("socket connection successful: %s", self._transport)
            self._transport = transport
            self._protocol = protocol

        self._loop.run_until_complete(connect_socket())

    @override
    def _connect_stdio(self) -> None:
        async def connect_stdin():
            if os.name == 'nt':
                pipe = PipeHandle(msvcrt.get_osfhandle(sys.stdin.fileno()))
            else:
                pipe = sys.stdin
            transport, protocol = await self._loop.connect_read_pipe(
                self._protocol_factory, pipe)
            debug("native stdin connection successful")
            self._to_close.append(transport)
            del protocol
        self._loop.run_until_complete(connect_stdin())

        # Make sure subprocesses don't clobber stdout,
        # send the output to stderr instead.
        rename_stdout = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

        async def connect_stdout():
            if os.name == 'nt':
                pipe = PipeHandle(msvcrt.get_osfhandle(rename_stdout))
            else:
                pipe = os.fdopen(rename_stdout, 'wb')

            transport, protocol = await self._loop.connect_write_pipe(
                self._protocol_factory, pipe)
            debug("native stdout connection successful")
            self._transport = transport
            self._protocol = protocol
        self._loop.run_until_complete(connect_stdout())

    @override
    def _connect_child(self, argv: List[str]) -> None:
        def get_child_watcher():
            try:
                return asyncio.get_child_watcher()
            except AttributeError:  # Python 3.14
                return None

            return None

        if os.name != 'nt' and sys.version_info < (3, 12):
            # see #238, #241
            watcher = get_child_watcher()
            if watcher is not None:
                watcher.attach_loop(self._loop)
                self._child_watcher = watcher

        async def create_subprocess():
            transport: asyncio.SubprocessTransport  # type: ignore
            transport, protocol = await self._loop.subprocess_exec(
                self._protocol_factory, *argv)
            pid = transport.get_pid()
            debug("child subprocess_exec successful, PID = %s", pid)

            self._transport = cast(asyncio.WriteTransport,
                                   transport.get_pipe_transport(0))  # stdin
            self._protocol = protocol

            # proactor transport implementations do not close the pipes
            # automatically, so make sure they are closed upon shutdown
            def _close_later(transport):
                if transport is not None:
                    self._to_close.append(transport)

            _close_later(transport.get_pipe_transport(1))
            _close_later(transport.get_pipe_transport(2))
            _close_later(transport)

        # await until child process have been launched and the transport has
        # been established
        self._loop.run_until_complete(create_subprocess())

    @override
    def _start_reading(self) -> None:
        pass

    @override
    def _send(self, data: bytes) -> None:
        assert self._transport, "connection has not been established."
        self._transport.write(data)

    @override
    def _run(self) -> None:
        # process the early messages that arrived as soon as the transport
        # channels are open and on_data is fully ready to receive messages.
        while self._data_buffer:
            data: bytes = self._data_buffer.popleft()
            if self._on_data is not None:
                self._on_data(data)

        self._loop.run_forever()

    @override
    def _stop(self) -> None:
        self._loop.stop()

    @override
    def _close(self) -> None:
        def _close_transport(transport):
            transport.close()

            # Windows: for ProactorBasePipeTransport, close() doesn't take in
            # effect immediately (closing happens asynchronously inside the
            # event loop), need to wait a bit for completing graceful shutdown.
            if (sys.version_info < (3, 13) and
                    os.name == 'nt' and hasattr(transport, '_sock')):
                async def wait_until_closed():
                    # pylint: disable-next=protected-access
                    while transport._sock is not None:
                        await asyncio.sleep(0.01)
                self._loop.run_until_complete(wait_until_closed())

        if self._transport:
            _close_transport(self._transport)
            self._transport = None
        for transport in self._to_close:
            _close_transport(transport)
        self._to_close[:] = []

        self._loop.close()

        if self._child_watcher is not None:
            self._child_watcher.close()
            self._child_watcher = None

    @override
    def _threadsafe_call(self, fn: Callable[[], Any]) -> None:
        self._loop.call_soon_threadsafe(fn)

    @override
    def _setup_signals(self, signals: List[Signals]) -> None:
        if os.name == 'nt':
            # add_signal_handler is not supported in win32
            self._signals = []
            return

        self._signals = list(signals)
        for signum in self._signals:
            self._loop.add_signal_handler(signum, self._on_signal, signum)

    @override
    def _teardown_signals(self) -> None:
        for signum in self._signals:
            self._loop.remove_signal_handler(signum)
