from . import vim, buffer, window, tabpage


__all__ = ['mixins']


mixins = {
    'vim': vim.Vim,
    'buffer': buffer.Buffer,
    'window': window.Window,
    'tabpage': tabpage.Tabpage
}
