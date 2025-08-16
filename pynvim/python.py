"""Wrapper to expose the Python interpreter as `pynvim-python`.

`setup.py` declares an entry point for the `main()` function below. When
`pynvim` is installed, an executable named `pynvim-python` will be generated
that will invoke `main()` below; that function then simply chains to the
underlying Python interpreter, passing along all command-line arguments.

The intent is to have `pynvim-python` be on the `PATH` such that an invocation
such as:

    pynvim-python -c 'import pynvim'

is equivalent to explicitly running the correct Python interpreter where
`pynvim` is installed:

    /path/to/python -c 'import pynvim'

This allows Neovim to automatically detect the correct Python interpreter for
use with `pynvim`.
"""

import subprocess
import sys


def main() -> None:
    """Chain to Python interpreter, passing all command-line args."""
    subprocess.run([sys.executable] + sys.argv[1:])
