"""Nvim plugin/host subpackage."""

from .decorators import (autocmd, command, decode, encoding, function,
                         plugin, rpc_export, shutdown_hook)
from .host import Host


__all__ = ('Host', 'plugin', 'rpc_export', 'command', 'autocmd',
           'function', 'encoding', 'decode', 'shutdown_hook')
