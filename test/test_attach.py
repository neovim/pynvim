"""Tests other session_types than subprocess Nvim."""

import contextlib
import os.path
import socket
import subprocess
import tempfile
import time
from typing import Generator

import pytest
import pytest_timeout  # pylint: disable=unused-import  # noqa

import pynvim
from pynvim.api import Nvim

# pylint: disable=consider-using-with
# pylint: disable=redefined-outer-name


@pytest.fixture
def server_addr() -> Generator[str, None, None]:
    """Get a socket/named pipe address using serverstart().

    On UNIX this is a socket path, on Windows a named pipe.
    """
    nvim = pynvim.attach('child', argv=[
        "nvim", "--clean", "--embed",
    ])
    addr = nvim.funcs.serverstart()
    nvim.funcs.serverstop(addr)
    nvim.close()

    yield addr


def test_connect_socket(server_addr: str) -> None:
    """Tests socket/pipe connection."""
    p = subprocess.Popen(["nvim", "--clean", "--headless",
                          "--listen", server_addr])
    time.sleep(0.2)  # wait a bit until nvim starts up

    try:
        nvim: Nvim = pynvim.attach('socket', path=server_addr)
        assert 42 == nvim.eval('42')
        assert "?" == nvim.command_output('echo "?"')
    finally:
        with contextlib.suppress(OSError):
            p.terminate()


def test_connect_socket_fail() -> None:
    """Tests UNIX socket connection, when the sock file is not found."""
    with pytest.raises(FileNotFoundError):
        pynvim.attach('socket', path='/tmp/not-exist.socket')


def find_free_port() -> int:
    """Find a free, available port number."""
    with socket.socket() as sock:
        sock.bind(('', 0))  # Bind to a free port provided by the host.
        return sock.getsockname()[1]


def test_connect_tcp() -> None:
    """Tests TCP connection."""
    address = '127.0.0.1'
    port = find_free_port()
    p = subprocess.Popen(["nvim", "--clean", "--headless",
                          "--listen", f"{address}:{port}"])
    time.sleep(0.2)  # wait a bit until nvim starts up

    try:
        nvim: Nvim = pynvim.attach('tcp', address=address, port=port)
        assert 42 == nvim.eval('42')
        assert "?" == nvim.command_output('echo "?"')
    finally:
        with contextlib.suppress(OSError):
            p.terminate()


@pytest.mark.timeout(5.0)
def test_connect_tcp_no_server() -> None:
    """Tests TCP socket connection that fails; connection refused."""
    port = find_free_port()

    with pytest.raises(ConnectionRefusedError):
        pynvim.attach('tcp', address='127.0.0.1', port=port)


@pytest.mark.xfail("os.name == 'nt'",
                   reason="stdio attach broken on Windows, see #544")
def test_connect_stdio(vim: Nvim) -> None:
    """Tests stdio connection, using jobstart(..., {'rpc': v:true})."""

    def source(vim: Nvim, code: str) -> None:
        """Source a vimscript code in the embedded nvim instance."""
        fd, fname = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(code)
            vim.command('source ' + fname)
        finally:
            os.unlink(fname)

    # A helper function for debugging that captures what pynvim writes to
    # stderr (e.g. python stacktrace): used as a |on_stderr| callback
    source(vim, """
        function! OutputHandler(j, lines, event_type)
            if a:event_type == 'stderr'
                for l:line in a:lines
                    echom l:line
                endfor
            endif
        endfunction
    """)

    remote_py_code = '\n'.join([
        'import pynvim',
        'nvim = pynvim.attach("stdio")',
        'print("rplugins can write to stdout")',  # tests #377 (#60)
        'nvim.api.command("let g:success = 42")',
    ])
    # see :help jobstart(), *jobstart-options* |msgpack-rpc|
    jobid = vim.funcs.jobstart([
        'python3', '-c', remote_py_code,
    ], {'rpc': True, 'on_stderr': 'OutputHandler'})
    assert jobid > 0
    exitcode = vim.funcs.jobwait([jobid], 5000)[0]
    messages = vim.command_output('messages')
    assert exitcode == 0, ("the python process failed, :messages =>\n\n" +
                           messages)

    assert 42 == vim.eval('g:success')
    assert "rplugins can write to stdout" in messages
