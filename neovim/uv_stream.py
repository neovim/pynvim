from collections import deque
from .util import VimExit
import sys, pyuv, logging, signal

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class UvStream(object):
    """
    Stream abstraction implemented on top of libuv
    """
    def __init__(self, address=None, port=None, spawn_argv=None):
        debug('initializing UvStream instance')
        self._loop = pyuv.Loop()
        self._fatal = None
        self._connected = False
        self._data_cb = None
        self._error_cb = None
        self._connection_error = None
        self._pending_writes = 0
        self._async = pyuv.Async(self._loop, self._on_async)
        self._term = pyuv.Signal(self._loop)
        self._term.start(self._on_signal, signal.SIGTERM)
        self._int = pyuv.Signal(self._loop)
        self._int.start(self._on_signal, signal.SIGINT)
        self._signames = dict((k, v) for v, k in signal.__dict__.items() \
                              if v.startswith('SIG'))
        self._error_stream = None
        # Select the type of handle
        if spawn_argv:
            self.init_spawn(spawn_argv)
        elif port:
            self.init_tcp(address, port)
        elif address:
            self.init_pipe(address)
        else:
            self.init_stdio()


    def init_tcp(self, address, port):
        # tcp/ip
        debug('TCP address was provided, connecting...')
        self._stream = pyuv.TCP(self._loop)
        self._stream.connect((address, port), self._on_connect)


    def init_pipe(self, address):
        # named pipe or unix socket
        debug('Pipe address was provided, connecting...')
        self._stream = pyuv.Pipe(self._loop)
        self._stream.connect(address, self._on_connect)


    def init_stdio(self):
        # stdin/stdout
        debug('No addresses were provided, will use stdin/stdout')
        self._read_stream = pyuv.Pipe(self._loop) 
        self._read_stream.open(sys.stdin.fileno())
        self._write_stream = pyuv.Pipe(self._loop) 
        self._write_stream.open(sys.stdout.fileno())
        self._connected = True


    def init_spawn(self, argv):
        # spawn a new neovim instance with argv
        self._write_stream = pyuv.Pipe(self._loop)
        self._read_stream = pyuv.Pipe(self._loop)
        self._error_stream = pyuv.Pipe(self._loop)
        stdin = pyuv.StdIO(self._write_stream,
                           flags=pyuv.UV_CREATE_PIPE + pyuv.UV_READABLE_PIPE)
        stdout = pyuv.StdIO(self._read_stream,
                            flags=pyuv.UV_CREATE_PIPE + pyuv.UV_WRITABLE_PIPE)
        stderr = pyuv.StdIO(self._error_stream,
                            flags=pyuv.UV_CREATE_PIPE + pyuv.UV_WRITABLE_PIPE)
        self._process = pyuv.Process(self._loop)
        self._process.spawn(file=argv[0],
                            exit_callback=self._on_exit,
                            args=argv[1:],
                            flags=pyuv.UV_PROCESS_WINDOWS_HIDE,
                            stdio=(stdin, stdout, stderr,))
        self._connected = True

    """
    Called when the libuv stream is connected
    """
    def _on_connect(self, stream, error):
        self.loop_stop()
        if error:
            msg = pyuv.errno.strerror(error)
            self._fatal = msg
            warn('error connecting to neovim: %s', msg)
            self._connection_error = IOError(msg)
            return
        self._connected = True
        self._read_stream = self._write_stream = stream


    def _on_signal(self, handle, signum):
        self.loop_stop()
        err = Exception('Received %s' % self._signames[signum])
        if not self._error_cb:
            raise err
        self._error_cb(err)


    def _on_async(self, handle):
        """
        Called when the async handle is fired
        """
        self.loop_stop()


    def _connect(self):
        while not self._connected and not self._connection_error:
            self._loop.run(pyuv.UV_RUN_ONCE)


    def _on_exit(self, handle, exit_status, term_signal):
        self._loop.stop()
        self._fatal = (
            'The child nvim instance exited with status %s' % exit_status)


    def _on_stderr_read(self, handle, data, error):
        if error or not data:
            msg = pyuv.errno.strerror(error)
            warn('Error reading child nvim stderr: %s', msg)
            err = IOError(msg)
            if not self._error_cb:
                self._loop.stop()
                self._fatal = err
                raise err
            self._error_cb(err)
        else:
            warn('nvim stderr: %s', data)


    def _on_read(self, handle, data, error):
        """
        Called when data is read from the libuv stream
        """
        if error:
            msg = pyuv.errno.strerror(error)
            warn('error reading data: %s', msg)
            self._error_cb(IOError(msg))
            self._loop.stop()
            self._fatal = msg
        elif not data:
            warn('connection was closed by neovim')
            self._loop.stop()
            self._fatal = 'EOF'
            self._error_cb(IOError(self._fatal))
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
                self._loop.stop()
                msg = pyuv.errno.strerror(error)
                self._fatal = msg
                warn('error writing data: %s', msg)
                self._error_cb(IOError(msg))
            debug('successfully wrote %d bytes of data', data_len)

        debug('writing %d bytes of data', data_len)
        # queue the data for writing
        self._write_stream.write(data, write_cb)


    def loop_start(self, data_cb, error_cb):
        if self._fatal:
            raise IOError('A fatal error was raised and the connection ' +
                          'was permanently closed: %s', self._fatal)
        if not self._connected:
            self._connect()
            if self._connection_error:
                err = self._connection_error
                self._connection_error = None
                return error_cb(err)

        self._data_cb = data_cb
        self._error_cb = error_cb
        self._read_stream.start_read(self._on_read)
        if self._error_stream:
            self._error_stream.start_read(self._on_stderr_read)
        debug('entering libuv event loop')
        self._loop.run(pyuv.UV_RUN_DEFAULT)
        debug('exited libuv event loop')
        if self._error_stream:
            self._error_stream.stop_read()
        self._read_stream.stop_read()
        self._data_cb = None
        self._error_cb = None


    def loop_stop(self):
        """
        Stops the event loop
        """
        self._loop.stop()
        debug('stopped event loop')
