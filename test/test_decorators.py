from neovim.plugin.decorators import autocmd, command, function


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


def test_name_command():
    def newcommand():
        return

    def newCommand():
        return

    def new_command():
        return

    def _new_command():
        return

    decorated = command()(newcommand)
    assert decorated._nvim_rpc_spec['name'] == 'Newcommand'

    decorated = command()(newCommand)
    assert decorated._nvim_rpc_spec['name'] == 'NewCommand'

    decorated = command()(new_command)
    assert decorated._nvim_rpc_spec['name'] == 'NewCommand'

    decorated = command()(_new_command)
    assert decorated._nvim_rpc_spec['name'] == 'NewCommand'


def test_name_function():
    def newfunction():
        return

    def newFunction():
        return

    def new_function():
        return

    def _new_function():
        return

    decorated = function()(newfunction)
    assert decorated._nvim_rpc_spec['name'] == 'Newfunction'

    decorated = function()(newFunction)
    assert decorated._nvim_rpc_spec['name'] == 'NewFunction'

    decorated = function()(new_function)
    assert decorated._nvim_rpc_spec['name'] == 'NewFunction'

    decorated = function()(_new_function)
    assert decorated._nvim_rpc_spec['name'] == 'NewFunction'


def test_name_autocmd():
    def newautocmd():
        return

    def newAutocmd():
        return

    def new_autocmd():
        return

    def _new_autocmd():
        return

    decorated = autocmd()(newautocmd)
    assert decorated._nvim_rpc_spec['name'] == 'Newautocmd'

    decorated = autocmd()(newAutocmd)
    assert decorated._nvim_rpc_spec['name'] == 'NewAutocmd'

    decorated = autocmd()(new_autocmd)
    assert decorated._nvim_rpc_spec['name'] == 'NewAutocmd'

    decorated = autocmd()(_new_autocmd)
    assert decorated._nvim_rpc_spec['name'] == 'NewAutocmd'
