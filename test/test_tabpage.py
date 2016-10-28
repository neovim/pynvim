import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from test_common import vim, cleanup


@with_setup(setup=cleanup)
def test_windows():
    vim.command('tabnew')
    vim.command('vsplit')
    eq(list(vim.tabpages[0].windows), [vim.windows[0]])
    eq(list(vim.tabpages[1].windows), [vim.windows[1], vim.windows[2]])
    eq(vim.tabpages[1].window, vim.windows[1])
    vim.current.window = vim.windows[2]
    eq(vim.tabpages[1].window, vim.windows[2])


@with_setup(setup=cleanup)
def test_vars():
    vim.current.tabpage.vars['python'] = [1, 2, {'3': 1}]
    eq(vim.current.tabpage.vars['python'], [1, 2, {'3': 1}])
    eq(vim.eval('t:python'), [1, 2, {'3': 1}])


@with_setup(setup=cleanup)
def test_valid():
    vim.command('tabnew')
    tabpage = vim.tabpages[1]
    ok(tabpage.valid)
    vim.command('tabclose')
    ok(not tabpage.valid)


@with_setup(setup=cleanup)
def test_number():
    curnum = vim.current.tabpage.number
    vim.command('tabnew')
    eq(vim.current.tabpage.number, curnum + 1)
    vim.command('tabnew')
    eq(vim.current.tabpage.number, curnum + 2)
