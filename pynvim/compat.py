"""Code for compatibility across Python versions."""

import warnings
from imp import find_module as original_find_module


def find_module(fullname, path):
    """Compatibility wrapper for imp.find_module.

    Automatically decodes arguments of find_module, in Python3
    they must be Unicode
    """
    if isinstance(fullname, bytes):
        fullname = fullname.decode()
    if isinstance(path, bytes):
        path = path.decode()
    elif isinstance(path, list):
        newpath = []
        for element in path:
            if isinstance(element, bytes):
                newpath.append(element.decode())
            else:
                newpath.append(element)
        path = newpath
    return original_find_module(fullname, path)


unicode_errors_default = 'surrogateescape'

NUM_TYPES = (int, float)


def check_async(async_, kwargs, default):
    """Return a value of 'async' in kwargs or default when async_ is None.

    This helper function exists for backward compatibility (See #274).
    It shows a warning message when 'async' in kwargs is used to note users.
    """
    if async_ is not None:
        return async_
    elif 'async' in kwargs:
        warnings.warn(
            '"async" attribute is deprecated. Use "async_" instead.',
            DeprecationWarning,
        )
        return kwargs.pop('async')
    else:
        return default
