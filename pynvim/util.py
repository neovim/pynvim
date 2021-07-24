"""Shared utility functions."""

import sys
from traceback import format_exception
from types import SimpleNamespace


def format_exc_skip(skip, limit=None):
    """Like traceback.format_exc but allow skipping the first frames."""
    etype, val, tb = sys.exc_info()
    for i in range(skip):
        tb = tb.tb_next
    return (''.join(format_exception(etype, val, tb, limit))).rstrip()


def get_client_info(kind, type_, method_spec):
    """Returns a tuple describing the client."""
    name = "python{}-{}".format(sys.version_info[0], kind)
    attributes = {"license": "Apache v2",
                  "website": "github.com/neovim/pynvim"}
    return (name, VERSION.__dict__, type_, method_spec, attributes)


VERSION = SimpleNamespace(major=0, minor=4, patch=3, prerelease='')
