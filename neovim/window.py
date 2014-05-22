from util import RemoteMap

class Window(object):
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
    def vars(self):
        if not hasattr(self, '_vars'):
            self._vars = RemoteMap(lambda k: self.get_var(k),
                                   lambda k, v: self.set_var(k, v))
        return self._vars

    @property
    def options(self):
        if not hasattr(self, '_options'):
            self._options = RemoteMap(lambda k: self.get_option(k),
                                      lambda k, v: self.set_option(k, v))
        return self._options

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
