class RemoteSequence(object):
    # TODO Need to add better support for this class on the server
    def __init__(self, vim, remote_klass, handle_array_fn):
        def wrap(handle):
            rv = remote_klass(vim, handle)
            remote_klass.initialize(rv)
            return rv

        self._wrap_fn = wrap
        self._handle_array_fn = handle_array_fn

    def __len__(self):
        return len(self._handle_array_fn())

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            return self._wrap_fn(self._handle_array_fn()[idx])
        return map(self._wrap_fn, self._handle_array_fn()[idx.start:idx.stop])

    def __iter__(self):
        handles = self._handle_array_fn()
        for handle in handles:
            yield self._wrap_fn(handle)
    
    def __contains__(self, item):
        return item._handle in self._handle_array_fn()


class RemoteMap(object):
    def __init__(self, get_fn, set_fn):
        self._get_fn = get_fn
        self._set_fn = set_fn

    def __getitem__(self, key):
        return self._get_fn(key)

    def __setitem__(self, key, value):
        if not self._set_fn:
            raise TypeError('This dict is read-only')
        self._set_fn(key, value)

    def __delitem__(self, key):
        if not self._set_fn:
            raise TypeError('This dict is read-only')
        return self._set_fn(key, None)

    def __contains__(self, key):
        try:
            self._get_fn(key)
            return True
        except:
            return False


class Current(object):
    def __init__(self, vim):
        self._vim = vim

    @property
    def line(self):
        return self._vim.get_current_line()

    @line.setter
    def line(self, line):
        self._vim.set_current_line(line)

    @property
    def buffer(self):
        return self._vim.get_current_buffer()

    @buffer.setter
    def buffer(self, buffer):
        self._vim.set_current_buffer(buffer)

    @property
    def window(self):
        return self._vim.get_current_window()

    @window.setter
    def window(self, window):
        self._vim.set_current_window(window)

    @property
    def tabpage(self):
        return self._vim.get_current_tabpage()

    @tabpage.setter
    def tabpage(self, tabpage):
        self._vim.set_current_tabpage(tabpage)


class VimExit(IOError):
    pass

class VimError(Exception):
    pass
