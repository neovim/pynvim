"""Code for supporting compatibility across python versions."""

import sys
from imp import find_module as original_find_module


IS_PYTHON3 = sys.version_info >= (3, 0)


if IS_PYTHON3:
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

    # There is no 'long' type in Python3 just int
    long = int
    unicode_errors_default = 'surrogateescape'
else:
    find_module = original_find_module
    unicode_errors_default = 'strict'

NUM_TYPES = (int, long, float)
