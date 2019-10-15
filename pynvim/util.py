"""Shared utility functions."""

import sys
from traceback import format_exception, format_exception_only


def format_exc_skip(skip, limit=None):
    """Like traceback.format_exc but allow skipping the first frames."""
    etype, val, tb = sys.exc_info()
    for i in range(skip):
        tb = tb.tb_next
    return (''.join(format_exception(etype, val, tb, limit))).rstrip()


def format_exc_msg(skip=1, limit=None):
    """Format ``exc`` to be used in error messages.

    It duplicates the exception itself on the first line, since v:exception
    will only contain this.

    `repr()` is used for SyntaxErrors, because it will contain more information
    (including the full path) that cannot be easily displayed on a single line.

        SyntaxError('unexpected EOF while parsing',
                    ('<string>', 1, 12, 'syntaxerror(')))

    For all other exceptions `traceback.format_exception_only` is used,
    which is the same as the last line then (via with `format_exception` in
    `format_exc_skip`).
    """
    etype, value, _ = sys.exc_info()
    if issubclass(etype, SyntaxError):
        exc_msg = repr(value)
    else:
        exc_msg = format_exception_only(etype, value)[-1].rstrip('\n')
    return "{!s}\n{}".format(exc_msg, format_exc_skip(skip))


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


VERSION = Version(major=0, minor=4, patch=0, prerelease='')
