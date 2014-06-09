import os
from util import RemoteSequence, RemoteMap, Current

os_chdir = os.chdir
os_fchdir = os.fchdir


class Vim(object):
    @classmethod
    def initialize(self, vim, classes, channel_id):
        vim.buffers = RemoteSequence(vim,
                                     classes['buffer'],
                                     lambda: vim.get_buffers())
        vim.windows = RemoteSequence(vim,
                                     classes['window'],
                                     lambda: vim.get_windows())
        vim.tabpages = RemoteSequence(vim,
                                      classes['tabpage'],
                                      lambda: vim.get_tabpages())
        vim.current = Current(vim)
        vim.vars = RemoteMap(lambda k: vim.get_var(k),
                             lambda k, v: vim.set_var(k, v))
        vim.vvars = RemoteMap(lambda k: vim.get_vvar(k),
                              None)
        vim.options = RemoteMap(lambda k: vim.get_option(k),
                                lambda k, v: vim.set_option(k, v))
        vim.channel_id = channel_id

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
