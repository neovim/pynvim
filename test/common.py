import json
import os
import sys

import neovim

from nose.tools import eq_ as eq


session = None
vim = None
if 'NVIM_SPAWN_ARGV' in os.environ:
    argv = json.loads(os.environ['NVIM_SPAWN_ARGV'])
    session = neovim.spawn_session(argv)
else:
    session = neovim.socket_session(os.environ['NVIM_LISTEN_ADDRESS'])

vim = neovim.Nvim.from_session(session)

if sys.version_info >= (3, 0):
    # For Python3 we decode binary strings as Unicode for compatibility
    # with Python2
    vim = vim.with_hook(neovim.DecodeHook())


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
