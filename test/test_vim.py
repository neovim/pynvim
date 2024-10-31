"""Tests interaction with neovim via Nvim API (with child process)."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

from pynvim.api import Nvim, NvimError


def source(vim: Nvim, code: str) -> None:
    fd, fname = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as f:
        f.write(code)
    vim.command('source ' + fname)
    os.unlink(fname)


def test_clientinfo(vim: Nvim) -> None:
    assert 'remote' == vim.api.get_chan_info(vim.channel_id)['client']['type']


def test_command(vim: Nvim) -> None:
    fname = tempfile.mkstemp()[1]
    vim.command('new')
    vim.command('edit {}'.format(fname))
    # skip the "press return" state, which does not handle deferred calls
    vim.input('\r')
    vim.command('normal itesting\npython\napi')
    vim.command('w')
    assert os.path.isfile(fname)
    with open(fname) as f:
        assert f.read() == 'testing\npython\napi\n'
    try:
        os.unlink(fname)
    except OSError:
        pass  # on windows, this can be flaky; ignore it


def test_command_output(vim: Nvim) -> None:
    assert vim.command_output('echo "test"') == 'test'

    # can capture multi-line outputs
    vim.command("let g:multiline_string = join(['foo', 'bar'], nr2char(10))")
    assert vim.command_output('echo g:multiline_string') == "foo\nbar"


def test_command_error(vim: Nvim) -> None:
    with pytest.raises(vim.error) as excinfo:
        vim.current.window.cursor = -1, -1
    assert excinfo.value.args == ('Cursor position outside buffer',)


def test_eval(vim: Nvim) -> None:
    vim.command('let g:v1 = "a"')
    vim.command('let g:v2 = [1, 2, {"v3": 3}]')
    g = vim.eval('g:')
    assert g['v1'] == 'a'
    assert g['v2'] == [1, 2, {'v3': 3}]


def test_call(vim: Nvim) -> None:
    assert vim.funcs.join(['first', 'last'], ', ') == 'first, last'
    source(vim, """
        function! Testfun(a,b)
            return string(a:a).":".a:b
        endfunction
    """)
    assert vim.funcs.Testfun(3, 'alpha') == '3:alpha'


def test_api(vim: Nvim) -> None:
    vim.api.command('let g:var = 3')
    assert vim.api.eval('g:var') == 3


def test_strwidth(vim: Nvim) -> None:
    assert vim.strwidth('abc') == 3
    # 6 + (neovim)
    # 19 * 2 (each japanese character occupies two cells)
    assert vim.strwidth('neovimのデザインかなりまともなのになってる。') == 44


def test_chdir(vim: Nvim) -> None:
    pwd = vim.eval('getcwd()')
    root = os.path.abspath(os.sep)
    # We can chdir to '/' on Windows, but then the pwd will be the root drive
    vim.chdir('/')
    assert vim.eval('getcwd()') == root
    vim.chdir(pwd)
    assert vim.eval('getcwd()') == pwd


def test_current_line(vim: Nvim) -> None:
    assert vim.current.line == ''
    vim.current.line = 'abc'
    assert vim.current.line == 'abc'


def test_current_line_delete(vim: Nvim) -> None:
    vim.current.buffer[:] = ['one', 'two']
    assert len(vim.current.buffer[:]) == 2
    del vim.current.line
    assert len(vim.current.buffer[:]) == 1 and vim.current.buffer[0] == 'two'
    del vim.current.line
    assert len(vim.current.buffer[:]) == 1 and not vim.current.buffer[0]


def test_vars(vim: Nvim) -> None:
    vim.vars['python'] = [1, 2, {'3': 1}]
    assert vim.vars['python'] == [1, 2, {'3': 1}]
    assert vim.eval('g:python') == [1, 2, {'3': 1}]
    assert vim.vars.get('python') == [1, 2, {'3': 1}]

    del vim.vars['python']
    with pytest.raises(KeyError):
        vim.vars['python']
    assert vim.eval('exists("g:python")') == 0

    with pytest.raises(KeyError):
        del vim.vars['python']

    assert vim.vars.get('python', 'default') == 'default'


def test_options(vim: Nvim) -> None:
    assert vim.options['background'] == 'dark'
    vim.options['background'] = 'light'
    assert vim.options['background'] == 'light'


def test_local_options(vim: Nvim) -> None:
    assert vim.windows[0].options['foldmethod'] == 'manual'
    vim.windows[0].options['foldmethod'] = 'syntax'
    assert vim.windows[0].options['foldmethod'] == 'syntax'


def test_buffers(vim: Nvim) -> None:
    buffers = []

    # Number of elements
    assert len(vim.buffers) == 1

    # Indexing (by buffer number)
    assert vim.buffers[vim.current.buffer.number] == vim.current.buffer

    buffers.append(vim.current.buffer)
    vim.command('new')
    assert len(vim.buffers) == 2
    buffers.append(vim.current.buffer)
    assert vim.buffers[vim.current.buffer.number] == vim.current.buffer
    vim.current.buffer = buffers[0]
    assert vim.buffers[vim.current.buffer.number] == buffers[0]

    # Membership test
    assert buffers[0] in vim.buffers
    assert buffers[1] in vim.buffers
    assert {} not in vim.buffers  # type: ignore[operator]

    # Iteration
    assert buffers == list(vim.buffers)


def test_windows(vim: Nvim) -> None:
    assert len(vim.windows) == 1
    assert vim.windows[0] == vim.current.window
    vim.command('vsplit')
    vim.command('split')
    assert len(vim.windows) == 3
    assert vim.windows[0] == vim.current.window
    vim.current.window = vim.windows[1]
    assert vim.windows[1] == vim.current.window


def test_tabpages(vim: Nvim) -> None:
    assert len(vim.tabpages) == 1
    assert vim.tabpages[0] == vim.current.tabpage
    vim.command('tabnew')
    assert len(vim.tabpages) == 2
    assert len(vim.windows) == 2
    assert vim.windows[1] == vim.current.window
    assert vim.tabpages[1] == vim.current.tabpage
    vim.current.window = vim.windows[0]
    # Switching window also switches tabpages if necessary(this probably
    # isn't the current behavior, but compatibility will be handled in the
    # python client with an optional parameter)
    assert vim.tabpages[0] == vim.current.tabpage
    assert vim.windows[0] == vim.current.window
    vim.current.tabpage = vim.tabpages[1]
    assert vim.tabpages[1] == vim.current.tabpage
    assert vim.windows[1] == vim.current.window


def test_hash(vim: Nvim) -> None:
    d = {}
    d[vim.current.buffer] = "alpha"
    assert d[vim.current.buffer] == 'alpha'
    vim.command('new')
    d[vim.current.buffer] = "beta"
    assert d[vim.current.buffer] == 'beta'
    vim.command('winc w')
    assert d[vim.current.buffer] == 'alpha'
    vim.command('winc w')
    assert d[vim.current.buffer] == 'beta'


def test_python3(vim: Nvim) -> None:
    """Tests whether python3 host can load."""
    rv = vim.exec_lua('''
        local prog, err = vim.provider.python.detect_by_module("neovim")
        return { prog = prog, err = err }''')
    assert rv['prog'] != "", rv['err']
    assert rv['prog'] == sys.executable

    assert sys.executable == vim.command_output(
        'python3 import sys; print(sys.executable)')

    assert 1 == vim.eval('has("python3")')


def test_python3_ex_eval(vim: Nvim) -> None:
    assert '42' == vim.command_output('python3 =42')
    assert '42' == vim.command_output('python3 =   42     ')
    assert '42' == vim.command_output('py3=    42     ')
    assert '42' == vim.command_output('py=42')

    # On syntax error or evaluation error, stacktrace information is printed
    # Note: the pynvim API command_output() throws an exception on error
    # because the Ex command :python will throw (wrapped with provider#python3#Call)
    with pytest.raises(NvimError) as excinfo:
        vim.command('py3= 1/0')
    stacktrace = excinfo.value.args[0]
    assert 'File "<string>", line 1, in <module>' in stacktrace
    assert 'ZeroDivisionError: division by zero' in stacktrace

    vim.command('python3 def raise_error(): raise RuntimeError("oops")')
    with pytest.raises(NvimError) as excinfo:
        vim.command_output('python3 =print("nooo", raise_error())')
    stacktrace = excinfo.value.args[0]
    assert 'File "<string>", line 1, in raise_error' in stacktrace
    assert 'RuntimeError: oops' in stacktrace
    assert 'nooo' not in vim.command_output(':messages')


def test_python_cwd(vim: Nvim, tmp_path: Path) -> None:
    vim.command('python3 import os')
    cwd_before = vim.command_output('python3 print(os.getcwd())')

    # handle DirChanged #296
    vim.command('cd {}'.format(str(tmp_path)))
    cwd_vim = vim.command_output('pwd')
    cwd_python = vim.command_output('python3 print(os.getcwd())')
    assert cwd_python == cwd_vim
    assert cwd_python != cwd_before


lua_code = """
local a = vim.api
local y = ...
function pynvimtest_func(x)
    return x+y
end

local function setbuf(buf,lines)
   a.nvim_buf_set_lines(buf, 0, -1, true, lines)
end


local function getbuf(buf)
   return a.nvim_buf_line_count(buf)
end

pynvimtest = {setbuf=setbuf, getbuf=getbuf}

return "eggspam"
"""


def test_lua(vim: Nvim) -> None:
    assert vim.exec_lua(lua_code, 7) == "eggspam"
    assert vim.lua.pynvimtest_func(3) == 10
    lua_module = vim.lua.pynvimtest
    buf = vim.current.buffer
    lua_module.setbuf(buf, ["a", "b", "c", "d"], async_=True)
    assert lua_module.getbuf(buf) == 4
