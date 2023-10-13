"""Python client for Nvim.

Client library for talking with Nvim processes via its msgpack-rpc API.
"""
import logging
import os
import sys
from types import SimpleNamespace as Version
from typing import List, Optional, cast, overload

from pynvim._version import VERSION, __version__
from pynvim.api import Nvim, NvimError
from pynvim.msgpack_rpc import (ErrorResponse, Session, TTransportType,
                                child_session, socket_session, stdio_session,
                                tcp_session)
from pynvim.plugin import (Host, autocmd, command, decode, encoding, function,
                           plugin, rpc_export, shutdown_hook)

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal


__all__ = ('tcp_session', 'socket_session', 'stdio_session', 'child_session',
           'start_host', 'autocmd', 'command', 'encoding', 'decode',
           'function', 'plugin', 'rpc_export', 'Host', 'Nvim', 'NvimError',
           'Version', 'VERSION', '__version__',
           'shutdown_hook', 'attach', 'setup_logging', 'ErrorResponse',
           )


def start_host(session: Optional[Session] = None) -> None:
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

    # Special case: the legacy scripthost receives a single relative filename
    # while the rplugin host will receive absolute paths.
    if plugins == ["script_host.py"]:
        name = "script"
    else:
        name = "rplugin"

    setup_logging(name)

    if not session:
        session = stdio_session()
    nvim = Nvim.from_session(session)

    if nvim.version.api_level < 1:
        sys.stderr.write("This version of pynvim "
                         "requires nvim 0.1.6 or later")
        sys.exit(1)

    host = Host(nvim)
    host.start(plugins)


@overload
def attach(session_type: Literal['tcp'], address: str, port: int = 7450) -> Nvim: ...


@overload
def attach(session_type: Literal['socket'], *, path: str) -> Nvim: ...


@overload
def attach(session_type: Literal['child'], *, argv: List[str]) -> Nvim: ...


@overload
def attach(session_type: Literal['stdio']) -> Nvim: ...


def attach(
    session_type: TTransportType,
    address: Optional[str] = None,
    port: int = 7450,
    path: Optional[str] = None,
    argv: Optional[List[str]] = None,
    decode: Literal[True] = True
) -> Nvim:
    """Provide a nicer interface to create python api sessions.

    Previous machinery to create python api sessions is still there. This only
    creates a facade function to make things easier for the most usual cases.
    Thus, instead of:
        from pynvim import socket_session, Nvim
        session = tcp_session(address=<address>, port=<port>)
        nvim = Nvim.from_session(session)
    You can now do:
        from pynvim import attach
        nvim = attach('tcp', address=<address>, port=<port>)
    And also:
        nvim = attach('socket', path=<path>)
        nvim = attach('child', argv=<argv>)
        nvim = attach('stdio')

    When the session is not needed anymore, it is recommended to explicitly
    close it:
       nvim.close()
    It is also possible to use the session as a context manager:
       with attach('socket', path=thepath) as nvim:
           print(nvim.funcs.getpid())
           print(nvim.current.line)
    This will automatically close the session when you're done with it, or
    when an error occurred.


    """
    session = (
        tcp_session(cast(str, address), port) if session_type == 'tcp' else
        socket_session(cast(str, path)) if session_type == 'socket' else
        stdio_session() if session_type == 'stdio' else
        child_session(cast(List[str], argv)) if session_type == 'child' else
        None
    )

    if not session:
        raise Exception('Unknown session type "%s"' % session_type)

    return Nvim.from_session(session).with_decode(decode)


def setup_logging(name: str) -> None:
    """Setup logging according to environment variables."""
    logger = logging.getLogger(__name__)
    if 'NVIM_PYTHON_LOG_FILE' in os.environ:
        prefix = os.environ['NVIM_PYTHON_LOG_FILE'].strip()
        major_version = sys.version_info[0]
        logfile = '{}_py{}_{}'.format(prefix, major_version, name)
        handler = logging.FileHandler(logfile, 'w', 'utf-8')
        handler.formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s @ '
            '%(filename)s:%(funcName)s:%(lineno)s] %(process)s - %(message)s')
        logging.root.addHandler(handler)
        level = logging.INFO
        env_log_level = os.environ.get('NVIM_PYTHON_LOG_LEVEL', None)
        if env_log_level is not None:
            lvl = getattr(logging, env_log_level.strip(), None)
            if isinstance(lvl, int):
                level = lvl
            else:
                logger.warning('Invalid NVIM_PYTHON_LOG_LEVEL: %r, using INFO.',
                               env_log_level)
        logger.setLevel(level)
