import sys, pyuv

class UvStream(object):
    """
    Blocking read/write stream implemented with libuv. Provides the read/write
    interface required by `Client`
    """
    def __init__(self, address=None, port=None):
        self._loop = pyuv.Loop()
        self._error = None
        self._data = None
        self._written = True
        self._connected = False
        self._timed_out = False
        self._timer = pyuv.Timer(self._loop)
        self._timeout_cb = self._on_timeout.__get__(self, UvStream)
        self._read_cb = self._on_read.__get__(self, UvStream)
        self._write_cb = self._on_write.__get__(self, UvStream)
        connect_cb = self._on_connect.__get__(self, UvStream)
        # Select the type of handle
        if port:
            # tcp
            self._stream = pyuv.TCP(self._loop)
            self._stream.connect((address, port), connect_cb)
        elif address:
            # named pipe or unix socket
            self._stream = pyuv.Pipe(self._loop)
            self._stream.connect(address, connect_cb)
        else:
            # stdin/stdout
            self._read_stream = pyuv.Pipe(self._loop) 
            self._read_stream.open(sys.stdin.fileno())
            self._write_stream = pyuv.Pipe(self._loop) 
            self._write_stream.open(sys.stdout.fileno())
        async_cb = self._on_async.__get__(self, UvStream)
        self._async = pyuv.Async(self._loop, async_cb)
        self._interrupted = False

    """
    Called when the libuv stream is connected
    """
    def _on_connect(self, stream, error):
        if error:
            self._error = IOError(pyuv.errno.strerror(error))
            return
        self._connected = True
        self._read_stream = self._write_stream = stream

    """
    Called when data is read from the libuv stream
    """
    def _on_read(self, handle, data, error):
        if error:
            self._error = IOError(pyuv.errno.strerror(error))
            return
        elif not data:
            self._error = IOError('EOF')
            return
        else:
            self._data = data
        self._loop.stop()

    """
    Called when the async handle is fired
    """
    def _on_async(self, handle):
        self._interrupted = True
        self._loop.stop()

    """
    Called when a timeout occurs
    """
    def _on_timeout(self, handle):
        self._timed_out = True
        self._loop.stop()

    """
    Called when data is written to the libuv stream
    """
    def _on_write(self, handle, error):
        if error:
            self._error = IOError(pyuv.errno.strerror(error))
            return
        self._written = True
        self._loop.stop()
    
    """
    Runs the event loop until a certain condition
    """
    def _run(self, condition=lambda: True, timeout=None):
        if timeout == 0 and not condition():
            return

        if timeout:
            self._timer.start(self._timeout_cb, timeout, 0)

        while not (condition() or self._timed_out or self._interrupted):
            if self._error:
                if timeout and not self._timed_out:
                    self._timer.stop()
                # Error occurred, throw it to the caller
                err = self._error
                self._error = None
                raise err
            # Continue processing events
            self._loop.run(pyuv.UV_RUN_ONCE)

        if timeout and not self._timed_out:
            self._timer.stop()
        self._timed_out = False
        # Always resed this
        self._interrupted = False

    """
    Read some data
    """
    def read(self, timeout=None):
        # first ensure the stream is connected
        self._run(lambda: self._connected)
        # start reading
        self._read_stream.start_read(self._read_cb)
        # wait until some data is read
        self._run(lambda: self._data, timeout)
        # stop reading
        self._read_stream.stop_read()
        # return a chunk of data
        rv = self._data
        self._data = None
        return rv

    """
    Write some data
    """
    def write(self, chunk):
        # first ensure the stream is connected
        self._run(lambda: self._connected)
        # queue the chunk for writing
        self._write_stream.write(chunk, self._write_cb)
        # unset the written flag
        self._written = False
        # wait for the flag
        self._run(lambda: self._written)

    """
    Interrupts a `read` call from another thread.
    """
    def interrupt(self):
        self._async.send()
