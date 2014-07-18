from collections import deque
from util import VimExit
from signal import SIGTERM
import sys, pyuv, logging

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class UvStream(object):
    """
    Blocking read/write stream implemented with libuv. Provides the read/write
    interface required by `Client`
    """
    def __init__(self, address=None, port=None):
        debug('initializing UvStream instance')
        self._loop = pyuv.Loop()
        self._errors = deque()
        self._data = deque()
        self._written = True
        self._connected = False
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
            self._read_stream.start_read(self._on_read)
        self._async = pyuv.Async(self._loop, self._on_async)
        self._interrupted = False
        self._term = pyuv.Signal(self._loop)
        self._term.start(self._on_term, SIGTERM)

    """
    Called when the libuv stream is connected
    """
    def _on_connect(self, stream, error):
        self._loop.stop()
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error connecting to neovim: %s', msg)
            self._errors.append(VimExit(msg))
            return
        self._connected = True
        self._read_stream = self._write_stream = stream
        self._read_stream.start_read(self._on_read)


    def _on_term(self, handle, signum):
        self._loop.stop()
        self._errors.append(VimExit('Received SIGTERM'))


    """
    Called when data is read from the libuv stream
    """
    def _on_read(self, handle, data, error):
        self._loop.stop()
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error reading data: %s', msg)
            self._errors.append(VimExit(msg))
            return
        elif not data:
            warn('connection was closed by neovim')
            self._errors.append(VimExit('EOF'))
            return
        else:
            debug('successfully read %d bytes of data', len(data))
            self._data.append(data)

    """
    Called when the async handle is fired
    """
    def _on_async(self, handle):
        debug('interrupted')
        self._interrupted = True
        self._loop.stop()

    """
    Called when data is written to the libuv stream
    """
    def _on_write(self, handle, error):
        self._loop.stop()
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error writing data: %s', msg)
            self._errors.append(VimExit(msg))
            return
        debug('successfully wrote %d bytes of data', self.last_write_size)
        self._written = True
    
    """
    Runs the event loop until a certain condition
    """
    def _run(self, condition=lambda: True):
        if self._errors:
            debug('pending errors collected in previous event loop iteration')
            # Pending errors, throw it now
            raise self._errors.popleft()
        while not condition():
            if self._errors:
                debug('caught error in event loop')
                # Error occurred, throw it to the caller
                raise self._errors.popleft()
            # Continue processing events
            debug('run a blocking event event loop iteration...')
            self._loop.run(pyuv.UV_RUN_ONCE)


    """
    Read some data
    """
    def read(self):
        if self._data:
            return self._data.popleft()
        # first ensure the stream is connected
        if not self._connected:
            self._run(lambda: self._connected)
        # wait until some data is read
        self._run(lambda: self._interrupted or self._data)
        if self._interrupted:
            self._interrupted = False
            return
        # return a chunk of data
        return self._data.popleft()

    """
    Write some data
    """
    def write(self, chunk):
        if not self._connected:
            # first ensure the stream is connected
            self._run(lambda: self._connected)
        # queue the chunk for writing
        self.last_write_size = len(chunk)
        debug('writing %d bytes of data', self.last_write_size)
        self._write_stream.write(chunk, self._on_write)
        # unset the written flag
        self._written = False
        # wait for the flag
        self._run(lambda: self._written)

    """
    Interrupts a `read` call from another thread.
    """
    def interrupt(self):
        self._async.send()
