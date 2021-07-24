import pytest

from pynvim.api import Nvim


def test_windows(vim: Nvim) -> None:
    vim.command('tabnew')
    vim.command('vsplit')
    assert list(vim.tabpages[0].windows) == [vim.windows[0]]
    assert list(vim.tabpages[1].windows) == [vim.windows[1], vim.windows[2]]
    assert vim.tabpages[1].window == vim.windows[1]
    vim.current.window = vim.windows[2]
    assert vim.tabpages[1].window == vim.windows[2]


def test_vars(vim: Nvim) -> None:
    vim.current.tabpage.vars['python'] = [1, 2, {'3': 1}]
    assert vim.current.tabpage.vars['python'] == [1, 2, {'3': 1}]
    assert vim.eval('t:python') == [1, 2, {'3': 1}]
    assert vim.current.tabpage.vars.get('python') == [1, 2, {'3': 1}]

    del vim.current.tabpage.vars['python']
    with pytest.raises(KeyError):
        vim.current.tabpage.vars['python']
    assert vim.eval('exists("t:python")') == 0

    with pytest.raises(KeyError):
        del vim.current.tabpage.vars['python']

    assert vim.current.tabpage.vars.get('python', 'default') == 'default'


def test_valid(vim: Nvim) -> None:
    vim.command('tabnew')
    tabpage = vim.tabpages[1]
    assert tabpage.valid
    vim.command('tabclose')
    assert not tabpage.valid


def test_number(vim: Nvim) -> None:
    curnum = vim.current.tabpage.number
    vim.command('tabnew')
    assert vim.current.tabpage.number == curnum + 1
    vim.command('tabnew')
    assert vim.current.tabpage.number == curnum + 2


def test_repr(vim: Nvim) -> None:
    assert repr(vim.current.tabpage) == "<Tabpage(handle=1)>"
