"""Python client for Nvim.

Client library for talking with Nvim processes via it's msgpack-rpc API.
"""
import logging
import os
import sys

from .api import Nvim
from .compat import IS_PYTHON3
from .msgpack_rpc import (ErrorResponse, child_session, socket_session,
                          stdio_session, tcp_session)
from .plugin import (Host, autocmd, command, decode, encoding, function,
                     plugin, rpc_export, shutdown_hook)


__all__ = ('tcp_session', 'socket_session', 'stdio_session', 'child_session',
           'start_host', 'autocmd', 'command', 'encoding', 'decode',
           'function', 'plugin', 'rpc_export', 'Host', 'Nvim',
           'shutdown_hook', 'attach', 'setup_logging', 'ErrorResponse')


def start_host(session=None):
    """Promote the current process into python plugin host for Nvim.

    Start msgpack-rpc event loop for `session`, listening for Nvim requests
    and notifications. It registers Nvim commands for loading/unloading
    python plugins.

    The sys.stdout and sys.stderr streams are redirected to Nvim through
    `session`. That means print statements probably won't work as expected
    while this function doesn't return.

    This function is normally called at program startup and could have been
    defined as a separate executable. It is exposed as a library function for
    testing purposes only.
    """
    plugins = []
    for arg in sys.argv:
        _, ext = os.path.splitext(arg)
        if ext == '.py':
            plugins.append(arg)
        elif os.path.isdir(arg):
            init = os.path.join(arg, '__init__.py')
            if os.path.isfile(init):
                plugins.append(arg)

    # This is a special case to support the old workaround of
    # adding an empty .py file to make a package directory
    # visible, and it should be removed soon.
    for path in list(plugins):
        dup = path + ".py"
        if os.path.isdir(path) and dup in plugins:
            plugins.remove(dup)

    setup_logging()

    if not session:
        session = stdio_session()
    host = Host(Nvim.from_session(session))
    host.start(plugins)


def attach(session_type, address=None, port=None,
           path=None, argv=None, decode=None):
    """Provide a nicer interface to create python api sessions.

    Previous machinery to create python api sessions is still there. This only
    creates a facade function to make things easier for the most usual cases.
    Thus, instead of:
        from neovim import socket_session, Nvim
        session = tcp_session(address=<address>, port=<port>)
        nvim = Nvim.from_session(session)
    You can now do:
        from neovim import attach
        nvim = attach('tcp', address=<address>, port=<port>)
    And also:
        nvim = attach('socket', path=<path>)
        nvim = attach('child', argv=<argv>)
        nvim = attach('stdio')
    """
    session = (tcp_session(address, port) if session_type == 'tcp' else
               socket_session(path) if session_type == 'socket' else
               stdio_session() if session_type == 'stdio' else
               child_session(argv) if session_type == 'child' else
               None)

    if not session:
        raise Exception('Unknown session type "%s"' % session_type)

    if decode is None:
        decode = IS_PYTHON3

    return Nvim.from_session(session).with_decode(decode)


def setup_logging():
    """Setup logging according to environment variables."""
    logger = logging.getLogger(__name__)
    if 'NVIM_PYTHON_LOG_FILE' in os.environ:
        logfile = (os.environ['NVIM_PYTHON_LOG_FILE'].strip() +
                   '_' + str(os.getpid()))
        handler = logging.FileHandler(logfile, 'w')
        handler.formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s @ '
            '%(filename)s:%(funcName)s:%(lineno)s] %(process)s - %(message)s')
        logging.root.addHandler(handler)
        level = logging.INFO
        if 'NVIM_PYTHON_LOG_LEVEL' in os.environ:
            l = getattr(logging,
                        os.environ['NVIM_PYTHON_LOG_LEVEL'].strip(),
                        level)
            if isinstance(l, int):
                level = l
        logger.setLevel(level)


# Required for python 2.6
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


if not logging.root.handlers:
    logging.root.addHandler(NullHandler())
