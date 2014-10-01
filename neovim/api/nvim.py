"""Main Nvim interface."""
import os

from msgpack import ExtType

from .buffer import Buffer
from .common import (DecodeHook, Remote, RemoteMap, RemoteSequence,
                     SessionFilter, SessionHook, walk)
from ..compat import IS_PYTHON3
from .tabpage import Tabpage
from .window import Window


__all__ = ('Nvim')


os_chdir = os.chdir
os_fchdir = os.fchdir


class Nvim(object):

    """Class that represents a remote Nvim instance.

    This class is main entry point to Nvim remote API, it is a thin wrapper
    around Session instances.

    The constructor of this class must not be called directly. Instead, the
    `from_session` class method should be used to create the first instance
    from a raw `Session` instance.

    Subsequent instances for the same session can be created by calling the
    `with_hook` instance method and passing a SessionHook instance. This can
    be useful to have multiple `Nvim` objects that behave differently without
    one affecting the other.
    """

    @classmethod
    def from_session(cls, session):
        """Create a new Nvim instance for a Session instance.

        This method must be called to create the first Nvim instance, since it
        queries Nvim metadata for type information and sets a SessionHook for
        creating specialized objects from Nvim remote handles.
        """
        session.error_wrapper = lambda e: NvimError(e[1])
        channel_id, metadata = session.request('vim_get_api_info')

        if IS_PYTHON3:
            hook = DecodeHook()
            # decode all metadata strings for python3
            metadata = walk(hook.from_nvim, metadata, None, None, None)

        types = {
            metadata['types']['Buffer']['id']: Buffer,
            metadata['types']['Window']['id']: Window,
            metadata['types']['Tabpage']['id']: Tabpage,
        }

        return cls(session, channel_id, metadata).with_hook(ExtHook(types))

    def __init__(self, session, channel_id, metadata):
        """Initialize a new Nvim instance. This method is module-private."""
        self._session = session
        self.channel_id = channel_id
        self.metadata = metadata
        self.vars = RemoteMap(session, 'vim_get_var', 'vim_set_var')
        self.vvars = RemoteMap(session, 'vim_get_vvar', None)
        self.options = RemoteMap(session, 'vim_get_option', 'vim_set_option')
        self.buffers = RemoteSequence(session, 'vim_get_buffers')
        self.windows = RemoteSequence(session, 'vim_get_windows')
        self.tabpages = RemoteSequence(session, 'vim_get_tabpages')
        self.current = Current(session)
        self.error = NvimError

    def with_hook(self, hook):
        """Initialize a new Nvim instance."""
        return Nvim(SessionFilter(self.session, hook), self.channel_id,
                    self.metadata)

    @property
    def session(self):
        """Return the Session or SessionFilter for a Nvim instance."""
        return self._session

    def subscribe(self, event):
        """Subscribe to a Nvim event."""
        return self._session.request('vim_subscribe', event)

    def unsubscribe(self, event):
        """Unsubscribe to a Nvim event."""
        return self._session.request('vim_unsubscribe', event)

    def register_provider(self, name):
        """Register this process as a Nvim feature provider."""
        return self._session.request('vim_register_provider', name)

    def command(self, string):
        """Execute a single ex command."""
        return self._session.request('vim_command', string)

    def eval(self, string):
        """Evaluate a vimscript expression."""
        return self._session.request('vim_eval', string)

    def strwidth(self, string):
        """Return the number of display cells `string` occupies.

        Tab is counted as one cell.
        """
        return self._session.request('vim_strwidth', string)

    def list_runtime_paths(self):
        """Return a list of paths contained in the 'runtimepath' option."""
        return self._session.request('vim_list_runtime_paths')

    def foreach_rtp(self, cb):
        """Invoke `cb` for each path in 'runtimepath'.

        Call the given callable for each path in 'runtimepath' until either
        callable returns something but None, the exception is raised or there
        are no longer paths. If stopped in case callable returned non-None,
        vim.foreach_rtp function returns the value returned by callable.
        """
        for path in self._session.request('vim_list_runtime_paths'):
            try:
                if cb(path) is not None:
                    break
            except:
                break

    def chdir(self, dir_path):
        """Run os.chdir, then all appropriate vim stuff."""
        os_chdir(dir_path)
        return self._session.request('vim_change_directory', dir_path)

    def fchdir(self, dir_fd):
        """Run os.chdir, then all appropriate vim stuff."""
        os_fchdir(dir_fd)
        return self._session.request('vim_change_directory', os.getcwd())

    def feedkeys(self, keys, options=''):
        """Push `keys` to Nvim user input buffer.

        Options can be a string with the following character flags:
        - 'm': Remap keys. This is default.
        - 'n': Do not remap keys.
        - 't': Handle keys as if typed; otherwise they are handled as if coming
               from a mapping. This matters for undo, opening folds, etc.
        """
        return self._session.request('vim_feedkeys', keys, options)

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
        return self._session.request('vim_replace_termcodes', string,
                                     from_part, do_lt, special)

    def out_write(self, msg):
        """Print `msg` as a normal message."""
        return self._session.request('vim_out_write', msg)

    def err_write(self, msg):
        """Print `msg` as an error message."""
        return self._session.request('vim_err_write', msg)

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


class Current(object):

    """Helper class for emulating vim.current from python-vim."""

    def __init__(self, session):
        self._session = session

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


class ExtHook(SessionHook):
    def __init__(self, types):
        self.types = types
        super(ExtHook, self).__init__(from_nvim=self.from_ext,
                                      to_nvim=self.to_ext)

    def from_ext(self, obj, session, method, kind):
        if type(obj) is ExtType:
            cls = self.types[obj.code]
            return cls(session, (obj.code, obj.data))
        return obj

    def to_ext(self, obj, session, method, kind):
        if isinstance(obj, Remote):
            return ExtType(*obj.code_data)
        return obj


class NvimError(Exception):
    pass
