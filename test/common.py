from nose.tools import eq_ as eq
import neovim, os, json

vim = None
if 'NEOVIM_SPAWN_ARGV' in os.environ:
    vim = neovim.spawn(json.loads(os.environ['NEOVIM_SPAWN_ARGV']))

if not vim:
    vim = neovim.connect(os.environ['NEOVIM_LISTEN_ADDRESS'])

cleanup_func = ''':function BeforeEachTest()
  set all&
  let &initpython = 'python -c "import neovim; neovim.start_host()"'
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

vim.feedkeys(cleanup_func, '')

def cleanup():
    # cleanup nvim
    vim.command('call BeforeEachTest()')
    vim.command('python import vim')
    eq(len(vim.tabpages), 1)
    eq(len(vim.windows), 1)
    eq(len(vim.buffers), 1)
