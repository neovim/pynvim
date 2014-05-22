from nose.tools import eq_ as eq
import neovim, os

vim = neovim.connect(os.environ['NEOVIM_LISTEN_ADDRESS'])

def cleanup():
    # cleanup nvim
    vim.command('call BeforeEachTest()')
    eq(len(vim.tabpages), 1)
    eq(len(vim.windows), 1)
    eq(len(vim.buffers), 1)
