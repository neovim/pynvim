"""Shared utility functions."""

import sys
from traceback import format_exception
from typing import Any, Dict, Optional, Tuple, TypeVar

from pynvim._version import VERSION


def format_exc_skip(skip: int, limit: Optional[int] = None) -> str:
    """Like traceback.format_exc but allow skipping the first frames."""
    etype, val, tb = sys.exc_info()
    for _ in range(skip):
        if tb is not None:
            tb = tb.tb_next
    return ("".join(format_exception(etype, val, tb, limit))).rstrip()


T1 = TypeVar("T1")
T2 = TypeVar("T2")


def get_client_info(
    kind: str, type_: T1, method_spec: T2
) -> Tuple[str, Dict[str, Any], T1, T2, Dict[str, str]]:
    """Returns a tuple describing the client."""
    name = "python{}-{}".format(sys.version_info[0], kind)
    attributes = {"license": "Apache v2", "website": "github.com/neovim/pynvim"}
    return (name, VERSION.__dict__, type_, method_spec, attributes)
