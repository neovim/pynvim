"""Event loop implementation that uses pyuv(libuv-python bindings)."""
import sys
from collections import deque

import pyuv

from pynvim.msgpack_rpc.event_loop.base import BaseEventLoop


class UvEventLoop(BaseEventLoop):

    """`BaseEventLoop` subclass that uses `pvuv` as a backend."""

    def _init(self):
        self._loop = pyuv.Loop()
        self._async = pyuv.Async(self._loop, self._on_async)
        self._connection_error = None
        self._error_stream = None
        self._callbacks = deque()

    def _on_connect(self, stream, error):
        self.stop()
        if error:
            msg = 'Cannot connect to {}: {}'.format(
                self._connect_address, pyuv.errno.strerror(error))
            self._connection_error = OSError(msg)
            return
        self._read_stream = self._write_stream = stream

    def _on_read(self, handle, data, error):
        if error or not data:
            msg = pyuv.errno.strerror(error) if error else 'EOF'
            self._on_error(msg)
            return
        if handle == self._error_stream:
            return
        self._on_data(data)

    def _on_write(self, handle, error):
        if error:
            msg = pyuv.errno.strerror(error)
            self._on_error(msg)

    def _on_exit(self, handle, exit_status, term_signal):
        self._on_error('EOF')

    def _disconnected(self, *args):
        raise OSError('Not connected to Nvim')

    def _connect_tcp(self, address, port):
        stream = pyuv.TCP(self._loop)
        self._connect_address = '{}:{}'.format(address, port)
        stream.connect((address, port), self._on_connect)

    def _connect_socket(self, path):
        stream = pyuv.Pipe(self._loop)
        self._connect_address = path
        stream.connect(path, self._on_connect)

    def _connect_stdio(self):
        self._read_stream = pyuv.Pipe(self._loop)
        self._read_stream.open(sys.stdin.fileno())
        self._write_stream = pyuv.Pipe(self._loop)
        self._write_stream.open(sys.stdout.fileno())

    def _connect_child(self, argv):
        self._write_stream = pyuv.Pipe(self._loop)
        self._read_stream = pyuv.Pipe(self._loop)
        self._error_stream = pyuv.Pipe(self._loop)
        stdin = pyuv.StdIO(self._write_stream,
                           flags=pyuv.UV_CREATE_PIPE + pyuv.UV_READABLE_PIPE)
        stdout = pyuv.StdIO(self._read_stream,
                            flags=pyuv.UV_CREATE_PIPE + pyuv.UV_WRITABLE_PIPE)
        stderr = pyuv.StdIO(self._error_stream,
                            flags=pyuv.UV_CREATE_PIPE + pyuv.UV_WRITABLE_PIPE)
        pyuv.Process.spawn(self._loop,
                           args=argv,
                           exit_callback=self._on_exit,
                           flags=pyuv.UV_PROCESS_WINDOWS_HIDE,
                           stdio=(stdin, stdout, stderr,))
        self._error_stream.start_read(self._on_read)

    def _start_reading(self):
        if self._transport_type in ['tcp', 'socket']:
            self._loop.run()
            if self._connection_error:
                self.run = self.send = self._disconnected
                raise self._connection_error
        self._read_stream.start_read(self._on_read)

    def _send(self, data):
        self._write_stream.write(data, self._on_write)

    def _run(self):
        self._loop.run(pyuv.UV_RUN_DEFAULT)

    def _stop(self):
        self._loop.stop()

    def _close(self):
        pass

    def _threadsafe_call(self, fn):
        self._callbacks.append(fn)
        self._async.send()

    def _on_async(self, handle):
        while self._callbacks:
            self._callbacks.popleft()()

    def _setup_signals(self, signals):
        self._signal_handles = []

        def handler(h, signum):
            self._on_signal(signum)

        for signum in signals:
            handle = pyuv.Signal(self._loop)
            handle.start(handler, signum)
            self._signal_handles.append(handle)

    def _teardown_signals(self):
        for handle in self._signal_handles:
            handle.stop()
