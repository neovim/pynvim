"""API for working with Nvim buffers."""
from .common import Remote
from ..compat import IS_PYTHON3


__all__ = ('Buffer')


if IS_PYTHON3:
    basestring = str


class Buffer(Remote):

    """A remote Nvim buffer."""

    _api_prefix = "buffer_"

    def __len__(self):
        """Return the number of lines contained in a Buffer."""
        return self.request('buffer_line_count')

    def __getitem__(self, idx):
        """Get a buffer line or slice by integer index.

        Indexes may be negative to specify positions from the end of the
        buffer. For example, -1 is the last line, -2 is the line before that
        and so on.

        When retrieving slices, omiting indexes(eg: `buffer[:]`) will bring
        the whole buffer.
        """
        if not isinstance(idx, slice):
            return self._session.request('buffer_get_line', self, idx)
        include_end = False
        start = idx.start
        end = idx.stop
        if start is None:
            start = 0
        if end is None:
            end = -1
            include_end = True
        return self._session.request('buffer_get_line_slice', self, start, end,
                                     True, include_end)

    def __setitem__(self, idx, lines):
        """Replace a buffer line or slice by integer index.

        Like with `__getitem__`, indexes may be negative.

        When replacing slices, omiting indexes(eg: `buffer[:]`) will replace
        the whole buffer.
        """
        if not isinstance(idx, slice):
            if lines is None:
                return self._session.request('buffer_del_line', self, idx)
            else:
                return self._session.request('buffer_set_line', self, idx,
                                             lines)
        if lines is None:
            lines = []
        include_end = False
        start = idx.start
        end = idx.stop
        if start is None:
            start = 0
        if end is None:
            end = -1
            include_end = True
        return self._session.request('buffer_set_line_slice', self, start, end,
                                     True, include_end, lines)

    def __iter__(self):
        """Iterate lines of a buffer.

        This will retrieve all lines locally before iteration starts. This
        approach is used because for most cases, the gain is much greater by
        minimizing the number of API calls by transfering all data needed to
        work.
        """
        lines = self[:]
        for line in lines:
            yield line

    def __delitem__(self, idx):
        """Delete line or slice of lines from the buffer.

        This is the same as __setitem__(idx, [])
        """
        if not isinstance(idx, slice):
            self.__setitem__(idx, None)
        else:
            self.__setitem__(idx, [])

    def get_line_slice(self, start, stop, start_incl, end_incl):
        """More flexible wrapper for retrieving slices."""
        return self._session.request('buffer_get_line_slice', self, start,
                                     stop, start_incl, end_incl)

    def set_line_slice(self, start, stop, start_incl, end_incl, lines):
        """More flexible wrapper for replacing slices."""
        return self._session.request('buffer_set_line_slice', self, start,
                                     stop, start_incl, end_incl, lines)

    def append(self, lines, index=-1):
        """Append a string or list of lines to the buffer."""
        if isinstance(lines, basestring):
            lines = [lines]
        return self._session.request('buffer_insert', self, index, lines)

    def mark(self, name):
        """Return (row, col) tuple for a named mark."""
        return self.request('buffer_get_mark', name)

    def range(self, start, end):
        """Return a `Range` object, which represents part of the Buffer."""
        return Range(self, start, end)

    def add_highlight(self, hl_group, line, col_start=0,
                      col_end=-1, src_id=-1, async=None):
        """Add a highlight to the buffer."""
        if async is None:
            async = (src_id != 0)
        return self.request('buffer_add_highlight', src_id, hl_group,
                            line, col_start, col_end, async=async)

    def clear_highlight(self, src_id, line_start=0, line_end=-1, async=True):
        """clear highlights from the buffer."""
        self.request('buffer_clear_highlight', src_id,
                     line_start, line_end, async=async)

    @property
    def name(self):
        """Get the buffer name."""
        return self.request('buffer_get_name')

    @name.setter
    def name(self, value):
        """Set the buffer name. BufFilePre/BufFilePost are triggered."""
        return self.request('buffer_set_name', value)

    @property
    def valid(self):
        """Return True if the buffer still exists."""
        return self.request('buffer_is_valid')

    @property
    def number(self):
        """Get the buffer number."""
        return self.request('buffer_get_number')


class Range(object):
    def __init__(self, buffer, start, end):
        self._buffer = buffer
        self.start = start - 1
        self.end = end - 1

    def __len__(self):
        return self.end - self.start + 1

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            return self._buffer[self._normalize_index(idx)]
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start is None:
            start = self.start
        if end is None:
            end = self.end + 1
        return self._buffer[start:end]

    def __setitem__(self, idx, lines):
        if not isinstance(idx, slice):
            self._buffer[self._normalize_index(idx)] = lines
            return
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start is None:
            start = self.start
        if end is None:
            end = self.end + 1
        self._buffer[start:end] = lines

    def __iter__(self):
        for i in range(self.start, self.end + 1):
            yield self._buffer[i]

    def append(self, lines, i=None):
        i = self._normalize_index(i)
        if i is None:
            i = self.end + 1
        self._buffer.append(lines, i)

    def _normalize_index(self, index):
        if index is None:
            return None
        if index < 0:
            index = self.end
        else:
            index += self.start
            if index > self.end:
                index = self.end
        return index
