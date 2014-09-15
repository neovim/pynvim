from .util import RemoteMap
import sys

if sys.version_info[0] >= 3:
    # For python3/2 compatibility define basestring
    basestring = str

class Buffer(object):
    @classmethod
    def initialize(self, buffer):
        buffer.vars = RemoteMap(lambda k: buffer.get_var(k),
                                lambda k, v: buffer.set_var(k, v))
        buffer.options = RemoteMap(lambda k: buffer.get_option(k),
                                   lambda k, v: buffer.set_option(k, v))

    def __len__(self):
        return self.get_length()

    def __getitem__(self, idx):
        if not isinstance(idx, slice):
            return self.get_line(idx)
        include_end = False
        start = idx.start
        end = idx.stop
        if start == None:
            start = 0
        if end == None:
            end = -1
            include_end = True
        return self.get_slice(start, end, True, include_end)

    def __setitem__(self, idx, lines):
        if not isinstance(idx, slice):
            if lines == None:
                return self.del_line(idx)
            else:
                return self.set_line(idx, lines)
        if lines == None:
            lines = []
        include_end = False
        start = idx.start
        end = idx.stop
        if start == None:
            start = 0
        if end == None:
            end = -1
            include_end = True
        return self.set_slice(start, end, True, include_end, lines)

    def __iter__(self):
        lines = self[:]
        for line in lines:
            yield line

    def append(self, lines, index=-1):
        if isinstance(lines, basestring):
            lines = [lines]
        self.insert(index, lines)

    def mark(self, name):
        return self.get_mark(name)

    def range(self, start, end):
        return Range(self, start, end)

    @property
    def name(self):
        return self.get_name()

    @name.setter
    def name(self, value):
        return self.set_name(value)

    @property
    def number(self):
        return self.get_number()

    @property
    def valid(self):
        return self.is_valid()


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
        if start == None:
            start = self.start
        if end == None:
            end = self.end
        return self._buffer[start:end]

    def __setitem__(self, idx, lines):
        if not isinstance(idx, slice):
            self._buffer[self._normalize_index(idx)] = lines
            return
        start = self._normalize_index(idx.start)
        end = self._normalize_index(idx.stop)
        if start == None:
            start = self.start
        if end == None:
            end = self.end
        self._buffer[start:end] = lines

    def __iter__(self):
        for i in xrange(self.start, self.end):
            yield self._buffer[i]

    def append(self, lines, i=None):
        i = self._normalize_index(i)
        if i == None:
            i = self.end
        self._buffer.append(lines, i)

    def _normalize_index(self, index):
        if index == None:
            return None
        if index < 0:
            index = self.end - 1
        else:
            index += self.start
            if index >= self.end:
                index = self.end - 1
        return index
