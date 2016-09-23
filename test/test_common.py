import json
import os
import sys

import neovim

from nose.tools import eq_ as eq

neovim.setup_logging("test")

child_argv = os.environ.get('NVIM_CHILD_ARGV')
listen_address = os.environ.get('NVIM_LISTEN_ADDRESS')
if child_argv is None and listen_address is None:
    child_argv = '["nvim", "-u", "NONE", "--embed"]'

if child_argv is not None:
    vim = neovim.attach('child', argv=json.loads(child_argv))
else:
    vim = neovim.attach('socket', path=listen_address)

cleanup_func = ''':function BeforeEachTest()
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
'''

vim.input(cleanup_func)


def cleanup():
    # cleanup nvim
    vim.command('call BeforeEachTest()')
    eq(len(vim.tabpages), 1)
    eq(len(vim.windows), 1)
    eq(len(vim.buffers), 1)
