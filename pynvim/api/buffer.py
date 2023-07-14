"""API for working with a Nvim Buffer."""
from typing import (Any, Iterator, List, Optional, TYPE_CHECKING, Tuple, Union, cast,
                    overload)

from pynvim.api.common import Remote
from pynvim.compat import check_async

if TYPE_CHECKING:
    from pynvim.api import Nvim


__all__ = ('Buffer',)


@overload
def adjust_index(idx: int, default: Optional[int] = None) -> int:
    ...


@overload
def adjust_index(idx: Optional[int], default: int) -> int:
    ...


@overload
def adjust_index(idx: Optional[int], default: Optional[int] = None) -> Optional[int]:
    ...


def adjust_index(idx: Optional[int], default: Optional[int] = None) -> Optional[int]:
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
    _session: "Nvim"

    def __init__(self, session: "Nvim", code_data: Tuple[int, Any]):
        """Initialize from Nvim and code_data immutable object."""
        super().__init__(session, code_data)

    def __len__(self) -> int:
        """Return the number of lines contained in a Buffer."""
        return self.request('nvim_buf_line_count')

    @overload
    def __getitem__(self, idx: int) -> str:  # noqa: D105
        ...

    @overload
    def __getitem__(self, idx: slice) -> List[str]:  # noqa: D105
        ...

    def __getitem__(self, idx: Union[int, slice]) -> Union[str, List[str]]:
        """Get a buffer line or slice by integer index.

        Indexes may be negative to specify positions from the end of the
        buffer. For example, -1 is the last line, -2 is the line before that
        and so on.

        When retrieving slices, omitting indexes(eg: `buffer[:]`) will bring
        the whole buffer.
        """
        if not isinstance(idx, slice):
            i = adjust_index(idx)
            return self.request('nvim_buf_get_lines', i, i + 1, True)[0]
        start = adjust_index(idx.start, 0)
        end = adjust_index(idx.stop, -1)
        return self.request('nvim_buf_get_lines', start, end, False)

    @overload
    def __setitem__(self, idx: int, item: Optional[str]) -> None:  # noqa: D105
        ...

    @overload
    def __setitem__(  # noqa: D105
        self, idx: slice, item: Optional[Union[List[str], str]]
    ) -> None:
        ...

    def __setitem__(
        self, idx: Union[int, slice], item: Union[None, str, List[str]]
    ) -> None:
        """Replace a buffer line or slice by integer index.

        Like with `__getitem__`, indexes may be negative.

        When replacing slices, omitting indexes(eg: `buffer[:]`) will replace
        the whole buffer.
        """
        if not isinstance(idx, slice):
            assert not isinstance(item, list)
            i = adjust_index(idx)
            lines = [item] if item is not None else []
            return self.request('nvim_buf_set_lines', i, i + 1, True, lines)
        if item is None:
            lines = []
        elif isinstance(item, str):
            lines = [item]
        else:
            lines = item
        start = adjust_index(idx.start, 0)
        end = adjust_index(idx.stop, -1)
        return self.request('nvim_buf_set_lines', start, end, False, lines)

    def __iter__(self) -> Iterator[str]:
        """Iterate lines of a buffer.

        This will retrieve all lines locally before iteration starts. This
        approach is used because for most cases, the gain is much greater by
        minimizing the number of API calls by transferring all data needed to
        work.
        """
        lines = self[:]
        for line in lines:
            yield line

    def __delitem__(self, idx: Union[int, slice]) -> None:
        """Delete line or slice of lines from the buffer.

        This is the same as __setitem__(idx, [])
        """
        self.__setitem__(idx, None)

    def __ne__(self, other: Any) -> bool:
        """Test inequality of Buffers.

        Necessary for Python 2 compatibility.
        """
        return not self.__eq__(other)

    def append(
        self, lines: Union[str, bytes, List[Union[str, bytes]]], index: int = -1
    ) -> None:
        """Append a string or list of lines to the buffer."""
        if isinstance(lines, (str, bytes)):
            lines = [lines]
        return self.request('nvim_buf_set_lines', index, index, True, lines)

    def mark(self, name: str) -> Tuple[int, int]:
        """Return (row, col) tuple for a named mark."""
        return cast(Tuple[int, int], tuple(self.request('nvim_buf_get_mark', name)))

    def range(self, start: int, end: int) -> "Range":
        """Return a `Range` object, which represents part of the Buffer."""
        return Range(self, start, end)

    def add_highlight(
        self,
        hl_group: str,
        line: int,
        col_start: int = 0,
        col_end: int = -1,
        src_id: int = -1,
        async_: Optional[bool] = None,
        **kwargs: Any
    ) -> int:
        """Add a highlight to the buffer."""
        async_ = check_async(async_, kwargs, src_id != 0)
        return self.request(
            "nvim_buf_add_highlight",
            src_id,
            hl_group,
            line,
            col_start,
            col_end,
            async_=async_,
        )

    def clear_highlight(
        self,
        src_id: int,
        line_start: int = 0,
        line_end: int = -1,
        async_: Optional[bool] = None,
        **kwargs: Any
    ) -> None:
        """Clear highlights from the buffer."""
        async_ = check_async(async_, kwargs, True)
        self.request(
            "nvim_buf_clear_highlight", src_id, line_start, line_end, async_=async_
        )

    def update_highlights(
        self,
        src_id: int,
        hls: List[Union[Tuple[str, int], Tuple[str, int, int, int]]],
        clear_start: Optional[int] = None,
        clear_end: int = -1,
        clear: bool = False,
        async_: bool = True,
    ) -> None:
        """Add or update highlights in batch to avoid unnecessary redraws.

        A `src_id` must have been allocated prior to use of this function. Use
        for instance `nvim.new_highlight_source()` to get a src_id for your
        plugin.

        `hls` should be a list of highlight items. Each item should be a list
        or tuple on the form `("GroupName", linenr, col_start, col_end)` or
        `("GroupName", linenr)` to highlight an entire line.

        By default existing highlights are preserved. Specify a line range with
        clear_start and clear_end to replace highlights in this range. As a
        shorthand, use clear=True to clear the entire buffer before adding the
        new highlights.
        """
        if clear and clear_start is None:
            clear_start = 0
        lua = self._session._get_lua_private()
        lua.update_highlights(self, src_id, hls, clear_start, clear_end, async_=async_)

    @property
    def name(self) -> str:
        """Get the buffer name."""
        return self.request('nvim_buf_get_name')

    @name.setter
    def name(self, value: str) -> None:
        """Set the buffer name. BufFilePre/BufFilePost are triggered."""
        return self.request('nvim_buf_set_name', value)

    @property
    def valid(self) -> bool:
        """Return True if the buffer still exists."""
        return self.request('nvim_buf_is_valid')

    @property
    def loaded(self) -> bool:
        """Return True if the buffer is valid and loaded."""
        return self.request('nvim_buf_is_loaded')

    @property
    def number(self) -> int:
        """Get the buffer number."""
        return self.handle


