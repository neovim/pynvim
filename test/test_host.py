# type: ignore
# pylint: disable=protected-access
import os
from typing import Sequence

from pynvim.plugin.host import Host, host_method_spec
from pynvim.plugin.script_host import ScriptHost

__PATH__ = os.path.abspath(os.path.dirname(__file__))


def test_host_imports(vim):
    h = ScriptHost(vim)
    try:
        assert h.module.__dict__['vim']
        assert h.module.__dict__['vim'] == h.legacy_vim
        assert h.module.__dict__['sys']
    finally:
        h.teardown()


def test_host_import_rplugin_modules(vim):
    # Test whether a Host can load and import rplugins (#461).
    # See also $VIMRUNTIME/autoload/provider/pythonx.vim.
    h = Host(vim)

    plugins: Sequence[str] = [  # plugin paths like real rplugins
        os.path.join(__PATH__, "./fixtures/simple_plugin/rplugin/python3/simple_nvim.py"),
        os.path.join(__PATH__, "./fixtures/module_plugin/rplugin/python3/mymodule/"),
        os.path.join(__PATH__, "./fixtures/module_plugin/rplugin/python3/mymodule"),  # duplicate
    ]
    h._load(plugins)
    assert len(h._loaded) == 2

    # pylint: disable-next=unbalanced-tuple-unpacking
    simple_nvim, mymodule = list(h._loaded.values())
    assert simple_nvim['module'].__name__ == 'simple_nvim'
    assert mymodule['module'].__name__ == 'mymodule'


def test_host_clientinfo(vim):
    h = Host(vim)
    assert h._request_handlers.keys() == host_method_spec.keys()
    assert 'remote' == vim.api.get_chan_info(vim.channel_id)['client']['type']
    h._load([])
    assert 'host' == vim.api.get_chan_info(vim.channel_id)['client']['type']


# Smoke test for Host._on_error_event(). #425
def test_host_async_error(vim):
    h = Host(vim)
    h._load([])
    # Invoke a bogus Ex command via notify (async).
    vim.command("lolwut", async_=True)
    event = vim.next_message()
    assert event[1] == 'nvim_error_event'
    assert 'rplugin-host: Async request caused an error:\nboom\n' \
           in h._on_error_event(None, 'boom')
