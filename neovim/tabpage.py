from .util import RemoteMap, RemoteSequence

class Tabpage(object):
    @classmethod
    def initialize(self, tabpage):
        tabpage.windows = RemoteSequence(tabpage._vim,
                                         lambda: tabpage.get_windows())
        tabpage.vars = RemoteMap(lambda k: tabpage.get_var(k),
                                 lambda k, v: tabpage.set_var(k, v))

    @property
    def number(self):
        return self._handle

    @property
    def window(self):
        return self.get_window()

    @property
    def valid(self):
        return self.is_valid()
