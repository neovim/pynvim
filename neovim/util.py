class RemoteSequence(object):
    # TODO Need to add better support for this class on the server
    def __init__(self, vim, fetch_fn):
        self._fetch_fn = fetch_fn

    def __len__(self):
        return len(self._fetch_fn())

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            return self._fetch_fn()[idx]
        return self._fetch_fn()[idx.start:idx.stop]

    def __iter__(self):
        items = self._fetch_fn()
        for item in items:
            yield item
    
    def __contains__(self, item):
        for i in self._fetch_fn():
            if i._handle == item._handle:
                return True
        return False


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

def decode_obj(obj, encoding=None, encoding_errors='strict'):
    """
    Recursively decode instances of 'bytes' into Unicode
    """
    if not encoding:
        return obj

    if isinstance(obj, bytes):
        return obj.decode(encoding, errors=encoding_errors)
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [decode_obj(o, encoding, encoding_errors) for o in obj]
    elif isinstance(obj, dict):
        d = {}
        for k,v in obj.items():
            k = decode_obj(k, encoding, encoding_errors)
            v = decode_obj(v, encoding, encoding_errors)
            d[k] = v
        return d
    return obj


