import os

from pynvim.compat import IS_PYTHON3


def test_repr(vim):
    assert repr(vim.current.buffer) == "<Buffer(handle=2)>"


def test_get_length(vim):
    assert len(vim.current.buffer) == 1
    vim.current.buffer.append('line')
    assert len(vim.current.buffer) == 2
    vim.current.buffer.append('line')
    assert len(vim.current.buffer) == 3
    vim.current.buffer[-1] = None
    assert len(vim.current.buffer) == 2
    vim.current.buffer[-1] = None
    vim.current.buffer[-1] = None
    # There's always at least one line
    assert len(vim.current.buffer) == 1


def test_get_set_del_line(vim):
    assert vim.current.buffer[0] == ''
    vim.current.buffer[0] = 'line1'
    assert vim.current.buffer[0] == 'line1'
    vim.current.buffer[0] = 'line2'
    assert vim.current.buffer[0] == 'line2'
    vim.current.buffer[0] = None
    assert vim.current.buffer[0] == ''
    # __delitem__
    vim.current.buffer[:] = ['line1', 'line2', 'line3']
    assert vim.current.buffer[2] == 'line3'
    del vim.current.buffer[0]
    assert vim.current.buffer[0] == 'line2'
    assert vim.current.buffer[1] == 'line3'
    del vim.current.buffer[-1]
    assert vim.current.buffer[0] == 'line2'
    assert len(vim.current.buffer) == 1


def test_get_set_del_slice(vim):
    assert vim.current.buffer[:] == ['']
    # Replace buffer
    vim.current.buffer[:] = ['a', 'b', 'c']
    assert vim.current.buffer[:] == ['a', 'b', 'c']
    assert vim.current.buffer[1:] == ['b', 'c']
    assert vim.current.buffer[1:2] == ['b']
    assert vim.current.buffer[1:1] == []
    assert vim.current.buffer[:-1] == ['a', 'b']
    assert vim.current.buffer[1:-1] == ['b']
    assert vim.current.buffer[-2:] == ['b', 'c']
    vim.current.buffer[1:2] = ['a', 'b', 'c']
    assert vim.current.buffer[:] == ['a', 'a', 'b', 'c', 'c']
    vim.current.buffer[-1:] = ['a', 'b', 'c']
    assert vim.current.buffer[:] == ['a', 'a', 'b', 'c', 'a', 'b', 'c']
    vim.current.buffer[:-3] = None
    assert vim.current.buffer[:] == ['a', 'b', 'c']
    vim.current.buffer[:] = None
    assert vim.current.buffer[:] == ['']
    # __delitem__
    vim.current.buffer[:] = ['a', 'b', 'c']
    del vim.current.buffer[:]
    assert vim.current.buffer[:] == ['']
    vim.current.buffer[:] = ['a', 'b', 'c']
    del vim.current.buffer[:1]
    assert vim.current.buffer[:] == ['b', 'c']
    del vim.current.buffer[:-1]
    assert vim.current.buffer[:] == ['c']


def test_vars(vim):
    vim.current.buffer.vars['python'] = [1, 2, {'3': 1}]
    assert vim.current.buffer.vars['python'] == [1, 2, {'3': 1}]
    assert vim.eval('b:python') == [1, 2, {'3': 1}]


def test_api(vim):
    vim.current.buffer.api.set_var('myvar', 'thetext')
    assert vim.current.buffer.api.get_var('myvar') == 'thetext'
    assert vim.eval('b:myvar') == 'thetext'
    vim.current.buffer.api.set_lines(0, -1, True, ['alpha', 'beta'])
    assert vim.current.buffer.api.get_lines(0, -1, True) == ['alpha', 'beta']
    assert vim.current.buffer[:] == ['alpha', 'beta']


def test_options(vim):
    assert vim.current.buffer.options['shiftwidth'] == 8
    vim.current.buffer.options['shiftwidth'] = 4
    assert vim.current.buffer.options['shiftwidth'] == 4
    # global-local option
    vim.current.buffer.options['define'] = 'test'
    assert vim.current.buffer.options['define'] == 'test'
    # Doesn't change the global value
    assert vim.options['define'] == '^\s*#\s*define'


def test_number(vim):
    curnum = vim.current.buffer.number
    vim.command('new')
    assert vim.current.buffer.number == curnum + 1
    vim.command('new')
    assert vim.current.buffer.number == curnum + 2


def test_name(vim):
    vim.command('new')
    assert vim.current.buffer.name == ''
    new_name = vim.eval('resolve(tempname())')
    vim.current.buffer.name = new_name
    assert vim.current.buffer.name == new_name
    vim.command('silent w!')
    assert os.path.isfile(new_name)
    os.unlink(new_name)


def test_valid(vim):
    vim.command('new')
    buffer = vim.current.buffer
    assert buffer.valid
    vim.command('bw!')
    assert not buffer.valid


def test_append(vim):
    vim.current.buffer.append('a')
    assert vim.current.buffer[:] == ['', 'a']
    vim.current.buffer.append('b', 0)
    assert vim.current.buffer[:] == ['b', '', 'a']
    vim.current.buffer.append(['c', 'd'])
    assert vim.current.buffer[:] == ['b', '', 'a', 'c', 'd']
    vim.current.buffer.append(['c', 'd'], 2)
    assert vim.current.buffer[:] == ['b', '', 'c', 'd', 'a', 'c', 'd']
    vim.current.buffer.append(b'bytes')
    assert vim.current.buffer[:] == ['b', '', 'c', 'd', 'a', 'c', 'd', 'bytes']


def test_mark(vim):
    vim.current.buffer.append(['a', 'bit of', 'text'])
    vim.current.window.cursor = [3, 4]
    vim.command('mark V')
    assert vim.current.buffer.mark('V') == [3, 0]


def test_invalid_utf8(vim):
    vim.command('normal "=printf("%c", 0xFF)\np')
    assert vim.eval("char2nr(getline(1))") == 0xFF

    assert vim.current.buffer[:] == ['\udcff'] if IS_PYTHON3 else ['\xff']
    vim.current.line += 'x'
    assert vim.eval("getline(1)", decode=False) == b'\xFFx'
    assert vim.current.buffer[:] == ['\udcffx'] if IS_PYTHON3 else ['\xffx']


def test_get_exceptions(vim):
    try:
        vim.current.buffer.options['invalid-option']
        assert False
    except vim.error:
        pass

def test_set_items_for_range(vim):
    vim.current.buffer[:] = ['a', 'b', 'c', 'd', 'e']
    r = vim.current.buffer.range(1, 3)
    r[1:3] = ['foo']*3
    assert vim.current.buffer[:] == ['a', 'foo', 'foo', 'foo', 'd', 'e']

# NB: we can't easily test the effect of this. But at least run the lua
# function sync, so we know it runs without runtime error with simple args.
def test_update_highlights(vim):
    vim.current.buffer[:] = ['a', 'b', 'c']
    src_id = vim.new_highlight_source()
    vim.current.buffer.update_highlights(src_id, [["Comment", 0, 0, -1], ("String", 1, 0, 1)], clear=True, async_=False)
