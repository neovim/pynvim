import json
import os

import pytest

import pynvim

pynvim.setup_logging("test")


@pytest.fixture
def vim() -> pynvim.Nvim:
    child_argv = os.environ.get('NVIM_CHILD_ARGV')
    listen_address = os.environ.get('NVIM_LISTEN_ADDRESS')
    if child_argv is None and listen_address is None:
        child_argv = json.dumps([
            "nvim",
            "--clean",  # no config and plugins (-u NONE), no SHADA
            "-n",  # no swap file
            "--embed",
            "--headless",
            "-c", "let g:python3_host_prog='python3'",  # workaround neovim/neovim#25316
        ])

    if child_argv is not None:
        editor = pynvim.attach('child', argv=json.loads(child_argv))
    else:
        assert listen_address is not None and listen_address != ''
        editor = pynvim.attach('socket', path=listen_address)

    return editor
