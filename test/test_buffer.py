import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from test_common import vim, cleanup

from neovim.compat import IS_PYTHON3


@with_setup(setup=cleanup)
def test_get_length():
    eq(len(vim.current.buffer), 1)
    vim.current.buffer.append('line')
    eq(len(vim.current.buffer), 2)
    vim.current.buffer.append('line')
    eq(len(vim.current.buffer), 3)
    vim.current.buffer[-1] = None
    eq(len(vim.current.buffer), 2)
    vim.current.buffer[-1] = None
    vim.current.buffer[-1] = None
    # There's always at least one line
    eq(len(vim.current.buffer), 1)


@with_setup(setup=cleanup)
def test_get_set_del_line():
    eq(vim.current.buffer[0], '')
    vim.current.buffer[0] = 'line1'
    eq(vim.current.buffer[0], 'line1')
    vim.current.buffer[0] = 'line2'
    eq(vim.current.buffer[0], 'line2')
    vim.current.buffer[0] = None
    eq(vim.current.buffer[0], '')
    # __delitem__
    vim.current.buffer[:] = ['line1', 'line2', 'line3']
    eq(vim.current.buffer[2], 'line3')
    del vim.current.buffer[0]
    eq(vim.current.buffer[0], 'line2')
    eq(vim.current.buffer[1], 'line3')
    del vim.current.buffer[-1]
    eq(vim.current.buffer[0], 'line2')
    eq(len(vim.current.buffer), 1)


@with_setup(setup=cleanup)
def test_get_set_del_slice():
    eq(vim.current.buffer[:], [''])
    # Replace buffer
    vim.current.buffer[:] = ['a', 'b', 'c']
    eq(vim.current.buffer[:], ['a', 'b', 'c'])
    eq(vim.current.buffer[1:], ['b', 'c'])
    eq(vim.current.buffer[1:2], ['b'])
    eq(vim.current.buffer[1:1], [])
    eq(vim.current.buffer[:-1], ['a', 'b'])
    eq(vim.current.buffer[1:-1], ['b'])
    eq(vim.current.buffer[-2:], ['b', 'c'])
    vim.current.buffer[1:2] = ['a', 'b', 'c']
    eq(vim.current.buffer[:], ['a', 'a', 'b', 'c', 'c'])
    vim.current.buffer[-1:] = ['a', 'b', 'c']
    eq(vim.current.buffer[:], ['a', 'a', 'b', 'c', 'a', 'b', 'c'])
    vim.current.buffer[:-3] = None
    eq(vim.current.buffer[:], ['a', 'b', 'c'])
    vim.current.buffer[:] = None
    eq(vim.current.buffer[:], [''])
    # __delitem__
    vim.current.buffer[:] = ['a', 'b', 'c']
    del vim.current.buffer[:]
    eq(vim.current.buffer[:], [''])
    vim.current.buffer[:] = ['a', 'b', 'c']
    del vim.current.buffer[:1]
    eq(vim.current.buffer[:], ['b', 'c'])
    del vim.current.buffer[:-1]
    eq(vim.current.buffer[:], ['c'])


@with_setup(setup=cleanup)
def test_vars():
    vim.current.buffer.vars['python'] = [1, 2, {'3': 1}]
    eq(vim.current.buffer.vars['python'], [1, 2, {'3': 1}])
    eq(vim.eval('b:python'), [1, 2, {'3': 1}])


@with_setup(setup=cleanup)
def test_api():
    vim.current.buffer.api.set_var('myvar', 'thetext')
    eq(vim.current.buffer.api.get_var('myvar'), 'thetext')
    eq(vim.eval('b:myvar'), 'thetext')
    vim.current.buffer.api.set_lines(0,-1,True,['alpha', 'beta'])
    eq(vim.current.buffer.api.get_lines(0,-1,True), ['alpha', 'beta'])
    eq(vim.current.buffer[:], ['alpha', 'beta'])


@with_setup(setup=cleanup)
def test_options():
    eq(vim.current.buffer.options['shiftwidth'], 8)
    vim.current.buffer.options['shiftwidth'] = 4
    eq(vim.current.buffer.options['shiftwidth'], 4)
    # global-local option
    vim.current.buffer.options['define'] = 'test'
    eq(vim.current.buffer.options['define'], 'test')
    # Doesn't change the global value
    eq(vim.options['define'], '^\s*#\s*define')


@with_setup(setup=cleanup)
def test_number():
    curnum = vim.current.buffer.number
    vim.command('new')
    eq(vim.current.buffer.number, curnum + 1)
    vim.command('new')
    eq(vim.current.buffer.number, curnum + 2)


@with_setup(setup=cleanup)
def test_name():
    vim.command('new')
    eq(vim.current.buffer.name, '')
    new_name = vim.eval('resolve(tempname())')
    vim.current.buffer.name = new_name
    eq(vim.current.buffer.name, new_name)
    vim.command('silent w!')
    ok(os.path.isfile(new_name))
    os.unlink(new_name)


@with_setup(setup=cleanup)
def test_valid():
    vim.command('new')
    buffer = vim.current.buffer
    ok(buffer.valid)
    vim.command('bw!')
    ok(not buffer.valid)


@with_setup(setup=cleanup)
def test_append():
    vim.current.buffer.append('a')
    eq(vim.current.buffer[:], ['', 'a'])
    vim.current.buffer.append('b', 0)
    eq(vim.current.buffer[:], ['b', '', 'a'])
    vim.current.buffer.append(['c', 'd'])
    eq(vim.current.buffer[:], ['b', '', 'a', 'c', 'd'])
    vim.current.buffer.append(['c', 'd'], 2)
    eq(vim.current.buffer[:], ['b', '', 'c', 'd', 'a', 'c', 'd'])
    vim.current.buffer.append(b'bytes')
    eq(vim.current.buffer[:], ['b', '', 'c', 'd', 'a', 'c', 'd', 'bytes'])


@with_setup(setup=cleanup)
def test_mark():
    vim.current.buffer.append(['a', 'bit of', 'text'])
    vim.current.window.cursor = [3, 4]
    vim.command('mark V')
    eq(vim.current.buffer.mark('V'), [3, 0])

@with_setup(setup=cleanup)
def test_invalid_utf8():
    vim.command('normal "=printf("%c", 0xFF)\np')
    eq(vim.eval("char2nr(getline(1))"), 0xFF)

    eq(vim.current.buffer[:], ['\udcff'] if IS_PYTHON3 else ['\xff'])
    vim.current.line += 'x'
    eq(vim.eval("getline(1)", decode=False), b'\xFFx')
    eq(vim.current.buffer[:], ['\udcffx'] if IS_PYTHON3 else ['\xffx'])

@with_setup(setup=cleanup)
def test_get_exceptions():
    try:
        vim.current.buffer.options['invalid-option']
        ok(False)
    except vim.error:
        pass

@with_setup(setup=cleanup)
def test_contains():
    ok(vim.current.buffer in vim.buffers)

@with_setup(setup=cleanup)
def test_set_items_for_range():
    vim.current.buffer[:] = ['a', 'b', 'c', 'd', 'e']
    r = vim.current.buffer.range(1, 3)
    r[1:3] = ['foo']*3
    eq(vim.current.buffer[:], ['a', 'foo', 'foo', 'foo', 'd', 'e'])
