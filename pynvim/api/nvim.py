"""Main Nvim interface."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from functools import partial
from traceback import format_stack
from types import SimpleNamespace
from typing import (Any, AnyStr, Callable, Dict, Iterator, List, Optional,
                    TYPE_CHECKING, Union)

from msgpack import ExtType

from pynvim.api.buffer import Buffer
from pynvim.api.common import (NvimError, Remote, RemoteApi, RemoteMap, RemoteSequence,
                               TDecodeMode, decode_if_bytes, walk)
from pynvim.api.tabpage import Tabpage
from pynvim.api.window import Window
from pynvim.util import format_exc_skip

if TYPE_CHECKING:
    from pynvim.msgpack_rpc import Session

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

__all__ = ['Nvim']


os_chdir = os.chdir

lua_module = """
local a = vim.api
local function update_highlights(buf, src_id, hls, clear_first, clear_end)
  if clear_first ~= nil then
      a.nvim_buf_clear_highlight(buf, src_id, clear_first, clear_end)
  end
  for _,hl in pairs(hls) do
    local group, line, col_start, col_end = unpack(hl)
    if col_start == nil then
      col_start = 0
    end
    if col_end == nil then
      col_end = -1
    end
    a.nvim_buf_add_highlight(buf, src_id, group, line, col_start, col_end)
  end
end

