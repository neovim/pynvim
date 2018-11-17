from pynvim.plugin.decorators import command


def test_command_count():
    def function():
        "A dummy function to decorate."
        return

    # ensure absence with default value of None
    decorated = command('test')(function)
    assert 'count' not in decorated._nvim_rpc_spec['opts']

    # ensure absence with explicit value of None
    count_value = None
    decorated = command('test', count=count_value)(function)
    assert 'count' not in decorated._nvim_rpc_spec['opts']

    # Test presesence with value of 0
    count_value = 0
    decorated = command('test', count=count_value)(function)
    assert 'count' in decorated._nvim_rpc_spec['opts']
    assert decorated._nvim_rpc_spec['opts']['count'] == count_value

    # Test presence with value of 1
    count_value = 1
    decorated = command('test', count=count_value)(function)
    assert 'count' in decorated._nvim_rpc_spec['opts']
    assert decorated._nvim_rpc_spec['opts']['count'] == count_value
