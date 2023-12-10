"""API for working with Nvim tabpages."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Tuple

from pynvim.api.common import Remote, RemoteSequence
from pynvim.api.window import Window

if TYPE_CHECKING:
    from pynvim.api.nvim import Nvim


__all__ = ['Tabpage']


class Tabpage(Remote):
    """A remote Nvim tabpage."""

    _api_prefix = "nvim_tabpage_"

    def __init__(self, session: Nvim, code_data: Tuple[int, Any]):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Buffer equality to work.
        """
        super(Tabpage, self).__init__(session, code_data)
        self.windows: RemoteSequence[Window] = RemoteSequence(
            self, "nvim_tabpage_list_wins"
        )

    @property
    def window(self) -> Window:
        """Get the `Window` currently focused on the tabpage."""
        return self.request('nvim_tabpage_get_win')

    @property
    def valid(self) -> bool:
        """Return True if the tabpage still exists."""
        return self.request('nvim_tabpage_is_valid')

    @property
    def number(self) -> int:
        """Get the tabpage number."""
        return self.request('nvim_tabpage_get_number')
