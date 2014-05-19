import os
from util import RemoteSequence, RemoteMap, Current

os_chdir = os.chdir
os_fchdir = os.fchdir


class Vim(object):
    def foreach_rtp(self, cb):
        """
        Call the given callable for each path in 'runtimepath' until either 
        callable returns something but None, the exception is raised or there 
        are no longer paths. If stopped in case callable returned non-None, 
        vim.foreach_rtp function returns the value returned by callable.
        """
        for path in self.list_runtime_paths():
            try:
                if cb(path) != None:
                    break;
            except:
                break

    def chdir(self, dir_path):
        """
        Run os.chdir, then all appropriate vim stuff.
        """
        os_chdir(dir_path)
        self.change_directory(dir_path)

    def fchdir(self, dir_fd):
        """
        Run os.chdir, then all appropriate vim stuff.
        """
        os_fchdir(dir_fd)
        self.change_directory(os.getcwd())

    @property
    def buffers(self):
        if not hasattr(self, '_buffers'):
            self._buffers = RemoteSequence(self,
                                           self.Buffer,
                                           lambda: self.get_buffers())
        return self._buffers

    @property
    def windows(self):
        if not hasattr(self, '_windows'):
            self._windows = RemoteSequence(self,
                                           self.Window,
                                           lambda: self.get_windows())
        return self._windows

    @property
    def tabpages(self):
        if not hasattr(self, '_tabpages'):
            self._tabpages = RemoteSequence(self,
                                            self.Tabpage,
                                            lambda: self.get_tabpages())
        return self._tabpages

    @property
    def current(self):
        if not hasattr(self, '_current'):
            self._current = Current(self)
        return self._current

    @property
    def vars(self):
        if not hasattr(self, '_vars'):
            self._vars = RemoteMap(lambda k: self.get_var(k),
                                   lambda k, v: self.set_var(k, v))
        return self._vars

    @property
    def vvars(self):
        if not hasattr(self, '_vvars'):
            self._vvars = RemoteMap(lambda k: self.get_vvar(k),
                                    None)
        return self._vvars

    @property
    def options(self):
        if not hasattr(self, '_options'):
            self._options = RemoteMap(lambda k: self.get_option(k),
                                      lambda k, v: self.set_option(k, v))
        return self._options
