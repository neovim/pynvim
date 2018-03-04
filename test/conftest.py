import json
import os
import textwrap

import pynvim
import pytest

pynvim.setup_logging("test")


@pytest.fixture(autouse=True)
def cleanup_func(vim):
    fun = textwrap.dedent('''function! BeforeEachTest()
        set all&
        redir => groups
        silent augroup
        redir END
        for group in split(groups)
            exe 'augroup '.group
            autocmd!
            augroup END
        endfor
        autocmd!
        tabnew
        let curbufnum = eval(bufnr('%'))
        redir => buflist
        silent ls!
        redir END
        let bufnums = []
        for buf in split(buflist, '\\n')
            let bufnum = eval(split(buf, '[ u]')[0])
            if bufnum != curbufnum
            call add(bufnums, bufnum)
            endif
        endfor
        if len(bufnums) > 0
            exe 'silent bwipeout! '.join(bufnums, ' ')
        endif
        silent tabonly
        for k in keys(g:)
            exe 'unlet g:'.k
        endfor
        filetype plugin indent off
        mapclear
        mapclear!
        abclear
        comclear
        endfunction
    ''')
    vim.command(fun)
    vim.command('call BeforeEachTest()')
    assert len(vim.tabpages) == len(vim.windows) == len(vim.buffers) == 1


@pytest.fixture
def vim():
    child_argv = os.environ.get('NVIM_CHILD_ARGV')
    listen_address = os.environ.get('NVIM_LISTEN_ADDRESS')
    if child_argv is None and listen_address is None:
        child_argv = '["nvim", "-u", "NONE", "--embed"]'

    if child_argv is not None:
        editor = pynvim.attach('child', argv=json.loads(child_argv))
    else:
        editor = pynvim.attach('socket', path=listen_address)

    return editor
