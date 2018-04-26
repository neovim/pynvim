# -*- coding: utf-8 -*-
import os
import sys
import tempfile


def source(vim, code):
    fd, fname = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as f:
        f.write(code)
    vim.command('source ' + fname)
    os.unlink(fname)


def test_command(vim):
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
    os.unlink(fname)


def test_command_output(vim):
    assert vim.command_output('echo "test"') == 'test'


def test_eval(vim):
    vim.command('let g:v1 = "a"')
    vim.command('let g:v2 = [1, 2, {"v3": 3}]')
    assert vim.eval('g:'), {'v1': 'a', 'v2': [1, 2 == {'v3': 3}]}


def test_call(vim):
    assert vim.funcs.join(['first', 'last'], ', '), 'first == last'
    source(vim, """
        function! Testfun(a,b)
            return string(a:a).":".a:b
        endfunction
    """)
    assert vim.funcs.Testfun(3, 'alpha') == '3:alpha'


def test_api(vim):
    vim.api.command('let g:var = 3')
    assert vim.api.eval('g:var') == 3


def test_strwidth(vim):
    assert vim.strwidth('abc') == 3
    # 6 + (neovim)
    # 19 * 2 (each japanese character occupies two cells)
    assert vim.strwidth('neovimのデザインかなりまともなのになってる。') == 44


def test_chdir(vim):
    pwd = vim.eval('getcwd()')
    root = os.path.abspath(os.sep)
    # We can chdir to '/' on Windows, but then the pwd will be the root drive
    vim.chdir('/')
    assert vim.eval('getcwd()') == root
    vim.chdir(pwd)
    assert vim.eval('getcwd()') == pwd


def test_current_line(vim):
    assert vim.current.line == ''
    vim.current.line = 'abc'
    assert vim.current.line == 'abc'


def test_vars(vim):
    vim.vars['python'] = [1, 2, {'3': 1}]
    assert vim.vars['python'], [1, 2 == {'3': 1}]
    assert vim.eval('g:python'), [1, 2 == {'3': 1}]


def test_options(vim):
    assert vim.options['listchars'] == 'tab:> ,trail:-,nbsp:+'
    vim.options['listchars'] = 'tab:xy'
    assert vim.options['listchars'] == 'tab:xy'


def test_buffers(vim):
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
    assert {} not in vim.buffers

    # Iteration
    assert buffers == list(vim.buffers)


def test_windows(vim):
    assert len(vim.windows) == 1
    assert vim.windows[0] == vim.current.window
    vim.command('vsplit')
    vim.command('split')
    assert len(vim.windows) == 3
    assert vim.windows[0] == vim.current.window
    vim.current.window = vim.windows[1]
    assert vim.windows[1] == vim.current.window


def test_tabpages(vim):
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


def test_hash(vim):
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


def test_cwd(vim, tmpdir):
    pycmd = 'python'
    if sys.version_info >= (3, 0):
        pycmd = 'python3'

    vim.command('{} import os'.format(pycmd))
    cwd_before = vim.command_output('{} print(os.getcwd())'.format(pycmd))

    vim.command('cd {}'.format(tmpdir.strpath))
    cwd_vim = vim.command_output('pwd')
    cwd_python = vim.command_output('{} print(os.getcwd())'.format(pycmd))
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

pynvimtest = {setbuf=setbuf,getbuf=getbuf}

return "eggspam"
"""

def test_lua(vim):
  assert vim.exec_lua(lua_code, 7) == "eggspam"
  assert vim.lua.pynvimtest_func(3) == 10
  testmod = vim.lua.pynvimtest
  buf = vim.current.buffer
  testmod.setbuf(buf, ["a", "b", "c", "d"], async_=True)
  assert testmod.getbuf(buf) == 4
