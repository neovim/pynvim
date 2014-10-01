"""API for working with Nvim buffers."""
from .common import Remote, RemoteMap
from ..compat import IS_PYTHON3


__all__ = ('Buffer')


if IS_PYTHON3:
    basestring = str


class Buffer(Remote):

    """A remote Nvim buffer."""

    def __init__(self, session, code_data):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Buffer equality to work.
        """
        self._session = session
        self.code_data = code_data
        self.vars = RemoteMap(session, 'buffer_get_var', 'buffer_set_var',
                              self)
        self.options = RemoteMap(session, 'buffer_get_option',
                                 'buffer_set_option', self)

    def __len__(self):
        """Return the number of lines contained in a Buffer."""
        return self._session.request('buffer_line_count', self)

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
        return self._session.request('buffer_get_mark', self, name)

    def range(self, start, end):
        """Return a `Range` object, which represents part of the Buffer."""
        return Range(self, start, end)

    @property
    def name(self):
        """Get the buffer name."""
        return self._session.request('buffer_get_name', self)

    @name.setter
    def name(self, value):
        """Set the buffer name. BufFilePre/BufFilePost are triggered."""
        return self._session.request('buffer_set_name', self, value)

    @property
    def valid(self):
        """Return True if the buffer still exists."""
        return self._session.request('buffer_is_valid', self)

    @property
    def number(self):
        """Get the buffer number."""
        return self._session.request('buffer_get_number', self)


class Range(object):
    def __init__(self, buffer, start, end):
        self._buffer = buffer
        self.start = start - 1
        self.end = end

    def __len__(self):
        return self.end - self.start

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            return self._buffer[self._normalize_index(idx)]
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start is None:
            start = self.start
        if end is None:
            end = self.end
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
            end = self.end
        self._buffer[start:end] = lines

    def __iter__(self):
        for i in range(self.start, self.end):
            yield self._buffer[i]

    def append(self, lines, i=None):
        i = self._normalize_index(i)
        if i is None:
            i = self.end
        self._buffer.append(lines, i)

    def _normalize_index(self, index):
        if index is None:
            return None
        if index < 0:
            index = self.end - 1
        else:
            index += self.start
            if index >= self.end:
                index = self.end - 1
        return index
