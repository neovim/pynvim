def test_buffer(vim):
    assert vim.current.buffer == vim.windows[0].buffer
    vim.command('new')
    vim.current.window = vim.windows[1]
    assert vim.current.buffer == vim.windows[1].buffer
    assert vim.windows[0].buffer != vim.windows[1].buffer


def test_cursor(vim):
    assert vim.current.window.cursor == [1, 0]
    vim.command('normal ityping\033o  some text')
    assert vim.current.buffer[:] == ['typing', '  some text']
    assert vim.current.window.cursor == [2, 10]
    vim.current.window.cursor = [2, 6]
    vim.command('normal i dumb')
    assert vim.current.buffer[:] == ['typing', '  some dumb text']


def test_height(vim):
    vim.command('vsplit')
    assert vim.windows[1].height == vim.windows[0].height
    vim.current.window = vim.windows[1]
    vim.command('split')
    assert vim.windows[1].height == vim.windows[0].height // 2
    vim.windows[1].height = 2
    assert vim.windows[1].height == 2


def test_width(vim):
    vim.command('split')
    assert vim.windows[1].width == vim.windows[0].width
    vim.current.window = vim.windows[1]
    vim.command('vsplit')
    assert vim.windows[1].width == vim.windows[0].width // 2
    vim.windows[1].width = 2
    assert vim.windows[1].width == 2


def test_vars(vim):
    vim.current.window.vars['python'] = [1, 2, {'3': 1}]
    assert vim.current.window.vars['python'] == [1, 2, {'3': 1}]
    assert vim.eval('w:python') == [1, 2, {'3': 1}]


def test_options(vim):
    vim.current.window.options['colorcolumn'] = '4,3'
    assert vim.current.window.options['colorcolumn'] == '4,3'
    # global-local option
    vim.current.window.options['statusline'] = 'window-status'
    assert vim.current.window.options['statusline'] == 'window-status'
    assert vim.options['statusline'] == ''


def test_position(vim):
    height = vim.windows[0].height
    width = vim.windows[0].width
    vim.command('split')
    vim.command('vsplit')
    assert (vim.windows[0].row, vim.windows[0].col) == (0, 0)
    vsplit_pos = width / 2
    split_pos = height / 2
    assert vim.windows[1].row == 0
    assert vsplit_pos - 1 <= vim.windows[1].col <= vsplit_pos + 1
    assert split_pos - 1 <= vim.windows[2].row <= split_pos + 1
    assert vim.windows[2].col == 0


def test_tabpage(vim):
    vim.command('tabnew')
    vim.command('vsplit')
    assert vim.windows[0].tabpage == vim.tabpages[0]
    assert vim.windows[1].tabpage == vim.tabpages[1]
    assert vim.windows[2].tabpage == vim.tabpages[1]


def test_valid(vim):
    vim.command('split')
    window = vim.windows[1]
    vim.current.window = window
    assert window.valid
    vim.command('q')
    assert not window.valid


def test_number(vim):
    curnum = vim.current.window.number
    vim.command('bot split')
    assert vim.current.window.number == curnum + 1
    vim.command('bot split')
    assert vim.current.window.number == curnum + 2


def test_handle(vim):
    hnd1 = vim.current.window.handle
    vim.command('bot split')
    hnd2 = vim.current.window.handle
    assert hnd2 != hnd1
    vim.command('bot split')
    hnd3 = vim.current.window.handle
    assert hnd1 != hnd2 != hnd3
    vim.command('wincmd w')
    assert vim.current.window.handle == hnd1


def test_repr(vim):
    assert repr(vim.current.window) == "<Window(handle=1001)>"
