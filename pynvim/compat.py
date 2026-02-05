"""Code for compatibility across Python versions."""
import warnings
from typing import Any, Dict, Optional


unicode_errors_default = 'surrogateescape'

NUM_TYPES = (int, float)


def check_async(async_: Optional[bool], kwargs: Dict[str, Any], default: bool) -> bool:
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
