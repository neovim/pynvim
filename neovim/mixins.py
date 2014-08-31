# -*- coding: utf-8 -*-
from . import vim
from . import buffer
from . import window
from . import tabpage


__all__ = ['mixins']


mixins = {
    'vim': vim.Vim,
    'buffer': buffer.Buffer,
    'window': window.Window,
    'tabpage': tabpage.Tabpage
}
