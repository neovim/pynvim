"""Main Nvim interface."""
import functools
import os
import sys

from traceback import format_stack

from msgpack import ExtType

from .buffer import Buffer
from .common import (Remote, RemoteApi, RemoteMap, RemoteSequence,
                     decode_if_bytes, walk)
from .tabpage import Tabpage
from .window import Window
from ..compat import IS_PYTHON3
from ..util import format_exc_skip

__all__ = ('Nvim')


os_chdir = os.chdir


class Nvim(object):

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
    """

    @classmethod
    def from_session(cls, session):
        """Create a new Nvim instance for a Session instance.

        This method must be called to create the first Nvim instance, since it
        queries Nvim metadata for type information and sets a SessionHook for
        creating specialized objects from Nvim remote handles.
        """
        session.error_wrapper = lambda e: NvimError(e[1])
        channel_id, metadata = session.request(b'vim_get_api_info')

        if IS_PYTHON3:
            # decode all metadata strings for python3
            metadata = walk(decode_if_bytes, metadata)

        types = {
            metadata['types']['Buffer']['id']: Buffer,
            metadata['types']['Window']['id']: Window,
            metadata['types']['Tabpage']['id']: Tabpage,
        }

        return cls(session, channel_id, metadata, types)

    @classmethod
    def from_nvim(cls, nvim):
        """Create a new Nvim instance from an existing instance."""
        return cls(nvim._session, nvim.channel_id, nvim.metadata,
                   nvim.types, nvim._decode, nvim._err_cb)

    def __init__(self, session, channel_id, metadata, types,
                 decode=False, err_cb=None):
        """Initialize a new Nvim instance. This method is module-private."""
        self._session = session
        self.channel_id = channel_id
        self.metadata = metadata
        self.types = types
        self.api = RemoteApi(self, 'vim_')
        self.vars = RemoteMap(self, 'vim_get_var', 'vim_set_var')
        self.vvars = RemoteMap(self, 'vim_get_vvar', None)
        self.options = RemoteMap(self, 'vim_get_option', 'vim_set_option')
        self.buffers = Buffers(self)
        self.windows = RemoteSequence(self, 'vim_get_windows')
        self.tabpages = RemoteSequence(self, 'vim_get_tabpages')
        self.current = Current(self)
        self.session = CompatibilitySession(self)
        self.funcs = Funcs(self)
        self.error = NvimError
        self._decode = decode
        self._err_cb = err_cb

    def _from_nvim(self, obj, decode=None):
        if decode is None:
            decode = self._decode
        if type(obj) is ExtType:
            cls = self.types[obj.code]
            return cls(self, (obj.code, obj.data))
        if decode:
            obj = decode_if_bytes(obj, decode)
        return obj

    def _to_nvim(self, obj):
        if isinstance(obj, Remote):
            return ExtType(*obj.code_data)
        return obj

    def request(self, name, *args, **kwargs):
        r"""Send an API request or notification to nvim.

        It is rarely needed to call this function directly, as most API
        functions have python wrapper functions. The `api` object can
        be also be used to call API functions as methods:

            vim.api.err_write('ERROR\n', async=True)
            vim.current.buffer.api.get_mark('.')

        is equivalent to

            vim.request('vim_err_write', 'ERROR\n', async=True)
            vim.request('buffer_get_mark', vim.current.buffer, '.')


        Normally a blocking request will be sent.  If the `async` flag is
        present and True, a asynchronous notification is sent instead. This
        will never block, and the return value or error is ignored.
        """
        decode = kwargs.pop('decode', self._decode)
        args = walk(self._to_nvim, args)
        res = self._session.request(name, *args, **kwargs)
        return walk(self._from_nvim, res, decode=decode)

    def next_message(self):
        """Block until a message(request or notification) is available.

        If any messages were previously enqueued, return the first in queue.
        If not, run the event loop until one is received.
        """
        msg = self._session.next_message()
        if msg:
            return walk(self._from_nvim, msg)

    def run_loop(self, request_cb, notification_cb,
                 setup_cb=None, err_cb=None):
        """Run the event loop to receive requests and notifications from Nvim.

        This should not be called from a plugin running in the host, which
        already runs the loop and dispatches events to plugins.
        """
        if err_cb is None:
            err_cb = sys.stderr.write
        self._err_cb = err_cb

        def filter_request_cb(name, args):
            name = self._from_nvim(name)
            args = walk(self._from_nvim, args)
            try:
                result = request_cb(name, args)
            except Exception:
                msg = ("error caught in request handler '{} {}'\n{}\n\n"
                       .format(name, args, format_exc_skip(1, 5)))
                self._err_cb(msg)
                raise
            return walk(self._to_nvim, result)

        def filter_notification_cb(name, args):
            name = self._from_nvim(name)
            args = walk(self._from_nvim, args)
            try:
                notification_cb(name, args)
            except Exception:
                msg = ("error caught in notification handler '{} {}'\n{}\n\n"
                       .format(name, args, format_exc_skip(1, 5)))
                self._err_cb(msg)
                raise

        self._session.run(filter_request_cb, filter_notification_cb, setup_cb)

    def stop_loop(self):
        """Stop the event loop being started with `run_loop`."""
        self._session.stop()

    def with_decode(self, decode=True):
        """Initialize a new Nvim instance."""
        return Nvim(self._session, self.channel_id,
                    self.metadata, self.types, decode, self._err_cb)

    def ui_attach(self, width, height, rgb):
        """Register as a remote UI.

        After this method is called, the client will receive redraw
        notifications.
        """
        return self.request('ui_attach', width, height, rgb)

    def ui_detach(self):
        """Unregister as a remote UI."""
        return self.request('ui_detach')

    def ui_try_resize(self, width, height):
        """Notify nvim that the client window has resized.

        If possible, nvim will send a redraw request to resize.
        """
        return self.request('ui_try_resize', width, height)

    def subscribe(self, event):
        """Subscribe to a Nvim event."""
        return self.request('vim_subscribe', event)

    def unsubscribe(self, event):
        """Unsubscribe to a Nvim event."""
        return self.request('vim_unsubscribe', event)

    def command(self, string, **kwargs):
        """Execute a single ex command."""
        return self.request('vim_command', string, **kwargs)

    def command_output(self, string):
        """Execute a single ex command and return the output."""
        return self.request('vim_command_output', string)

    def eval(self, string, **kwargs):
        """Evaluate a vimscript expression."""
        return self.request('vim_eval', string, **kwargs)

    def call(self, name, *args, **kwargs):
        """Call a vimscript function."""
        return self.request('vim_call_function', name, args, **kwargs)

    def strwidth(self, string):
        """Return the number of display cells `string` occupies.

        Tab is counted as one cell.
        """
        return self.request('vim_strwidth', string)

    def list_runtime_paths(self):
        """Return a list of paths contained in the 'runtimepath' option."""
        return self.request('vim_list_runtime_paths')

    def foreach_rtp(self, cb):
        """Invoke `cb` for each path in 'runtimepath'.

        Call the given callable for each path in 'runtimepath' until either
        callable returns something but None, the exception is raised or there
        are no longer paths. If stopped in case callable returned non-None,
        vim.foreach_rtp function returns the value returned by callable.
        """
        for path in self.request('vim_list_runtime_paths'):
            try:
                if cb(path) is not None:
                    break
            except Exception:
                break

    def chdir(self, dir_path):
        """Run os.chdir, then all appropriate vim stuff."""
        os_chdir(dir_path)
        return self.request('vim_change_directory', dir_path)

    def feedkeys(self, keys, options='', escape_csi=True):
        """Push `keys` to Nvim user input buffer.

        Options can be a string with the following character flags:
        - 'm': Remap keys. This is default.
        - 'n': Do not remap keys.
        - 't': Handle keys as if typed; otherwise they are handled as if coming
               from a mapping. This matters for undo, opening folds, etc.
        """
        return self.request('vim_feedkeys', keys, options, escape_csi)

    def input(self, bytes):
        """Push `bytes` to Nvim low level input buffer.

        Unlike `feedkeys()`, this uses the lowest level input buffer and the
        call is not deferred. It returns the number of bytes actually
        written(which can be less than what was requested if the buffer is
        full).
        """
        return self.request('vim_input', bytes)

    def replace_termcodes(self, string, from_part=False, do_lt=True,
                          special=True):
        r"""Replace any terminal code strings by byte sequences.

        The returned sequences are Nvim's internal representation of keys,
        for example:

        <esc> -> '\x1b'
        <cr>  -> '\r'
        <c-l> -> '\x0c'
        <up>  -> '\x80ku'

        The returned sequences can be used as input to `feedkeys`.
        """
        return self.request('vim_replace_termcodes', string,
                            from_part, do_lt, special)

    def out_write(self, msg):
        """Print `msg` as a normal message."""
        return self.request('vim_out_write', msg)

    def err_write(self, msg, **kwargs):
        """Print `msg` as an error message."""
        return self.request('vim_err_write', msg, **kwargs)

    def quit(self, quit_command='qa!'):
        """Send a quit command to Nvim.

        By default, the quit command is 'qa!' which will make Nvim quit without
        saving anything.
        """
        try:
            self.command(quit_command)
        except IOError:
            # sending a quit command will raise an IOError because the
            # connection is closed before a response is received. Safe to
            # ignore it.
            pass

    def new_highlight_source(self):
        """Return new src_id for use with Buffer.add_highlight."""
        return self.current.buffer.add_highlight("", 0, src_id=0)

    def _error_wrapper(self, fn, call_point, *args, **kwargs):
        if fn is None:
            return None
        def handler():
            try:
                fn(*args, **kwargs)
            except Exception as err:
                msg = ("error caught while executing async callback:\n"
                       "{0!r}\n{1}\n \nthe call was requested at\n{2}"
                       .format(err, format_exc_skip(1, 5), call_point))
                self._err_cb(msg)
                raise
        return handler

    def async_call(self, fn, *args, **kwargs):
        """Schedule `fn` to be called by the event loop soon.

        This function is thread-safe, and is the only way code not
        on the main thread could interact with nvim api objects.

        This function can also be called in a synchronous
        event handler, just before it returns, to defer execution
        that shouldn't block neovim.
        """
        call_point = ''.join(format_stack(None, 5)[:-1])
        handler = self._error_wrapper(fn, call_point, *args, **kwargs)

        self._session.threadsafe_call(handler)

    def poll_fd(self, fd, on_readable=None, on_writable=None, greenlet=True):
        """
        Invoke callbacks when the fd is ready for reading and/or writing. if
        `on_readable` is not None, it should be callback, which will be invoked
        (with no arguments) when the fd is ready for writing. Similarily if
        `on_writable` is not None it will be invoked when the fd is ready for
        writing.

        Only one callback (of each kind) can be registered on the same fd at a
        time. If both readability and writability should be monitored, both
        callbacks must be registered by the same `poll_fd` call.

        By default, the function is invoked in a greenlet, just like a callback
        scheduled by async_call. 

        Returns a function that deactivates the callback(s).
        """
        call_point = ''.join(format_stack(None, 5)[:-1])
        on_readable = self._error_wrapper(on_readable, call_point)
        on_writable = self._error_wrapper(on_writable, call_point)
        return self._session.poll_fd(fd, on_readable, on_writable, greenlet)



class Buffers(object):

    """Remote NVim buffers.

    Currently the interface for interacting with remote NVim buffers is the
    `vim_get_buffers` msgpack-rpc function. Most methods fetch the list of
    buffers from NVim.

    Conforms to *python-buffers*.
    """

    def __init__(self, nvim):
        """Initialize a Buffers object with Nvim object `nvim`."""
        self._fetch_buffers = nvim.api.get_buffers

    def __len__(self):
        """Return the count of buffers."""
        return len(self._fetch_buffers())

    def __getitem__(self, number):
        """Return the Buffer object matching buffer number `number`."""
        for b in self._fetch_buffers():
            if b.number == number:
                return b
        raise KeyError(number)

    def __contains__(self, b):
        """Return whether Buffer `b` is a known valid buffer."""
        return isinstance(b, Buffer) and b.valid

    def __iter__(self):
        """Return an iterator over the list of buffers."""
        return iter(self._fetch_buffers())


class CompatibilitySession(object):

    """Helper class for API compatibility."""

    def __init__(self, nvim):
        self.threadsafe_call = nvim.async_call


class Current(object):

    """Helper class for emulating vim.current from python-vim."""

    def __init__(self, session):
        self._session = session
        self.range = None

    @property
    def line(self):
        return self._session.request('vim_get_current_line')

    @line.setter
    def line(self, line):
        return self._session.request('vim_set_current_line', line)

    @property
    def buffer(self):
        return self._session.request('vim_get_current_buffer')

    @buffer.setter
    def buffer(self, buffer):
        return self._session.request('vim_set_current_buffer', buffer)

    @property
    def window(self):
        return self._session.request('vim_get_current_window')

    @window.setter
    def window(self, window):
        return self._session.request('vim_set_current_window', window)

    @property
    def tabpage(self):
        return self._session.request('vim_get_current_tabpage')

    @tabpage.setter
    def tabpage(self, tabpage):
        return self._session.request('vim_set_current_tabpage', tabpage)


class Funcs(object):

    """Helper class for functional vimscript interface."""

    def __init__(self, nvim):
        self._nvim = nvim

    def __getattr__(self, name):
        return functools.partial(self._nvim.call, name)


class NvimError(Exception):
    pass
