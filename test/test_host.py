# type: ignore
# pylint: disable=protected-access
import os
from types import SimpleNamespace
from typing import Sequence

from pynvim.api.nvim import Nvim
from pynvim.plugin import decorators
from pynvim.plugin.host import Host, host_method_spec
from pynvim.plugin.script_host import ScriptHost

__PATH__ = os.path.abspath(os.path.dirname(__file__))


def test_host_imports(vim: Nvim):
    h = ScriptHost(vim)
    try:
        assert h.module.__dict__['vim']
        assert h.module.__dict__['vim'] == h.legacy_vim
        assert h.module.__dict__['sys']
    finally:
        h.teardown()


def test_host_import_rplugin_modules(vim: Nvim):
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
    assert len(h._specs) == 2
    assert len(h._load_errors) == 0

    # pylint: disable-next=unbalanced-tuple-unpacking
    simple_nvim, mymodule = list(h._loaded.values())
    assert simple_nvim['module'].__name__ == 'simple_nvim'
    assert mymodule['module'].__name__ == 'mymodule'


# @pytest.mark.timeout(5.0)
def test_host_register_plugin_handlers(vim: Nvim):
    """Test whether a Host can register plugin's RPC handlers."""
    h = Host(vim)

    @decorators.plugin
    class TestPluginModule:
        """A plugin for testing, having all types of the decorators."""
        def __init__(self, nvim: Nvim):
            self._nvim = nvim

        @decorators.rpc_export('python_foobar', sync=True)
        def foobar(self):
            pass

        @decorators.command("MyCommandSync", sync=True)
        def command(self):
            pass

        @decorators.function("MyFunction", sync=True)
        def function(self, a, b):
            return a + b

        @decorators.autocmd("BufEnter", pattern="*.py", sync=True)
        def buf_enter(self):
            vim.command("echom 'BufEnter'")

        @decorators.rpc_export('python_foobar_async', sync=False)
        def foobar_async(self):
            pass

        @decorators.command("MyCommandAsync", sync=False)
        def command_async(self):
            pass

        @decorators.function("MyFunctionAsync", sync=False)
        def function_async(self, a, b):
            return a + b

        @decorators.autocmd("BufEnter", pattern="*.async", sync=False)
        def buf_enter_async(self):
            vim.command("echom 'BufEnter'")

        @decorators.shutdown_hook
        def shutdown_hook():
            print("bye")

    @decorators.function("ModuleFunction")
    def module_function(self):
        pass

    dummy_module = SimpleNamespace(
        TestPluginModule=TestPluginModule,
        module_function=module_function,
    )
    h._load_plugin("virtual://dummy_module", module=dummy_module)
    assert list(h._loaded.keys()) == ["virtual://dummy_module"]
    assert h._loaded['virtual://dummy_module']['module'] is dummy_module

    # _notification_handlers: async commands and functions
    print(h._notification_handlers.keys())
    assert 'python_foobar_async' in h._notification_handlers
    assert 'virtual://dummy_module:autocmd:BufEnter:*.async' in h._notification_handlers
    assert 'virtual://dummy_module:command:MyCommandAsync' in h._notification_handlers
    assert 'virtual://dummy_module:function:MyFunctionAsync' in h._notification_handlers
    assert 'virtual://dummy_module:function:ModuleFunction' in h._notification_handlers

    # _request_handlers: sync commands and functions
    print(h._request_handlers.keys())
    assert 'python_foobar' in h._request_handlers
    assert 'virtual://dummy_module:autocmd:BufEnter:*.py' in h._request_handlers
    assert 'virtual://dummy_module:command:MyCommandSync' in h._request_handlers
    assert 'virtual://dummy_module:function:MyFunction' in h._request_handlers


def test_host_clientinfo(vim: Nvim):
    h = Host(vim)
    assert h._request_handlers.keys() == host_method_spec.keys()
    assert 'remote' == vim.api.get_chan_info(vim.channel_id)['client']['type']
    h._load([])
    assert 'host' == vim.api.get_chan_info(vim.channel_id)['client']['type']


# Smoke test for Host._on_error_event(). #425
def test_host_async_error(vim: Nvim):
    h = Host(vim)
    h._load([])
    # Invoke a bogus Ex command via notify (async).
    vim.command("lolwut", async_=True)
    event = vim.next_message()
    assert event[1] == 'nvim_error_event'

    h._on_error_event(None, 'boom')
    msg = vim.command_output('messages')
    assert 'rplugin-host: Async request caused an error:\nboom' in msg


def test_legacy_vim_eval(vim: Nvim):
    h = ScriptHost(vim)
    try:
        assert h.legacy_vim.eval('1') == '1'
        assert h.legacy_vim.eval('v:null') is None
        assert h.legacy_vim.eval('v:true') is True
        assert h.legacy_vim.eval('v:false') is False
    finally:
        h.teardown()
