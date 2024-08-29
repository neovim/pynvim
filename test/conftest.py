"""Configs for pytest."""

import gc
import json
import os
import sys
from typing import Generator

import pytest

import pynvim

pynvim.setup_logging("test")


@pytest.fixture
def vim() -> Generator[pynvim.Nvim, None, None]:
    """Create an embedded, sub-process Nvim fixture instance."""
    editor: pynvim.Nvim

    child_argv = os.environ.get('NVIM_CHILD_ARGV')
    listen_address = os.environ.get('NVIM')
    if child_argv is None and listen_address is None:
        child_argv = json.dumps([
            "nvim",
            "--clean",  # no config and plugins (-u NONE), no SHADA
            "-n",  # no swap file
            "--embed",
            "--headless",
            # Always use the same exact python executable regardless of $PATH
            "--cmd", f"let g:python3_host_prog='{sys.executable}'",
        ])

    if child_argv is not None:
        editor = pynvim.attach('child', argv=json.loads(child_argv))
    else:
        assert listen_address is not None and listen_address != ''
        editor = pynvim.attach('socket', path=listen_address)

    try:
        yield editor

    finally:
        # Ensure all internal resources (pipes, transports, etc.) are always
        # closed properly. Otherwise, during GC finalizers (__del__) will raise
        # "Event loop is closed" error.
        editor.close()

        gc.collect()  # force-run GC, to early-detect potential leakages
