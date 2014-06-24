from imp import new_module, find_module, load_module
import sys, logging, os.path
from traceback import format_exc

logger = logging.getLogger(__name__)
debug, warn = (logger.debug, logger.warn,)

class ScriptHost(object):
    """
    Plugin that provides the 'python' feature, emulating an environment for
    python code similar to the one provided by vim-python bindings.
    """
    def __init__(self, vim):
        self.provides = [
            'python_execute',
            'python_execute_file',
            'python_do_range',
            'python_eval'
        ]
        self.vim = vim
        # context where all code will run
        self.module = new_module('__main__')
        vim.script_context = self.module
        # it seems some plugins assume 'sys' is already imported, so do it now
        exec 'import sys' in self.module.__dict__

    def python_execute(self, script):
        exec script in self.module.__dict__

    def python_execute_file(self, file_path):
        execfile(file_path, self.module.__dict__)

    def python_do_range(self, arg):
        vim = self.vim
        start = arg[0] - 1
        stop = arg[1] - 1
        fname = '_vim_pydo'
        # define the function
        function_def = 'def %s(line, linenr):\n %s' % (fname, arg[2],)
        exec function_def in self.module.__dict__
        # get the function
        function = self.module.__dict__[fname]
        while start <= stop:
            # Process batches of 5000 to avoid the overhead of making multiple
            # API calls for every line. Assuming an average line length of 100
            # bytes, approximately 488 kilobytes will be transferred per batch,
            # which can be done very quickly in a single API call.
            sstart = start
            sstop = min(start + 5000, stop)
            lines = vim.current.buffer.get_slice(sstart, sstop, True, True)
            for i, line in enumerate(lines):
                linenr = i + sstart + 1
                result = str(function(line, linenr))
                if result:
                    lines[i] = result
            start = sstop + 1
            vim.current.buffer.set_slice(sstart, sstop, True, True, lines)
        # delete the function
        del self.module.__dict__[fname]

    def python_eval(self, arg):
        return eval(arg, self.module.__dict__)

