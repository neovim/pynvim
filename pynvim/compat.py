"""Code for compatibility across Python versions."""

import sys
import warnings


IS_PYTHON3 = sys.version_info >= (3, 0)


if IS_PYTHON3:
    # There is no 'long' type in Python3 just int
    long = int
    unicode_errors_default = 'surrogateescape'
else:
    from imp import find_module as original_find_module
    find_module = original_find_module
    unicode_errors_default = 'ignore'

NUM_TYPES = (int, long, float)


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
