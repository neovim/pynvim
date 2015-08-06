# -*- coding: utf-8 -*-
import os, tempfile
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup

def source(code):
    fd, fname = tempfile.mkstemp()
    with os.fdopen(fd,'w') as f:
        f.write(code)
    vim.command('source '+fname)
    os.unlink(fname)


@with_setup(setup=cleanup)
def test_command():
    fname = tempfile.mkstemp()[1]
    vim.command('new')
    vim.command('edit %s' % fname)
    # skip the "press return" state, which does not handle deferred calls
    vim.input('\r')
    vim.command('normal itesting\npython\napi')
    vim.command('w')
    ok(os.path.isfile(fname))
    eq(open(fname).read(), 'testing\npython\napi\n')
    os.unlink(fname)


@with_setup
def test_command_output():
    eq(vim.command_output('echo test'), 'test')


@with_setup(setup=cleanup)
def test_eval():
    vim.command('let g:v1 = "a"')
    vim.command('let g:v2 = [1, 2, {"v3": 3}]')
    eq(vim.eval('g:'), {'v1': 'a', 'v2': [1, 2, {'v3': 3}]})

@with_setup(setup=cleanup)
def test_call():
    eq(vim.funcs.join(['first', 'last'], ', '), 'first, last')
    source("""
        function! Testfun(a,b)
            return string(a:a).":".a:b
        endfunction
    """)
    eq(vim.funcs.Testfun(3, 'alpha'), '3:alpha')


@with_setup(setup=cleanup)
def test_strwidth():
    eq(vim.strwidth('abc'), 3)
    # 6 + (neovim)
    # 19 * 2 (each japanese character occupies two cells)
    eq(vim.strwidth('neovimのデザインかなりまともなのになってる。'), 44)


@with_setup(setup=cleanup)
def test_list_runtime_paths():
    # Is this the default runtime path list?
    homedir = os.path.join(os.environ['HOME'], '.nvim')
    vimdir = vim.eval('$VIM')
    dflt_rtp = [
        homedir,
        os.path.join(vimdir, 'vimfiles'),
        vimdir,
        os.path.join(vimdir, 'vimfiles', 'after')
    ]
    # If the runtime is installed the default path
    # is nvim/runtime
    dflt_rtp2 = list(dflt_rtp)
    dflt_rtp2[2] = os.path.join(dflt_rtp2[2], 'runtime')

    rtp = vim.list_runtime_paths()
    ok(rtp == dflt_rtp or rtp == dflt_rtp2)


@with_setup(setup=cleanup)
def test_chdir():
    pwd = vim.eval('getcwd()')
    vim.chdir('/')
    eq(vim.eval('getcwd()'), '/')
    vim.chdir(pwd)
    eq(vim.eval('getcwd()'), pwd)


@with_setup(setup=cleanup)
def test_current_line():
    eq(vim.current.line, '')
    vim.current.line = 'abc'
    eq(vim.current.line, 'abc')


@with_setup(setup=cleanup)
def test_vars():
    vim.vars['python'] = [1, 2, {'3': 1}]
    eq(vim.vars['python'], [1, 2, {'3': 1}])
    eq(vim.eval('g:python'), [1, 2, {'3': 1}])


@with_setup(setup=cleanup)
def test_options():
    eq(vim.options['listchars'], 'eol:$')
    vim.options['listchars'] = 'tab:xy'
    eq(vim.options['listchars'], 'tab:xy')


@with_setup(setup=cleanup)
def test_buffers():
    eq(len(vim.buffers), 1)
    eq(vim.buffers[0], vim.current.buffer)
    vim.command('new')
    eq(len(vim.buffers), 2)
    eq(vim.buffers[1], vim.current.buffer)
    vim.current.buffer = vim.buffers[0]
    eq(vim.buffers[0], vim.current.buffer)


@with_setup(setup=cleanup)
def test_windows():
    eq(len(vim.windows), 1)
    eq(vim.windows[0], vim.current.window)
    vim.command('vsplit')
    vim.command('split')
    eq(len(vim.windows), 3)
    eq(vim.windows[0], vim.current.window)
    vim.current.window = vim.windows[1]
    eq(vim.windows[1], vim.current.window)


@with_setup(setup=cleanup)
def test_tabpages():
    eq(len(vim.tabpages), 1)
    eq(vim.tabpages[0], vim.current.tabpage)
    vim.command('tabnew')
    eq(len(vim.tabpages), 2)
    eq(len(vim.windows), 2)
    eq(vim.windows[1], vim.current.window)
    eq(vim.tabpages[1], vim.current.tabpage)
    vim.current.window = vim.windows[0]
    # Switching window also switches tabpages if necessary(this probably
    # isn't the current behavior, but compatibility will be handled in the
    # python client with an optional parameter)
    eq(vim.tabpages[0], vim.current.tabpage)
    eq(vim.windows[0], vim.current.window)
    vim.current.tabpage = vim.tabpages[1]
    eq(vim.tabpages[1], vim.current.tabpage)
    eq(vim.windows[1], vim.current.window)


@with_setup(setup=cleanup)
def test_hash():
    d = {}
    d[vim.current.buffer] = "alpha"
    eq(d[vim.current.buffer], "alpha")
    vim.command('new')
    d[vim.current.buffer] = "beta"
    eq(d[vim.current.buffer], "beta")
    vim.command('winc w')
    eq(d[vim.current.buffer], "alpha")
    vim.command('winc w')
    eq(d[vim.current.buffer], "beta")