class Range(object):
    def __init__(self, buffer: Buffer, start: int, end: int):
        self._buffer = buffer
        self.start = start - 1
        self.end = end - 1

    def __len__(self) -> int:
        return self.end - self.start + 1

    @overload
    def __getitem__(self, idx: int) -> str:
        ...

    @overload
    def __getitem__(self, idx: slice) -> List[str]:
        ...

    def __getitem__(self, idx: Union[int, slice]) -> Union[str, List[str]]:
        if not isinstance(idx, slice):
            return self._buffer[self._normalize_index(idx)]
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start is None:
            start = self.start
        if end is None:
            end = self.end + 1
        return self._buffer[start:end]

    @overload
    def __setitem__(self, idx: int, lines: Optional[str]) -> None:
        ...

    @overload
    def __setitem__(self, idx: slice, lines: Optional[List[str]]) -> None:
        ...

    def __setitem__(
        self, idx: Union[int, slice], lines: Union[None, str, List[str]]
    ) -> None:
        if not isinstance(idx, slice):
            assert not isinstance(lines, list)
            self._buffer[self._normalize_index(idx)] = lines
            return
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start is None:
            start = self.start
        if end is None:
            end = self.end
        self._buffer[start:end + 1] = lines

    def __iter__(self) -> Iterator[str]:
        for i in range(self.start, self.end + 1):
            yield self._buffer[i]

    def append(
        self, lines: Union[str, bytes, List[Union[str, bytes]]], i: Optional[int] = None
    ) -> None:
        i = self._normalize_index(i)
        if i is None:
            i = self.end + 1
        self._buffer.append(lines, i)

    @overload
    def _normalize_index(self, index: int) -> int:
        ...

    @overload
    def _normalize_index(self, index: None) -> None:
        ...

    def _normalize_index(self, index: Optional[int]) -> Optional[int]:
        if index is None:
            return None
        if index < 0:
            index = self.end
        else:
            index += self.start
            if index > self.end:
                index = self.end
        return index
