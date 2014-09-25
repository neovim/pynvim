"""API for working with Nvim tabpages."""
from .common import Remote, RemoteMap, RemoteSequence


__all__ = ('Tabpage')


class Tabpage(Remote):

    """A remote Nvim tabpage."""

    def __init__(self, session, code_data):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Tabpage equality to work.
        """
        self._session = session
        self.code_data = code_data
        self.windows = RemoteSequence(session, 'tabpage_get_windows', self)
        self.vars = RemoteMap(session, 'tabpage_get_var', 'tabpage_set_var',
                              self)

    @property
    def window(self):
        """Get the `Window` currently focused on the tabpage."""
        return self._session.request('tabpage_get_window', self)

    @property
    def valid(self):
        """Return True if the tabpage still exists."""
        return self._session.request('tabpage_is_valid', self)
