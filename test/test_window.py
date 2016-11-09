import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from test_common import vim, cleanup


@with_setup(setup=cleanup)
def test_buffer():
    eq(vim.current.buffer, vim.windows[0].buffer)
    vim.command('new')
    vim.current.window = vim.windows[1]
    eq(vim.current.buffer, vim.windows[1].buffer)
    ok(vim.windows[0].buffer != vim.windows[1].buffer)


@with_setup(setup=cleanup)
def test_cursor():
    eq(vim.current.window.cursor, [1, 0])
    vim.command('normal ityping\033o  some text')
    eq(vim.current.buffer[:], ['typing', '  some text'])
    eq(vim.current.window.cursor, [2, 10])
    vim.current.window.cursor = [2, 6]
    vim.command('normal i dumb')
    eq(vim.current.buffer[:], ['typing', '  some dumb text'])


@with_setup(setup=cleanup)
def test_height():
    vim.command('vsplit')
    eq(vim.windows[1].height, vim.windows[0].height)
    vim.current.window = vim.windows[1]
    vim.command('split')
    eq(vim.windows[1].height, vim.windows[0].height // 2)
    vim.windows[1].height = 2
    eq(vim.windows[1].height, 2)


@with_setup(setup=cleanup)
def test_width():
    vim.command('split')
    eq(vim.windows[1].width, vim.windows[0].width)
    vim.current.window = vim.windows[1]
    vim.command('vsplit')
    eq(vim.windows[1].width, vim.windows[0].width // 2)
    vim.windows[1].width = 2
    eq(vim.windows[1].width, 2)


@with_setup(setup=cleanup)
def test_vars():
    vim.current.window.vars['python'] = [1, 2, {'3': 1}]
    eq(vim.current.window.vars['python'], [1, 2, {'3': 1}])
    eq(vim.eval('w:python'), [1, 2, {'3': 1}])


@with_setup(setup=cleanup)
def test_options():
    vim.current.window.options['colorcolumn'] = '4,3'
    eq(vim.current.window.options['colorcolumn'], '4,3')
    # global-local option
    vim.current.window.options['statusline'] = 'window-status'
    eq(vim.current.window.options['statusline'], 'window-status')
    eq(vim.options['statusline'], '')


@with_setup(setup=cleanup)
def test_position():
    height = vim.windows[0].height
    width = vim.windows[0].width
    vim.command('split')
    vim.command('vsplit')
    eq((vim.windows[0].row, vim.windows[0].col), (0, 0))
    vsplit_pos = width / 2
    split_pos = height / 2
    eq(vim.windows[1].row, 0)
    ok(vsplit_pos - 1 <= vim.windows[1].col <= vsplit_pos + 1)
    ok(split_pos - 1 <= vim.windows[2].row <= split_pos + 1)
    eq(vim.windows[2].col, 0)


@with_setup(setup=cleanup)
def test_tabpage():
    vim.command('tabnew')
    vim.command('vsplit')
    eq(vim.windows[0].tabpage, vim.tabpages[0])
    eq(vim.windows[1].tabpage, vim.tabpages[1])
    eq(vim.windows[2].tabpage, vim.tabpages[1])


@with_setup(setup=cleanup)
def test_valid():
    vim.command('split')
    window = vim.windows[1]
    vim.current.window = window
    ok(window.valid)
    vim.command('q')
    ok(not window.valid)


@with_setup(setup=cleanup)
def test_number():
    curnum = vim.current.window.number
    vim.command('bot split')
    eq(vim.current.window.number, curnum + 1)
    vim.command('bot split')
    eq(vim.current.window.number, curnum + 2)


@with_setup(setup=cleanup)
def test_handle():
    hnd1 = vim.current.window.handle
    vim.command('bot split')
    hnd2 = vim.current.window.handle
    ok(hnd2 != hnd1)
    vim.command('bot split')
    hnd3 = vim.current.window.handle
    ok(hnd3 != hnd1)
    ok(hnd3 != hnd2)
    vim.command('wincmd w')
    eq(vim.current.window.handle,hnd1)
