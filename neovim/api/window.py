"""API for working with Nvim windows."""
from .common import Remote, RemoteMap


__all__ = ('Window')


class Window(Remote):

    """A remote Nvim window."""

    def __init__(self, session, code_data):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Window equality to work.
        """
        self._session = session
        self.code_data = code_data
        self.vars = RemoteMap(session, 'window_get_var', 'window_set_var',
                              self)
        self.options = RemoteMap(session, 'window_get_option',
                                 'window_set_option', self)

    @property
    def buffer(self):
        """Get the `Buffer` currently being displayed by the window."""
        return self._session.request('window_get_buffer', self)

    @property
    def cursor(self):
        """Get the (row, col) tuple with the current cursor position."""
        return self._session.request('window_get_cursor', self)

    @cursor.setter
    def cursor(self, pos):
        """Set the (row, col) tuple as the new cursor position."""
        return self._session.request('window_set_cursor', self, pos)

    @property
    def height(self):
        """Get the window height in rows."""
        return self._session.request('window_get_height', self)

    @height.setter
    def height(self, height):
        """Set the window height in rows."""
        return self._session.request('window_set_height', self, height)

    @property
    def width(self):
        """Get the window width in rows."""
        return self._session.request('window_get_width', self)

    @width.setter
    def width(self, width):
        """Set the window height in rows."""
        return self._session.request('window_set_width', self, width)

    @property
    def row(self):
        """0-indexed, on-screen window position(row) in display cells."""
        return self._session.request('window_get_position', self)[0]

    @property
    def col(self):
        """0-indexed, on-screen window position(col) in display cells."""
        return self._session.request('window_get_position', self)[1]

    @property
    def tabpage(self):
        """Get the `Tabpage` that contains the window."""
        return self._session.request('window_get_tabpage', self)

    @property
    def valid(self):
        """Return True if the window still exists."""
        return self._session.request('window_is_valid', self)
