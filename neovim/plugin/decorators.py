"""Decorators used by python host plugin system."""

import inspect
import logging

from ..compat import IS_PYTHON3

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warning,)
__all__ = ('plugin', 'rpc_export', 'command', 'autocmd', 'function',
           'encoding', 'shutdown_hook')


def plugin(cls):
    """Tag a class as a plugin.

    This decorator is required to make the a class methods discoverable by the
    plugin_load method of the host.
    """
    cls._nvim_plugin = True
    # the _nvim_bind attribute is set to True by default, meaning that
    # decorated functions have a bound Nvim instance as first argument.
    # For methods in a plugin-decorated class this is not required, because
    # the class initializer will already receive the nvim object.
    predicate = lambda fn: hasattr(fn, '_nvim_bind')
    for _, fn in inspect.getmembers(cls, predicate):
        if IS_PYTHON3:
            fn._nvim_bind = False
        else:
            fn.im_func._nvim_bind = False
    return cls


def rpc_export(rpc_method_name, sync=False):
    """Export a function or plugin method as a msgpack-rpc request handler."""
    def dec(f):
        f._nvim_rpc_method_name = rpc_method_name
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = False
        return f
    return dec


def command(name, nargs=0, complete=None, range=None, count=None, bang=False,
            register=False, sync=False, eval=None):
    """Tag a function or plugin method as a Nvim command handler."""
    def dec(f):
        f._nvim_rpc_method_name = 'command:{0}'.format(name)
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

        opts = {}

        if range is not None:
            opts['range'] = '' if range is True else str(range)
        elif count:
            opts['count'] = count

        if bang:
            opts['bang'] = True

        if register:
            opts['register'] = True

        if nargs:
            opts['nargs'] = nargs

        if complete:
            opts['complete'] = complete

        if eval:
            opts['eval'] = eval

        f._nvim_rpc_spec = {
            'type': 'command',
            'name': name,
            'sync': sync,
            'opts': opts
        }
        return f
    return dec


def autocmd(name, pattern='*', sync=False, eval=None):
    """Tag a function or plugin method as a Nvim autocommand handler."""
    def dec(f):
        f._nvim_rpc_method_name = 'autocmd:{0}:{1}'.format(name, pattern)
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

        opts = {
            'pattern': pattern
        }

        if eval:
            opts['eval'] = eval

        f._nvim_rpc_spec = {
            'type': 'autocmd',
            'name': name,
            'sync': sync,
            'opts': opts
        }
        return f
    return dec


def function(name, range=False, sync=False, eval=None):
    """Tag a function or plugin method as a Nvim function handler."""
    def dec(f):
        f._nvim_rpc_method_name = 'function:{0}'.format(name)
        f._nvim_rpc_sync = sync
        f._nvim_bind = True
        f._nvim_prefix_plugin_path = True

        opts = {}

        if range:
            opts['range'] = '' if range is True else str(range)

        if eval:
            opts['eval'] = eval

        f._nvim_rpc_spec = {
            'type': 'function',
            'name': name,
            'sync': sync,
            'opts': opts
        }
        return f
    return dec


def shutdown_hook(f):
    """Tag a function or method as a shutdown hook."""
    f._nvim_shutdown_hook = True
    f._nvim_bind = True
    return f


def encoding(encoding=True):
    """Configure automatic encoding/decoding of strings."""
    def dec(f):
        f._nvim_encoding = encoding
        return f
    return dec
