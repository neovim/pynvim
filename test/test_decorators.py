# type: ignore
from pynvim.plugin.decorators import (Handler, autocmd, command, decode,
                                      function, plugin, rpc_export, shutdown_hook)


def _ensure_attributes(decorated: Handler) -> Handler:
    """Ensure that a Handler has all the private _nvim_* attributes set."""
    attrs = [
        k for k in Handler.__annotations__.keys() if k.startswith('_nvim_')
    ]

    for attr in attrs:
        assert hasattr(decorated, attr), \
            f"{decorated} does not have attr: {attr}"

    assert decorated._nvim_registered_name is None  # shouldn't be set yet
    return decorated


def test_rpc_export() -> None:

    @rpc_export("rpc_remote_point", sync=True)
    def handler():
        pass

    _ensure_attributes(handler)
    assert "rpc_remote_point" == handler._nvim_rpc_method_name
    assert True == handler._nvim_rpc_sync  # noqa


def test_command_count() -> None:

    def function() -> None:
        """A dummy function to decorate."""
        return

    # ensure absence with default value of None
    decorated = command('test')(function)
    assert 'count' not in decorated._nvim_rpc_spec['opts']
    _ensure_attributes(decorated)

    # ensure absence with explicit value of None
    count_value = None
    decorated = command('test', count=count_value)(function)
    assert 'count' not in decorated._nvim_rpc_spec['opts']

    # Test precedence with value of 0
    count_value = 0
    decorated = command('test', count=count_value)(function)
    assert 'count' in decorated._nvim_rpc_spec['opts']
    assert decorated._nvim_rpc_spec['opts']['count'] == count_value

    # Test presence with value of 1
    count_value = 1
    decorated = command('test', count=count_value)(function)
    assert 'count' in decorated._nvim_rpc_spec['opts']
    assert decorated._nvim_rpc_spec['opts']['count'] == count_value


def test_autocmd() -> None:

    @autocmd(name="BufEnter", pattern="*.py", sync=True)
    def handler(afile):
        print(afile)

    _ensure_attributes(handler)
    assert 'autocmd:BufEnter:*.py' == handler._nvim_rpc_method_name


def test_function() -> None:
    pass

    @function(name="MyRemoteFunction")
    def MyRemoteFunc(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    _ensure_attributes(MyRemoteFunc)
    assert 'function:MyRemoteFunction' == MyRemoteFunc._nvim_rpc_method_name


def test_shutdown_hook() -> None:

    @shutdown_hook
    def hook():
        print("shutdown...")

    _ensure_attributes(hook)
    assert True == hook._nvim_shutdown_hook  # noqa
    assert not hook._nvim_rpc_method_name


def test_decode() -> None:

    # Case 1
    @decode(mode="strict")
    @function(name="MyFunc")
    def handler1():
        """A valid usage."""

    # decode set, and all other attributes are preserved
    assert "function:MyFunc" == handler1._nvim_rpc_method_name
    assert "strict" == handler1._nvim_decode

    # Case 2: decode "inside" function
    @function(name="MyFunc")
    @decode(mode="strict")
    def handler2():
        """Note the swapped order between function and decode."""

    assert "function:MyFunc" == handler2._nvim_rpc_method_name
    assert "strict" == handler2._nvim_decode

    # Case 3: on class
    @decode(mode="strict")
    @plugin
    class MyPlugin:
        pass

    assert "strict" == MyPlugin._nvim_decode
    assert True == MyPlugin._nvim_plugin  # noqa
