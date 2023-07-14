"""Code shared between the API classes."""
import functools
import sys
from abc import ABC, abstractmethod
from typing import (Any, Callable, Generic, Iterator, List, Optional, Tuple, TypeVar,
                    Union, overload)

from msgpack import unpackb
if sys.version_info < (3, 8):
    from typing_extensions import Literal, Protocol
else:
    from typing import Literal, Protocol

from pynvim.compat import unicode_errors_default

__all__ = ()


T = TypeVar('T')
TDecodeMode = Union[Literal[True], str]


class NvimError(Exception):
    pass


class IRemote(Protocol):
    def request(self, name: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class Remote(ABC):

    """Base class for Nvim objects(buffer/window/tabpage).

    Each type of object has it's own specialized class with API wrappers around
    the msgpack-rpc session. This implements equality which takes the remote
    object handle into consideration.
    """

    def __init__(self, session: IRemote, code_data: Tuple[int, Any]):
        """Initialize from session and code_data immutable object.

        The `code_data` contains serialization information required for
        msgpack-rpc calls. It must be immutable for Buffer equality to work.
        """
        self._session = session
        self.code_data = code_data
        self.handle = unpackb(code_data[1])
        self.api = RemoteApi(self, self._api_prefix)
        self.vars = RemoteMap(self, self._api_prefix + 'get_var',
                              self._api_prefix + 'set_var',
                              self._api_prefix + 'del_var')
        self.options = RemoteMap(self, self._api_prefix + 'get_option',
                                 self._api_prefix + 'set_option')

    @property
    @abstractmethod
    def _api_prefix(self) -> str:
        raise NotImplementedError()

    def __repr__(self) -> str:
        """Get text representation of the object."""
        return '<%s(handle=%r)>' % (
            self.__class__.__name__,
            self.handle,
        )

    def __eq__(self, other: Any) -> bool:
        """Return True if `self` and `other` are the same object."""
        return (hasattr(other, 'code_data')
                and other.code_data == self.code_data)

    def __hash__(self) -> int:
        """Return hash based on remote object id."""
        return self.code_data.__hash__()

    def request(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Wrapper for nvim.request."""
        return self._session.request(name, self, *args, **kwargs)


class RemoteApi(object):

    """Wrapper to allow api methods to be called like python methods."""

    def __init__(self, obj: IRemote, api_prefix: str):
        """Initialize a RemoteApi with object and api prefix."""
        self._obj = obj
        self._api_prefix = api_prefix

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Return wrapper to named api method."""
        return functools.partial(self._obj.request, self._api_prefix + name)


E = TypeVar('E', bound=Exception)


def transform_keyerror(exc: E) -> Union[E, KeyError]:
    if isinstance(exc, NvimError):
        if exc.args[0].startswith('Key not found:'):
            return KeyError(exc.args[0])
        if exc.args[0].startswith('Invalid option name:'):
            return KeyError(exc.args[0])
    return exc


class RemoteMap(object):
    """Represents a string->object map stored in Nvim.

    This is the dict counterpart to the `RemoteSequence` class, but it is used
    as a generic way of retrieving values from the various map-like data
    structures present in Nvim.

    It is used to provide a dict-like API to vim variables and options.
    """

    _set = None
    _del = None

    def __init__(
        self,
        obj: IRemote,
        get_method: str,
        set_method: Optional[str] = None,
        del_method: Optional[str] = None
    ):
        """Initialize a RemoteMap with session, getter/setter."""
        self._get = functools.partial(obj.request, get_method)
        if set_method:
            self._set = functools.partial(obj.request, set_method)
        if del_method:
            self._del = functools.partial(obj.request, del_method)

    def __getitem__(self, key: str) -> Any:
        """Return a map value by key."""
        try:
            return self._get(key)
        except NvimError as exc:
            raise transform_keyerror(exc)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a map value by key(if the setter was provided)."""
        if not self._set:
            raise TypeError('This dict is read-only')
        self._set(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete a map value by associating None with the key."""
        if not self._del:
            raise TypeError('This dict is read-only')
        try:
            return self._del(key)
        except NvimError as exc:
            raise transform_keyerror(exc)

    def __contains__(self, key: str) -> bool:
        """Check if key is present in the map."""
        try:
            self._get(key)
            return True
        except Exception:
            return False

    @overload
    def get(self, key: str, default: T) -> T: ...

    @overload
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]: ...

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Return value for key if present, else a default value."""
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


class RemoteSequence(Generic[T]):

    """Represents a sequence of objects stored in Nvim.

    This class is used to wrap msgpack-rpc functions that work on Nvim
    sequences(of lines, buffers, windows and tabpages) with an API that
    is similar to the one provided by the python-vim interface.

    For example, the 'windows' property of the `Nvim` class is a RemoteSequence
    sequence instance, and the expression `nvim.windows[0]` is translated to
    session.request('nvim_list_wins')[0].

    One important detail about this class is that all methods will fetch the
    sequence into a list and perform the necessary manipulation
    locally(iteration, indexing, counting, etc).
    """

    def __init__(self, session: IRemote, method: str):
        """Initialize a RemoteSequence with session, method."""
        self._fetch = functools.partial(session.request, method)

    def __len__(self) -> int:
        """Return the length of the remote sequence."""
        return len(self._fetch())

    @overload
    def __getitem__(self, idx: int) -> T: ...

    @overload
    def __getitem__(self, idx: slice) -> List[T]: ...

    def __getitem__(self, idx: Union[slice, int]) -> Union[T, List[T]]:
        """Return a sequence item by index."""
        if not isinstance(idx, slice):
            return self._fetch()[idx]
        return self._fetch()[idx.start:idx.stop]

    def __iter__(self) -> Iterator[T]:
        """Return an iterator for the sequence."""
        items = self._fetch()
        for item in items:
            yield item

    def __contains__(self, item: T) -> bool:
        """Check if an item is present in the sequence."""
        return item in self._fetch()


@overload
def decode_if_bytes(obj: bytes, mode: TDecodeMode = True) -> str: ...


@overload
def decode_if_bytes(obj: T, mode: TDecodeMode = True) -> Union[T, str]: ...


def decode_if_bytes(obj: T, mode: TDecodeMode = True) -> Union[T, str]:
    """Decode obj if it is bytes."""
    if mode is True:
        mode = unicode_errors_default
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors=mode)
    return obj


def walk(fn: Callable[..., Any], obj: Any, *args: Any, **kwargs: Any) -> Any:
    """Recursively walk an object graph applying `fn`/`args` to objects."""
    if type(obj) in [list, tuple]:
        return list(walk(fn, o, *args) for o in obj)
    if type(obj) is dict:
        return dict((walk(fn, k, *args), walk(fn, v, *args)) for k, v in
                    obj.items())
    return fn(obj, *args, **kwargs)
