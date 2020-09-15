"""Shared utility functions."""

import sys
from traceback import format_exception


def format_exc_skip(skip, limit=None):
    """Like traceback.format_exc but allow skipping the first frames."""
    etype, val, tb = sys.exc_info()
    for i in range(skip):
        tb = tb.tb_next
    return (''.join(format_exception(etype, val, tb, limit))).rstrip()


# Taken from SimpleNamespace in python 3
class Version:
    """Helper class for version info."""

    def __init__(self, **kwargs):
        """Create the Version object."""
        self.__dict__.update(kwargs)

    def __repr__(self):
        """Return str representation of the Version."""
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))

    def __eq__(self, other):
        """Check if version is same as other."""
        return self.__dict__ == other.__dict__


def get_client_info(kind, type_, method_spec):
    """Returns a tuple describing the client."""
    name = "python{}-{}".format(sys.version_info[0], kind)
    attributes = {"license": "Apache v2",
                  "website": "github.com/neovim/pynvim"}
    return (name, VERSION.__dict__, type_, method_spec, attributes)


VERSION = Version(major=0, minor=4, patch=2, prerelease='')
