"""Common code for event loop implementations."""
import logging
import signal
import sys
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)


# When signals are restored, the event loop library may reset SIGINT to SIG_DFL
# which exits the program. To be able to restore the python interpreter to it's
# default state, we keep a reference to the default handler
default_int_handler = signal.getsignal(signal.SIGINT)
main_thread = threading.current_thread()

TTransportType = Union[
    Literal['stdio'],
    Literal['socket'],
    Literal['tcp'],
    Literal['child']
]

# TODO: Since pynvim now supports python 3, the only available backend of the
# msgpack_rpc BaseEventLoop is the built-in asyncio (see #294). We will have
# to remove some unnecessary abstractions as well as greenlet. See also #489


class BaseEventLoop(ABC):
    """Abstract base class for all event loops.

    Event loops act as the bottom layer for Nvim sessions created by this
    library. They hide system/transport details behind a simple interface for
    reading/writing bytes to the connected Nvim instance.

    A lifecycle of event loop is as follows: (1. -> [2. -> 3.]* -> 4.)
      1. initialization (__init__): connection to Nvim is established.
      2. run(data_cb): run the event loop (blocks until the loop stops).
         Requests are sent to the remote neovim by calling send(), and
         responses (messages) from the remote neovim will be passed to the
         given `data_cb` callback function while the event loop is running.
         Note that run() may be called multiple times.
      3. stop(): stop the event loop.
      4. close(): close the event loop, destroying all the internal resources.

    This class exposes public methods for interacting with the underlying
    event loop and delegates implementation-specific work to the following
    methods, which subclasses are expected to implement:

    - `_init()`: Implementation-specific initialization
    - `_connect_tcp(address, port)`: connect to Nvim using tcp/ip
    - `_connect_socket(path)`: Same as tcp, but use a UNIX domain socket or
      named pipe.
    - `_connect_stdio()`: Use stdin/stdout as the connection to Nvim
    - `_connect_child(argv)`: Use the argument vector `argv` to spawn an
      embedded Nvim that has its stdin/stdout connected to the event loop.
    - `_start_reading()`: Called after any of _connect_* methods. Can be used
      to perform any post-connection setup or validation.
    - `_send(data)`: Send `data` (byte array) to Nvim (usually RPC request).
    - `_run()`: Runs the event loop until stopped or the connection is closed.
      The following methods can be called upon some events by the event loop:
      - `_on_data(data)`: When Nvim sends some data (usually RPC response).
      - `_on_signal(signum)`: When a signal is received.
      - `_on_error(exc)`: When a non-recoverable error occurs (e.g:
        connection lost, or any other OSError)
      Note that these _on_{data,signal,error} methods are not 'final', may be
      changed around an execution of run(). The subclasses are expected to
      handle any early messages arriving while _on_data is not yet set.
    - `_stop()`: Stop the event loop.
    - `_interrupt(data)`: Like `stop()`, but may be called from other threads
      this.
    - `_setup_signals(signals)`: Add implementation-specific listeners for
      for `signals`, which is a list of OS-specific signal numbers.
    - `_teardown_signals()`: Removes signal listeners set by `_setup_signals`
    """

    def __init__(self, transport_type: TTransportType, *args: Any, **kwargs: Any):
        """Initialize and connect the event loop instance.

        The only arguments are the transport type and transport-specific
        configuration, like this:

        >>> BaseEventLoop('tcp', '127.0.0.1', 7450)
        >>> BaseEventLoop('socket', '/tmp/nvim-socket')
        >>> BaseEventLoop('stdio')
        >>> BaseEventLoop('child', ['nvim', '--embed', '--headless', '-u', 'NONE'])

        Implementation-specific initialization should be made in the __init__
        constructor of the subclass, which must call the constructor of the
        super class (BaseEventLoop), in which one of the `_connect_*` methods
        (based on `transport_type`) and then `_start_reading()`.
        """
        self._transport_type = transport_type
        self._signames = dict((k, v) for v, k in signal.__dict__.items()
                              if v.startswith('SIG'))
        self._on_data: Optional[Callable[[bytes], None]] = None
        self._error: Optional[BaseException] = None
        try:
            getattr(self, '_connect_{}'.format(transport_type))(*args, **kwargs)
        except Exception as e:
            self.close()
            raise e
        self._start_reading()

    @abstractmethod
    def _start_reading(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _send(self, data: bytes) -> None:
        raise NotImplementedError()

    def connect_tcp(self, address: str, port: int) -> None:
        """Connect to tcp/ip `address`:`port`. Delegated to `_connect_tcp`."""
        info('Connecting to TCP address: %s:%d', address, port)
        self._connect_tcp(address, port)

    @abstractmethod
    def _connect_tcp(self, address: str, port: int) -> None:
        raise NotImplementedError()

    def connect_socket(self, path: str) -> None:
        """Connect to socket at `path`. Delegated to `_connect_socket`."""
        info('Connecting to %s', path)
        self._connect_socket(path)

    @abstractmethod
    def _connect_socket(self, path: str) -> None:
        raise NotImplementedError()

    def connect_stdio(self) -> None:
        """Connect using stdin/stdout. Delegated to `_connect_stdio`."""
        info('Preparing stdin/stdout for streaming data')
        self._connect_stdio()

    @abstractmethod
    def _connect_stdio(self) -> None:
        raise NotImplementedError()

    def connect_child(self, argv):
        """Connect a new Nvim instance. Delegated to `_connect_child`."""
        info('Spawning a new nvim instance')
        self._connect_child(argv)

    @abstractmethod
    def _connect_child(self, argv: List[str]) -> None:
        raise NotImplementedError()

    def send(self, data: bytes) -> None:
        """Queue `data` for sending to Nvim."""
        debug("Sending '%s'", data)
        self._send(data)

    def threadsafe_call(self, fn):
        """Call a function in the event loop thread.

        This is the only safe way to interact with a session from other
        threads.
        """
        self._threadsafe_call(fn)

    @abstractmethod
    def _threadsafe_call(self, fn: Callable[[], Any]) -> None:
        raise NotImplementedError()

    def run(self, data_cb: Callable[[bytes], None]) -> None:
        """Run the event loop, and receives response messages to a callback."""
        if self._error:
            err = self._error
            if isinstance(self._error, KeyboardInterrupt):
                # KeyboardInterrupt is not destructive (it may be used in
                # the REPL).
                # After throwing KeyboardInterrupt, cleanup the _error field
                # so the loop may be started again
                self._error = None
            raise err

        # data_cb: e.g., MsgpackStream._on_data
        self._on_data = data_cb
        if threading.current_thread() == main_thread:
            self._setup_signals([signal.SIGINT, signal.SIGTERM])
        debug('Entering event loop')
        self._run()
        debug('Exited event loop')
        if threading.current_thread() == main_thread:
            self._teardown_signals()
            signal.signal(signal.SIGINT, default_int_handler)
        self._on_data = None

        # eventloop was stopped due to an error, re-raise it
        # (e.g. connection lost when subprocess nvim dies)
        if self._error:
            # Note: traceback is not preserved and attached for some reason,
            # should be somewhere from msgpack_rpc.event_loop.asyncio.Protocol
            raise self._error

    @abstractmethod
    def _run(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        """Stop the event loop."""
        self._stop()
        debug('Stopped event loop')

    @abstractmethod
    def _stop(self) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        """Stop the event loop."""
        self._close()
        debug('Closed event loop')

    @abstractmethod
    def _close(self) -> None:
        raise NotImplementedError()

    def _on_signal(self, signum: signal.Signals) -> None:
        # pylint: disable-next=consider-using-f-string
        msg = 'Received signal {}'.format(self._signames[signum])
        debug(msg)

        if signum == signal.SIGINT and self._transport_type == 'stdio':
            # When the transport is stdio, we are probably running as a Nvim
            # child process. In that case, we don't want to be killed by
            # ctrl+C
            return

        if signum == signal.SIGINT:
            self._error = KeyboardInterrupt()
        else:
            self._error = Exception(msg)
        self.stop()

    def _on_error(self, exc: Exception) -> None:
        warn('on_error: %s', repr(exc))
        if self._error is None:
            # ignore subsequent exceptions, it's enough to raise only
            # the first exception arrived
            self._error = exc
        self.stop()

    def _on_interrupt(self) -> None:
        self.stop()

    def _setup_signals(self, signals: List[signal.Signals]) -> None:
        pass  # no-op by default

    def _teardown_signals(self) -> None:
        pass  # no-op by default
