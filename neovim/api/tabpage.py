"""API for working with Nvim tabpages."""
from .common import Remote, RemoteSequence


__all__ = ('Tabpage')


class Tabpage(Remote):
    """A remote Nvim tabpage."""

    _api_prefix = "tabpage_"

    def __init__(self, *args):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Buffer equality to work.
        """
        super(Tabpage, self).__init__(*args)
        self.windows = RemoteSequence(self, 'tabpage_get_windows')

    @property
    def window(self):
        """Get the `Window` currently focused on the tabpage."""
        return self.request('tabpage_get_window')

    @property
    def valid(self):
        """Return True if the tabpage still exists."""
        return self.request('tabpage_is_valid')
