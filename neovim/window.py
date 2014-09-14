from .util import RemoteMap

class Window(object):
    @classmethod
    def initialize(self, window):
        window.vars = RemoteMap(lambda k: window.get_var(k),
                                lambda k, v: window.set_var(k, v))
        window.options = RemoteMap(lambda k: window.get_option(k),
                                   lambda k, v: window.set_option(k, v))

    @property
    def buffer(self):
        return self.get_buffer()

    @property
    def cursor(self):
        return self.get_cursor()

    @cursor.setter
    def cursor(self, pos):
        self.set_cursor(pos)

    @property
    def height(self):
        return self.get_height()

    @height.setter
    def height(self, height):
        self.set_height(height)

    @property
    def width(self):
        return self.get_width()

    @width.setter
    def width(self, width):
        self.set_width(width)

    @property
    def number(self):
        return self._handle

    @property
    def row(self):
        return self.get_position()[0]

    @property
    def col(self):
        return self.get_position()[1]

    @property
    def tabpage(self):
        return self.get_tabpage()

    @property
    def valid(self):
        return self.is_valid()
