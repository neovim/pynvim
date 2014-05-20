from util import RemoteMap, RemoteSequence

class Tabpage(object):
    @property
    def windows(self):
        if not hasattr(self, '_windows'):
            self._windows = RemoteSequence(self,
                                           self._vim.Window,
                                           lambda: self.get_windows())
        return self._windows

    @property
    def vars(self):
        if not hasattr(self, '_vars'):
            self._vars = RemoteMap(lambda k: self.get_var(k),
                                   lambda k, v: self.set_var(k, v))
        return self._vars

    @property
    def number(self):
        return self._handle

    @property
    def window(self):
        return self.get_window()

    @property
    def valid(self):
        return self.is_valid()
