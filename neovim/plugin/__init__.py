"""Nvim plugin/host subpackage."""

from .decorators import (autocmd, command, encoding, function, plugin,
                         rpc_export, shutdown_hook)
from .host import Host


__all__ = ('Host', 'plugin', 'rpc_export', 'command', 'autocmd',
           'function', 'encoding', 'shutdown_hook')
