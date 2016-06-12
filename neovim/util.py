"""Shared utility functions."""

import sys
from traceback import format_exception


def format_exc_skip(skip, limit=None):
    """Like traceback.format_exc but allow skipping the first frames."""
    type, val, tb = sys.exc_info()
    for i in range(skip):
        tb = tb.tb_next
    return ('\n'.join(format_exception(type, val, tb, limit))).rstrip()
