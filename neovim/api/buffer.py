"""API for working with a Nvim Buffer."""
from .common import Remote
from ..compat import IS_PYTHON3

from collections import Iterable
import itertools


__all__ = ('Buffer')


if IS_PYTHON3:
    basestring = str


def adjust_index(idx, default=None):
    """Convert from python indexing convention to nvim indexing convention."""
    if idx is None:
        return default
    elif idx < 0:
        return idx - 1
    else:
        return idx


class Buffer(Remote):

    """A remote Nvim buffer."""

    _api_prefix = "nvim_buf_"

    def __len__(self):
        """Return the number of lines contained in a Buffer."""
        return self.request('nvim_buf_line_count')

    def __getitem__(self, idx):
        """Get a buffer line or slice by integer index.

        Indexes may be negative to specify positions from the end of the
        buffer. For example, -1 is the last line, -2 is the line before that
        and so on.

        When retrieving slices, omiting indexes(eg: `buffer[:]`) will bring
        the whole buffer.
        """
        if not isinstance(idx, slice):
            i = adjust_index(idx)
            return self.request('nvim_buf_get_lines', i, i + 1, True)[0]
        start = adjust_index(idx.start, 0)
        end = adjust_index(idx.stop, -1)
        return self.request('nvim_buf_get_lines', start, end, False)

    def __setitem__(self, idx, item):
        """Replace a buffer line or slice by integer index.

        Like with `__getitem__`, indexes may be negative.

        When replacing slices, omiting indexes(eg: `buffer[:]`) will replace
        the whole buffer.
        """
        if not isinstance(idx, slice):
            i = adjust_index(idx)
            lines = [item] if item is not None else []
            return self.request('nvim_buf_set_lines', i, i + 1, True, lines)
        lines = item if item is not None else []
        start = adjust_index(idx.start, 0)
        end = adjust_index(idx.stop, -1)
        return self.request('nvim_buf_set_lines', start, end, False, lines)

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
        self.__setitem__(idx, None)

    def append(self, lines, index=-1):
        """Append a string or list of lines to the buffer."""
        if isinstance(lines, (basestring, bytes)):
            lines = [lines]
        return self.request('nvim_buf_set_lines', index, index, True, lines)

    def mark(self, name):
        """Return (row, col) tuple for a named mark."""
        return self.request('nvim_buf_get_mark', name)

    def range(self, start, end):
        """Return a `Range` object, which represents part of the Buffer."""
        return Range(self, start, end)

    def add_highlight(self, hl_group, line, col_start=0,
                      col_end=-1, src_id=-1, async=None):
        """Add a highlight to the buffer."""
        if async is None:
            async = (src_id != 0)
        return self.request('nvim_buf_add_highlight', src_id, hl_group,
                            line, col_start, col_end, async=async)

    def clear_highlight(self, src_id, line_start=0, line_end=-1, async=True):
        """Clear highlights from the buffer."""
        self.request('nvim_buf_clear_highlight', src_id,
                     line_start, line_end, async=async)

    @property
    def name(self):
        """Get the buffer name."""
        return self.request('nvim_buf_get_name')

    @name.setter
    def name(self, value):
        """Set the buffer name. BufFilePre/BufFilePost are triggered."""
        return self.request('nvim_buf_set_name', value)

    @property
    def valid(self):
        """Return True if the buffer still exists."""
        return self.request('nvim_buf_is_valid')

    @property
    def number(self):
        """Get the buffer number."""
        return self.handle

    @property
    def visual_selection(self):
        """Get the current visual selection as a Region object."""

        startmark = self.mark('<')
        endmark = self.mark('>')

        rowstart, colstart = self.mark('<')
        rowend, colend     = self.mark('>')

        if rowend - rowstart == 0:
            # same line, one liners are easy
            return Region(self, rowstart, rowend, partials=(colstart, colend))

        vmode = self.nvim.funcs.visualmode()

        if vmode == "v":
            # standard visual mode
            line_count = rowend - rowstart + 1
            full_lines_count = line_count - 2  # all except the first and last line
            partiallist = [(colstart, None)] + full_lines_count*[(None, None)] + [(None, colend)]
            return Region(self, rowstart, rowend, partials=partiallist)
        elif vmode == "":
            # visual block mode
            return Region(self, rowstart, rowend, partials=(colstart, colend))
        elif vmode == "V":
            # visual line mode
            return Region(self, rowstart, rowend, partials=(None, None))

        return Region(self, startmark, endmark)


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
            end = self.end
        self._buffer[start:end + 1] = lines

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



class Region(object):
    def __init__(self, buffer, startrow, endrow, partials=(None, None)):
        if not startrow <= endrow:
            raise ValueError("Negative span of rows provided.")

        # the range of the buffer this Region covers
        self._range = buffer.range(startrow, endrow)

        if not isinstance(partials[0], Iterable):
            # in this case we assume the provided partial
            # to be (int, int) and the default for all lines,
            # so create a list of appropriate length
            partials = [partials]*len(self._range)
        else:
            # we only need to assert this if we haven't created
            # that list ourselves
            if len(self._range) != len(partials):
                raise ValueError("length mismatch between partials and provided range")

        self._partials = [slice(*p) for p in partials]
        return

    def __len__(self):
        """
        Returns the number of characters covered by the Region
        """
        return sum([len(line[part]) for line, part in zip(self._range, self._partials)])

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            i = adjust_index(idx)
            return self.request('nvim_buf_get_lines', i, i + 1, True)[0]
        start = adjust_index(idx.start, 0)
        end = adjust_index(idx.stop, -1)
        #for i, (a, b, c) in enumerate(itertools.islice(zip(l1, l2, l3), 3, 7)):
        if not isinstance(idx, slice):
            return self._range[idx][self.partials[idx+1]]

        start = idx.start or 0
        end = idx.stop or len(self._range)

        lineiter = itertools.islice(zip(self._range, self._partials), start, end)
        return [line[partial] for line, partial in lineiter]

    def __setitem__(self, idx, lineparts):
        if not isinstance(idx, slice):
            new_line = self._assemble_line(idx, lineparts[0])
            self._range[idx] = new_line
            return
        start = idx.start or 0
        end = idx.stop or len(self._range)
        if end - start != len(lineparts):
            raise ValueError("mismatch of target lines and inserts")

        lines = []
        for i in range(start, end):
            ni = i - start  # normalized index
            lines.append(self._assemble_line(i, lineparts[ni]))
        self._range[start:end] = lines

    def __iter__(self):
        return self

    def __next__(self):
        for line, partial in zip(self._range, self._partials):
            yield line[partial]

    def _assemble_line(self, i, replacement):
        start = self._partials[i].start or 0
        stop = self._partials[i].stop
        orig_prefix = self._range[i][:start]

        if stop:
            orig_suffix = self._range[i][stop:]
        else:
            orig_suffix = ""
        new_line = orig_prefix + replacement + orig_suffix
        return new_line
