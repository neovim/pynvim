"""Common code for event loop implementations."""
import logging
import signal
import threading


logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)


# When signals are restored, the event loop library may reset SIGINT to SIG_DFL
# which exits the program. To be able to restore the python interpreter to it's
# default state, we keep a reference to the default handler
default_int_handler = signal.getsignal(signal.SIGINT)
main_thread = threading.current_thread()


class BaseEventLoop(object):

    """Abstract base class for all event loops.

    Event loops act as the bottom layer for Nvim sessions created by this
    library. They hide system/transport details behind a simple interface for
    reading/writing bytes to the connected Nvim instance.

    This class exposes public methods for interacting with the underlying
    event loop and delegates implementation-specific work to the following
    methods, which subclasses are expected to implement:

    - `_init()`: Implementation-specific initialization
    - `_connect_tcp(address, port)`: connect to Nvim using tcp/ip
    - `_connect_socket(path)`: Same as tcp, but use a UNIX domain socket or
      or named pipe.
    - `_connect_stdio()`: Use stdin/stdout as the connection to Nvim
    - `_connect_child(argv)`: Use the argument vector `argv` to spawn an
      embedded Nvim that has it's stdin/stdout connected to the event loop.
    - `_start_reading()`: Called after any of _connect_* methods. Can be used
      to perform any post-connection setup or validation.
    - `_send(data)`: Send `data`(byte array) to Nvim. The data is only
    - `_run()`: Runs the event loop until stopped or the connection is closed.
      calling the following methods when some event happens:
      actually sent when the event loop is running.
      - `_on_data(data)`: When Nvim sends some data.
      - `_on_signal(signum)`: When a signal is received.
      - `_on_error(message)`: When a non-recoverable error occurs(eg:
        connection lost)
    - `_stop()`: Stop the event loop
    - `_interrupt(data)`: Like `stop()`, but may be called from other threads
      this.
    - `_setup_signals(signals)`: Add implementation-specific listeners for
      for `signals`, which is a list of OS-specific signal numbers.
    - `_teardown_signals()`: Removes signal listeners set by `_setup_signals`
    """

    def __init__(self, transport_type, *args):
        """Initialize and connect the event loop instance.

        The only arguments are the transport type and transport-specific
        configuration, like this:

        >>> BaseEventLoop('tcp', '127.0.0.1', 7450)
        Traceback (most recent call last):
            ...
        AttributeError: 'BaseEventLoop' object has no attribute '_init'
        >>> BaseEventLoop('socket', '/tmp/nvim-socket')
        Traceback (most recent call last):
            ...
        AttributeError: 'BaseEventLoop' object has no attribute '_init'
        >>> BaseEventLoop('stdio')
        Traceback (most recent call last):
            ...
        AttributeError: 'BaseEventLoop' object has no attribute '_init'
        >>> BaseEventLoop('child', ['nvim', '--embed', '-u', 'NONE'])
        Traceback (most recent call last):
            ...
        AttributeError: 'BaseEventLoop' object has no attribute '_init'

        This calls the implementation-specific initialization
        `_init`, one of the `_connect_*` methods(based on `transport_type`)
        and `_start_reading()`
        """
        self._transport_type = transport_type
        self._signames = dict((k, v) for v, k in signal.__dict__.items()
                              if v.startswith('SIG'))
        self._on_data = None
        self._error = None
        self._init()
        try:
            getattr(self, '_connect_{}'.format(transport_type))(*args)
        except Exception as e:
            self.close()
            raise e
        self._start_reading()

    def connect_tcp(self, address, port):
        """Connect to tcp/ip `address`:`port`. Delegated to `_connect_tcp`."""
        info('Connecting to TCP address: %s:%d', address, port)
        self._connect_tcp(address, port)

    def connect_socket(self, path):
        """Connect to socket at `path`. Delegated to `_connect_socket`."""
        info('Connecting to %s', path)
        self._connect_socket(path)

    def connect_stdio(self):
        """Connect using stdin/stdout. Delegated to `_connect_stdio`."""
        info('Preparing stdin/stdout for streaming data')
        self._connect_stdio()

    def connect_child(self, argv):
        """Connect a new Nvim instance. Delegated to `_connect_child`."""
        info('Spawning a new nvim instance')
        self._connect_child(argv)

    def send(self, data):
        """Queue `data` for sending to Nvim."""
        debug("Sending '%s'", data)
        self._send(data)

    def threadsafe_call(self, fn):
        """Call a function in the event loop thread.

        This is the only safe way to interact with a session from other
        threads.
        """
        self._threadsafe_call(fn)

    def run(self, data_cb):
        """Run the event loop."""
        if self._error:
            err = self._error
            if isinstance(self._error, KeyboardInterrupt):
                # KeyboardInterrupt is not destructive(it may be used in
                # the REPL).
                # After throwing KeyboardInterrupt, cleanup the _error field
                # so the loop may be started again
                self._error = None
            raise err
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

    def stop(self):
        """Stop the event loop."""
        self._stop()
        debug('Stopped event loop')

    def close(self):
        """Stop the event loop."""
        self._close()
        debug('Closed event loop')

    def _on_signal(self, signum):
        msg = 'Received {}'.format(self._signames[signum])
        debug(msg)
        if signum == signal.SIGINT and self._transport_type == 'stdio':
            # When the transport is stdio, we are probably running as a Nvim
            # child process. In that case, we don't want to be killed by
            # ctrl+C
            return
        cls = Exception
        if signum == signal.SIGINT:
            cls = KeyboardInterrupt
        self._error = cls(msg)
        self.stop()

    def _on_error(self, error):
        debug(error)
        self._error = IOError(error)
        self.stop()

    def _on_interrupt(self):
        self.stop()
