import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup


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


@with_setup(setup=cleanup)
def test_vars():
    vim.current.buffer.vars['python'] = [1, 2, {'3': 1}]
    eq(vim.current.buffer.vars['python'], [1, 2, {'3': 1}])
    eq(vim.eval('b:python'), [1, 2, {'3': 1}])


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
    new_name = vim.eval('tempname()')
    vim.current.buffer.name = new_name
    eq(vim.current.buffer.name, new_name)
    vim.command('w!')
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
    eq(vim.current.buffer[:], ['', 'b', 'a'])
    vim.current.buffer.append(['c', 'd'])
    eq(vim.current.buffer[:], ['', 'b', 'a', 'c', 'd'])
    vim.current.buffer.append(['c', 'd'], 2)
    eq(vim.current.buffer[:], ['', 'b', 'a', 'c', 'd', 'c', 'd'])


@with_setup(setup=cleanup)
def test_mark():
    vim.current.buffer.append(['a', 'bit of', 'text'])
    vim.current.window.cursor = [3, 4]
    vim.command('mark V')
    eq(vim.current.buffer.mark('V'), [3, 0])


@with_setup(setup=cleanup)
def test_get_exceptions():
    try:
        vim.current.buffer.options['invalid-option']
        ok(False)
    except vim.error:
        pass
