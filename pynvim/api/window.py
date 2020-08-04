"""API for working with Nvim windows."""
from pynvim.api.common import Remote


__all__ = ('Window')


class Window(Remote):

    """A remote Nvim window."""

    _api_prefix = "nvim_win_"

    @property
    def buffer(self):
        """Get the `Buffer` currently being displayed by the window."""
        return self.request('nvim_win_get_buf')

    @property
    def cursor(self):
        """Get the (row, col) tuple with the current cursor position."""
        return self.request('nvim_win_get_cursor')

    @cursor.setter
    def cursor(self, pos):
        """Set the (row, col) tuple as the new cursor position."""
        return self.request('nvim_win_set_cursor', pos)

    @property
    def height(self):
        """Get the window height in rows."""
        return self.request('nvim_win_get_height')

    @height.setter
    def height(self, height):
        """Set the window height in rows."""
        return self.request('nvim_win_set_height', height)

    @property
    def width(self):
        """Get the window width in rows."""
        return self.request('nvim_win_get_width')

    @width.setter
    def width(self, width):
        """Set the window height in rows."""
        return self.request('nvim_win_set_width', width)

    @property
    def row(self):
        """0-indexed, on-screen window position(row) in display cells."""
        return self.request('nvim_win_get_position')[0]

    @property
    def col(self):
        """0-indexed, on-screen window position(col) in display cells."""
        return self.request('nvim_win_get_position')[1]

    @property
    def tabpage(self):
        """Get the `Tabpage` that contains the window."""
        return self.request('nvim_win_get_tabpage')

    @property
    def valid(self):
        """Return True if the window still exists."""
        return self.request('nvim_win_is_valid')

    @property
    def number(self):
        """Get the window number."""
        return self.request('nvim_win_get_number')
