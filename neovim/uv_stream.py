from collections import deque
from util import VimExit
from signal import SIGTERM
import sys, pyuv, logging

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class UvStream(object):
    """
    Stream abstraction implemented on top of libuv
    """
    def __init__(self, address=None, port=None):
        debug('initializing UvStream instance')
        self._loop = pyuv.Loop()
        self._connected = False
        self._data_cb = None
        self._error_cb = None
        self._connection_error = None
        self._pending_writes = 0
        # Select the type of handle
        if port:
            debug('TCP address was provided, connecting...')
            # tcp
            self._stream = pyuv.TCP(self._loop)
            self._stream.connect((address, port), self._on_connect)
        elif address:
            debug('Pipe address was provided, connecting...')
            # named pipe or unix socket
            self._stream = pyuv.Pipe(self._loop)
            self._stream.connect(address, self._on_connect)
        else:
            debug('No addresses were provided, will use stdin/stdout')
            # stdin/stdout
            self._read_stream = pyuv.Pipe(self._loop) 
            self._read_stream.open(sys.stdin.fileno())
            self._write_stream = pyuv.Pipe(self._loop) 
            self._write_stream.open(sys.stdout.fileno())
            self._connected = True
        self._async = pyuv.Async(self._loop, self._on_async)
        self._term = pyuv.Signal(self._loop)
        self._term.start(self._on_term, SIGTERM)


    """
    Called when the libuv stream is connected
    """
    def _on_connect(self, stream, error):
        self.loop_stop()
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error connecting to neovim: %s', msg)
            self._connection_error = IOError(msg)
            return
        self._connected = True
        self._read_stream = self._write_stream = stream


    def _on_term(self, handle, signum):
        self.loop_stop()
        self._error_cb(IOError('Received SIGTERM'))


    def _on_async(self, handle):
        """
        Called when the async handle is fired
        """
        self.loop_stop()


    def _connect(self):
        while not self._connected and not self._connection_error:
            self._loop.run(pyuv.UV_RUN_ONCE)


    def _on_read(self, handle, data, error):
        """
        Called when data is read from the libuv stream
        """
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error reading data: %s', msg)
            self._error_cb(IOError(msg))
        elif not data:
            warn('connection was closed by neovim')
            self._error_cb(IOError('EOF'))
        else:
            debug('successfully read %d bytes of data', len(data))
            self._data_cb(data)


    def interrupt(self):
        """
        Stops the event loop from another thread.
        """
        self._async.send()


    def send(self, data):
        if not self._connected:
            self._connect()
            if self._connection_error:
                err = self._connection_error
                self._connection_error = None
                raise err
        self._pending_writes += 1
        data_len = len(data)

        def write_cb(handle, error):
            self._pending_writes -= 1
            if error:
                msg = pyuv.errno.strerror(error)
                warn('error writing data: %s', msg)
                self._error_cb(IOError(msg))
            debug('successfully wrote %d bytes of data', data_len)

        debug('writing %d bytes of data', data_len)
        # queue the data for writing
        self._write_stream.write(data, write_cb)


    def loop_start(self, data_cb, error_cb):
        if not self._connected:
            self._connect()
            if self._connection_error:
                err = self._connection_error
                self._connection_error = None
                return error_cb(err)

        self._data_cb = data_cb
        self._error_cb = error_cb
        self._read_stream.start_read(self._on_read)
        debug('entering libuv event loop')
        self._loop.run(pyuv.UV_RUN_DEFAULT)
        debug('exited libuv event loop')
        self._read_stream.stop_read()
        self._data_cb = None
        self._error_cb = None


    def loop_stop(self):
        """
        Stops the event loop
        """
        self._loop.stop()
        debug('stopped event loop')
