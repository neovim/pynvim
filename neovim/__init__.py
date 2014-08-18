from .client import Client
from .script_host import ScriptHost
from .plugin_host import PluginHost
from .uv_stream import UvStream
from .msgpack_stream import MsgpackStream
from .rpc_stream import RPCStream
from time import sleep
import logging, os

__all__ = ['connect', 'start_host', 'ScriptHost', 'PluginHost']


# Required for python 2.6
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


def connect(address=None, port=None, vim_compatible=False, decode_str=False):
    client = Client(RPCStream(MsgpackStream(UvStream(address, port)), decode_str=decode_str),
                    vim_compatible)
    return client.vim


def spawn(argv, decode_str=False):
    client = Client(RPCStream(MsgpackStream(UvStream(spawn_argv=argv)), decode_str=decode_str))
    return client.vim


def start_host(address=None, port=None):
    logging.root.addHandler(NullHandler())
    logger = logging.getLogger(__name__)
    info = logger.info
    if 'NVIM_PYTHON_LOG_FILE' in os.environ:
        logfile = os.environ['NVIM_PYTHON_LOG_FILE'].strip()
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
    info('connecting to neovim')
    vim = connect(address, port, vim_compatible=True)
    info('connected to neovim')
    with PluginHost(vim, discovered_plugins=[ScriptHost]) as host:
        host.run()

