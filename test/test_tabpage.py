def test_windows(vim):
    vim.command('tabnew')
    vim.command('vsplit')
    assert list(vim.tabpages[0].windows) == [vim.windows[0]]
    assert list(vim.tabpages[1].windows) == [vim.windows[1], vim.windows[2]]
    assert vim.tabpages[1].window == vim.windows[1]
    vim.current.window = vim.windows[2]
    assert vim.tabpages[1].window == vim.windows[2]


def test_vars(vim):
    vim.current.tabpage.vars['python'] = [1, 2, {'3': 1}]
    assert vim.current.tabpage.vars['python'] == [1, 2, {'3': 1}]
    assert vim.eval('t:python') == [1, 2, {'3': 1}]


def test_valid(vim):
    vim.command('tabnew')
    tabpage = vim.tabpages[1]
    assert tabpage.valid
    vim.command('tabclose')
    assert not tabpage.valid


def test_number(vim):
    curnum = vim.current.tabpage.number
    vim.command('tabnew')
    assert vim.current.tabpage.number == curnum + 1
    vim.command('tabnew')
    assert vim.current.tabpage.number == curnum + 2


def test_repr(vim):
    assert repr(vim.current.tabpage) == "<Tabpage(handle=2)>"