local chid = ...
local mod = {update_highlights=update_highlights}
_G["_pynvim_"..chid] = mod
"""


class Nvim:
    """Class that represents a remote Nvim instance.

    This class is main entry point to Nvim remote API, it is a wrapper
    around Session instances.

    The constructor of this class must not be called directly. Instead, the
    `from_session` class method should be used to create the first instance
    from a raw `Session` instance.

    Subsequent instances for the same session can be created by calling the
    `with_decode` instance method to change the decoding behavior or
    `SubClass.from_nvim(nvim)` where `SubClass` is a subclass of `Nvim`, which
    is useful for having multiple `Nvim` objects that behave differently
    without one affecting the other.

    When this library is used on python3.4+, asyncio event loop is guaranteed
    to be used. It is available as the "loop" attribute of this class. Note
    that asyncio callbacks cannot make blocking requests, which includes
    accessing state-dependent attributes. They should instead schedule another
    callback using nvim.async_call, which will not have this restriction.
    """

    @classmethod
    def from_session(cls, session: Session) -> Nvim:
        """Create a new Nvim instance for a Session instance.

        This method must be called to create the first Nvim instance, since it
        queries Nvim metadata for type information and sets a SessionHook for
        creating specialized objects from Nvim remote handles.
        """
        session.error_wrapper = lambda e: NvimError(decode_if_bytes(e[1]))
        channel_id, metadata = session.request(b'nvim_get_api_info')

        metadata = walk(decode_if_bytes, metadata)

        types = {
            metadata['types']['Buffer']['id']: Buffer,
            metadata['types']['Window']['id']: Window,
            metadata['types']['Tabpage']['id']: Tabpage,
        }

        return cls(session, channel_id, metadata, types)

    @classmethod
    def from_nvim(cls, nvim: Nvim) -> Nvim:
        """Create a new Nvim instance from an existing instance."""
        return cls(nvim._session, nvim.channel_id, nvim.metadata,
                   nvim.types, nvim._decode, nvim._err_cb)

    def __init__(
        self,
        session: Session,
        channel_id: int,
        metadata: Dict[str, Any],
        types: Dict[int, Any],
        decode: TDecodeMode = True,
        err_cb: Optional[Callable[[str], None]] = None
    ):
        """Initialize a new Nvim instance. This method is module-private."""
        self._session = session
        self.channel_id = channel_id
        self.metadata = metadata
        version = metadata.get("version", {"api_level": 0})
        self.version = SimpleNamespace(**version)
        self.types = types
        self.api = RemoteApi(self, 'nvim_')
        self.vars = RemoteMap(self, 'nvim_get_var', 'nvim_set_var', 'nvim_del_var')
        self.vvars = RemoteMap(self, 'nvim_get_vvar', None, None)
        self.options = RemoteMap(self, 'nvim_get_option', 'nvim_set_option')
        self.buffers = Buffers(self)
        self.windows: RemoteSequence[Window] = RemoteSequence(self, 'nvim_list_wins')
        self.tabpages: RemoteSequence[Tabpage] = RemoteSequence(
            self, 'nvim_list_tabpages'
        )
        self.current = Current(self)
        self.session = CompatibilitySession(self)
        self.funcs = Funcs(self)
        self.lua = LuaFuncs(self)
        self.error = NvimError
        self._decode = decode
        if err_cb is None:
            self._err_cb: Callable[[str], Any] = lambda _: None
        else:
            self._err_cb = err_cb

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop (exposed to rplugins)."""  # noqa

        # see #294: for python 3.4+, the only available and guaranteed
        # implementation of msgpack_rpc BaseEventLoop is the AsyncioEventLoop.
        # The underlying asyncio event loop is exposed to rplugins.
        # pylint: disable=protected-access
        return self._session.loop._loop  # type: ignore

    def _from_nvim(self, obj: Any, decode: Optional[TDecodeMode] = None) -> Any:
        if decode is None:
            decode = self._decode
        if type(obj) is ExtType:
            cls = self.types[obj.code]
            return cls(self, (obj.code, obj.data))
        if decode:
            obj = decode_if_bytes(obj, decode)
        return obj

    def _to_nvim(self, obj: Any) -> Any:
        if isinstance(obj, Remote):
            return ExtType(*obj.code_data)
        return obj

    def _get_lua_private(self) -> LuaFuncs:
        if not getattr(self._session, "_has_lua", False):
            self.exec_lua(lua_module, self.channel_id)
            self._session._has_lua = True  # type: ignore[attr-defined]
        return getattr(self.lua, "_pynvim_{}".format(self.channel_id))

    def request(self, name: str, *args: Any, **kwargs: Any) -> Any:
        r"""Send an API request or notification to nvim.

        It is rarely needed to call this function directly, as most API
        functions have python wrapper functions. The `api` object can
        be also be used to call API functions as methods:

            vim.api.err_write('ERROR\n', async_=True)
            vim.current.buffer.api.get_mark('.')

        is equivalent to

            vim.request('nvim_err_write', 'ERROR\n', async_=True)
            vim.request('nvim_buf_get_mark', vim.current.buffer, '.')


        Normally a blocking request will be sent.  If the `async_` flag is
        present and True, a asynchronous notification is sent instead. This
        will never block, and the return value or error is ignored.
        """
        if (self._session._loop_thread is not None
                and threading.current_thread() != self._session._loop_thread):

            msg = ("Request from non-main thread.\n"
                   "Requests from different threads should be wrapped "
                   "with nvim.async_call(cb, ...) \n{}\n"
                   .format('\n'.join(format_stack(None, 5)[:-1])))

            self.async_call(self._err_cb, msg)
            raise NvimError("request from non-main thread")

        decode = kwargs.pop('decode', self._decode)
        args = walk(self._to_nvim, args)
        res = self._session.request(name, *args, **kwargs)
        return walk(self._from_nvim, res, decode=decode)

    def next_message(self) -> Any:
        """Block until a message(request or notification) is available.

        If any messages were previously enqueued, return the first in queue.
        If not, run the event loop until one is received.
        """
        msg = self._session.next_message()
        if msg:
            return walk(self._from_nvim, msg)

    def run_loop(
        self,
        request_cb: Optional[Callable[[str, List[Any]], Any]],
        notification_cb: Optional[Callable[[str, List[Any]], Any]],
        setup_cb: Optional[Callable[[], None]] = None,
        err_cb: Optional[Callable[[str], Any]] = None
    ) -> None:
        """Run the event loop to receive requests and notifications from Nvim.

        This should not be called from a plugin running in the host, which
        already runs the loop and dispatches events to plugins.
        """
        if err_cb is None:
            err_cb = sys.stderr.write
        self._err_cb = err_cb

        def filter_request_cb(name: str, args: Any) -> Any:
            name = self._from_nvim(name)
            args = walk(self._from_nvim, args)
            try:
                result = request_cb(name, args)  # type: ignore[misc]
            except Exception:
                msg = ("error caught in request handler '{} {}'\n{}\n\n"
                       .format(name, args, format_exc_skip(1)))
                self._err_cb(msg)
                raise
            return walk(self._to_nvim, result)

        def filter_notification_cb(name: str, args: Any) -> None:
            name = self._from_nvim(name)
            args = walk(self._from_nvim, args)
            try:
                notification_cb(name, args)  # type: ignore[misc]
            except Exception:
                msg = ("error caught in notification handler '{} {}'\n{}\n\n"
                       .format(name, args, format_exc_skip(1)))
                self._err_cb(msg)
                raise

        self._session.run(filter_request_cb, filter_notification_cb, setup_cb)

    def stop_loop(self) -> None:
        """Stop the event loop being started with `run_loop`."""
        self._session.stop()

    def close(self) -> None:
        """Close the nvim session and release its resources."""
        self._session.close()

    def __enter__(self) -> Nvim:
        """Enter nvim session as a context manager."""
        return self

    def __exit__(self, *exc_info: Any) -> None:
        """Exit nvim session as a context manager.

        Closes the event loop.
        """
        self.close()

    def with_decode(self, decode: Literal[True] = True) -> Nvim:
        """Initialize a new Nvim instance."""
        return Nvim(self._session, self.channel_id,
                    self.metadata, self.types, decode, self._err_cb)

    def ui_attach(
        self, width: int, height: int, rgb: Optional[bool] = None, **kwargs: Any
    ) -> None:
        """Register as a remote UI.

        After this method is called, the client will receive redraw
        notifications.
        """
        options = kwargs
        if rgb is not None:
            options['rgb'] = rgb
        return self.request('nvim_ui_attach', width, height, options)

    def ui_detach(self) -> None:
        """Unregister as a remote UI."""
        return self.request('nvim_ui_detach')

    def ui_try_resize(self, width: int, height: int) -> None:
        """Notify nvim that the client window has resized.

        If possible, nvim will send a redraw request to resize.
        """
        return self.request('ui_try_resize', width, height)

    def subscribe(self, event: str) -> None:
        """Subscribe to a Nvim event."""
        return self.request('nvim_subscribe', event)

    def unsubscribe(self, event: str) -> None:
        """Unsubscribe to a Nvim event."""
        return self.request('nvim_unsubscribe', event)

    def command(self, string: str, **kwargs: Any) -> None:
        """Execute a single ex command."""
        return self.request('nvim_command', string, **kwargs)

    def command_output(self, string: str) -> str:
        """Execute a single ex command and return the output."""
        return self.request('nvim_command_output', string)

    def eval(self, string: str, **kwargs: Any) -> Any:
        """Evaluate a vimscript expression."""
        return self.request('nvim_eval', string, **kwargs)

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a vimscript function."""
        return self.request('nvim_call_function', name, args, **kwargs)

    def exec_lua(self, code: str, *args: Any, **kwargs: Any) -> Any:
        """Execute lua code.

        Additional parameters are available as `...` inside the lua chunk.
        Only statements are executed.  To evaluate an expression, prefix it
        with `return`: `return my_function(...)`

        There is a shorthand syntax to call lua functions with arguments:

            nvim.lua.func(1,2)
            nvim.lua.mymod.myfunction(data, async_=True)

        is equivalent to

            nvim.exec_lua("return func(...)", 1, 2)
            nvim.exec_lua("mymod.myfunction(...)", data, async_=True)

        Note that with `async_=True` there is no return value.
        """
        return self.request('nvim_execute_lua', code, args, **kwargs)

    def strwidth(self, string: str) -> int:
        """Return the number of display cells `string` occupies.

        Tab is counted as one cell.
        """
        return self.request('nvim_strwidth', string)

    def list_runtime_paths(self) -> List[str]:
        """Return a list of paths contained in the 'runtimepath' option."""
        return self.request('nvim_list_runtime_paths')

    def foreach_rtp(self, cb: Callable[[str], Any]) -> None:
        """Invoke `cb` for each path in 'runtimepath'.

        Call the given callable for each path in 'runtimepath' until either
        callable returns something but None, the exception is raised or there
        are no longer paths. If stopped in case callable returned non-None,
        vim.foreach_rtp function returns the value returned by callable.
        """
        for path in self.list_runtime_paths():
            try:
                if cb(path) is not None:
                    break
            except Exception:
                break

    def chdir(self, dir_path: str) -> None:
        """Run os.chdir, then all appropriate vim stuff."""
        os_chdir(dir_path)
        return self.request('nvim_set_current_dir', dir_path)

    def feedkeys(self, keys: str, options: str = '', escape_csi: bool = True) -> None:
        """Push `keys` to Nvim user input buffer."""
        return self.request('nvim_feedkeys', keys, options, escape_csi)

    def input(self, bytes: AnyStr) -> int:
        """Push `bytes` to Nvim low level input buffer.

        Unlike `feedkeys()`, this uses the lowest level input buffer and the
        call is not deferred. It returns the number of bytes actually
        written(which can be less than what was requested if the buffer is
        full).
        """
        return self.request('nvim_input', bytes)

    def replace_termcodes(
        self,
        string: str,
        from_part: bool = False,
        do_lt: bool = True,
        special: bool = True
    ) -> str:
        r"""Replace any terminal code strings by byte sequences.

        The returned sequences are Nvim's internal representation of keys,
        for example:

        <esc> -> '\x1b'
        <cr>  -> '\r'
        <c-l> -> '\x0c'
        <up>  -> '\x80ku'

        The returned sequences can be used as input to `feedkeys`.
        """
        return self.request('nvim_replace_termcodes', string,
                            from_part, do_lt, special)

    def out_write(self, msg: str, **kwargs: Any) -> None:
        r"""Print `msg` as a normal message.

        The message is buffered (won't display) until linefeed ("\n").
        """
        return self.request('nvim_out_write', msg, **kwargs)

    def err_write(self, msg: str, **kwargs: Any) -> None:
        r"""Print `msg` as an error message.

        The message is buffered (won't display) until linefeed ("\n").
        """
        if self._thread_invalid():
            # special case: if a non-main thread writes to stderr
            # i.e. due to an uncaught exception, pass it through
            # without raising an additional exception.
            self.async_call(self.err_write, msg, **kwargs)
            return
        return self.request('nvim_err_write', msg, **kwargs)

    def _thread_invalid(self) -> bool:
        return (self._session._loop_thread is not None
                and threading.current_thread() != self._session._loop_thread)

    def quit(self, quit_command: str = 'qa!') -> None:
        """Send a quit command to Nvim.

        By default, the quit command is 'qa!' which will make Nvim quit without
        saving anything.
        """
        try:
            self.command(quit_command)
        except OSError:
            # sending a quit command will raise an IOError because the
            # connection is closed before a response is received. Safe to
            # ignore it.
            pass

    def new_highlight_source(self) -> int:
        """Return new src_id for use with Buffer.add_highlight."""
        return self.current.buffer.add_highlight("", 0, src_id=0)

    def async_call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Schedule `fn` to be called by the event loop soon.

        This function is thread-safe, and is the only way code not
        on the main thread could interact with nvim api objects.

        This function can also be called in a synchronous
        event handler, just before it returns, to defer execution
        that shouldn't block neovim.
        """
        call_point = ''.join(format_stack(None, 5)[:-1])

        def handler() -> None:
            try:
                fn(*args, **kwargs)
            except Exception as err:
                msg = ("error caught while executing async callback:\n"
                       "{!r}\n{}\n \nthe call was requested at\n{}"
                       .format(err, format_exc_skip(1), call_point))
                self._err_cb(msg)
                raise
        self._session.threadsafe_call(handler)


class Buffers(object):

    """Remote NVim buffers.

    Currently the interface for interacting with remote NVim buffers is the
    `nvim_list_bufs` msgpack-rpc function. Most methods fetch the list of
    buffers from NVim.

    Conforms to *python-buffers*.
    """

    def __init__(self, nvim: Nvim):
        """Initialize a Buffers object with Nvim object `nvim`."""
        self._fetch_buffers = nvim.api.list_bufs

    def __len__(self) -> int:
        """Return the count of buffers."""
        return len(self._fetch_buffers())

    def __getitem__(self, number: int) -> Buffer:
        """Return the Buffer object matching buffer number `number`."""
        for b in self._fetch_buffers():
            if b.number == number:
                return b
        raise KeyError(number)

    def __contains__(self, b: Buffer) -> bool:
        """Return whether Buffer `b` is a known valid buffer."""
        return isinstance(b, Buffer) and b.valid

    def __iter__(self) -> Iterator[Buffer]:
        """Return an iterator over the list of buffers."""
        return iter(self._fetch_buffers())


class CompatibilitySession(object):

    """Helper class for API compatibility."""

    def __init__(self, nvim: Nvim):
        self.threadsafe_call = nvim.async_call


class Current(object):

    """Helper class for emulating vim.current from python-vim."""

    def __init__(self, session: Nvim):
        self._session = session
        self.range = None

    @property
    def line(self) -> str:
        return self._session.request('nvim_get_current_line')

    @line.setter
    def line(self, line: str) -> None:
        return self._session.request('nvim_set_current_line', line)

    @line.deleter
    def line(self) -> None:
        return self._session.request('nvim_del_current_line')

    @property
    def buffer(self) -> Buffer:
        return self._session.request('nvim_get_current_buf')

    @buffer.setter
    def buffer(self, buffer: Union[Buffer, int]) -> None:
        return self._session.request('nvim_set_current_buf', buffer)

    @property
    def window(self) -> Window:
        return self._session.request('nvim_get_current_win')

    @window.setter
    def window(self, window: Union[Window, int]) -> None:
        return self._session.request('nvim_set_current_win', window)

    @property
    def tabpage(self) -> Tabpage:
        return self._session.request('nvim_get_current_tabpage')

    @tabpage.setter
    def tabpage(self, tabpage: Union[Tabpage, int]) -> None:
        return self._session.request('nvim_set_current_tabpage', tabpage)


class Funcs:
    """Helper class for functional vimscript interface."""

    def __init__(self, nvim: Nvim):
        self._nvim = nvim

    def __getattr__(self, name: str) -> Callable[..., Any]:
        return partial(self._nvim.call, name)


class LuaFuncs:
    """Wrapper to allow lua functions to be called like python methods."""

    def __init__(self, nvim: Nvim, name: str = ""):
        self._nvim = nvim
        self.name = name

    def __getattr__(self, name: str) -> LuaFuncs:
        """Return wrapper to named api method."""
        prefix = self.name + "." if self.name else ""
        return LuaFuncs(self._nvim, prefix + name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # first new function after keyword rename, be a bit noisy
        if 'async' in kwargs:
            raise ValueError('"async" argument is not allowed. '
                             'Use "async_" instead.')
        async_ = kwargs.get('async_', False)
        pattern = "return {}(...)" if not async_ else "{}(...)"
        code = pattern.format(self.name)
        return self._nvim.exec_lua(code, *args, **kwargs)
