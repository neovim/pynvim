from imp import find_module, load_module
import os, sys, inspect, logging, os.path
from traceback import format_exc
from .util import VimExit

logger = logging.getLogger(__name__)
debug, info, warn = (logger.debug, logger.info, logger.warn,)


class RedirectStream(object):
    def __init__(self, redirect_handler):
        self.redirect_handler = redirect_handler

    def write(self, data):
        self.redirect_handler(data)

    def writelines(self, seq):
        self.redirect_handler('\n'.join(seq))


class PluginHost(object):
    """
    Class that transforms the python interpreter into a plugin host for Neovim.
    It takes care of discovering plugins and routing events/calls sent by
    Neovim to the appropriate handlers(registered by plugins)
    """
    def __init__(self, vim, discovered_plugins=[]):
        self.vim = vim
        self.method_handlers = {}
        self.event_handlers = {}
        self.discovered_plugins = discovered_plugins
        self.installed_plugins = []
        sys.modules['vim'] = vim


    def __enter__(self):
        vim = self.vim
        info('install import hook/path')
        self.hook = path_hook(vim)
        sys.path_hooks.append(self.hook)
        vim.VIM_SPECIAL_PATH = '_vim_path_'
        sys.path.append(vim.VIM_SPECIAL_PATH)
        info('redirect sys.stdout and sys.stderr')
        self.saved_stdout = sys.stdout
        self.saved_stderr = sys.stderr
        sys.stdout = RedirectStream(lambda data: vim.out_write(data))
        sys.stderr = RedirectStream(lambda data: vim.err_write(data))
        debug('installing plugins')
        self.install_plugins()
        return self


    def __exit__(self, type, value, traceback):
        for plugin in self.installed_plugins:
            if hasattr(plugin, 'on_plugin_teardown'):
                plugin.on_plugin_teardown()
        vim = self.vim
        info('uninstall import hook/path')
        sys.path.remove(vim.VIM_SPECIAL_PATH)
        sys.path_hooks.remove(self.hook)
        info('restore sys.stdout and sys.stderr')
        sys.stdout = self.saved_stdout
        sys.stderr = self.saved_stderr


    def discover_plugins(self):
        loaded = set()
        for directory in discover_runtime_directories(self.vim):
            for name in os.listdir(directory):
                if not name.startswith(b'nvim_'):
                    continue
                name = os.path.splitext(name)[0]
                if name in loaded:
                    continue
                loaded.add(name)
                try:
                    discovered = find_module(name, [directory])
                except:
                    err_str = format_exc(5)
                    warn('error while searching module %s: %s', name, err_str)
                    continue
                debug('discovered %s', name)
                try:
                    file, pathname, description = discovered
                    module = load_module(name, file, pathname, description)
                    for name, value in inspect.getmembers(module, inspect.isclass):
                        if name.startswith('Nvim'):
                            self.discovered_plugins.append(value)
                    debug('loaded %s', name)
                except:
                    err_str = format_exc(5)
                    warn('error while loading module %s: %s', name, err_str)
                    continue
                finally:
                    file.close()

    def install_plugins(self):
        self.discover_plugins()
        vim = self.vim
        features = vim.api_metadata['features']
        registered = set()
        for plugin_class in self.discovered_plugins:
            cls_name = plugin_class.__name__
            debug('inspecting class %s', plugin_class.__name__)
            try:
                plugin = plugin_class(self.vim)
            except:
                err_str = format_exc(5)
                warn('constructor for %s failed: %s', cls_name, err_str)
                continue
            methods = inspect.getmembers(plugin, inspect.ismethod)
            debug('registering event handlers for %s', plugin_class.__name__)
            for method_name, method in methods:
                assert method.__self__ == plugin
                if not method_name.startswith('on_'):
                    continue
                # event handler
                event_name = method_name[3:]
                debug('registering %s event handler', event_name)
                if event_name not in self.event_handlers:
                    self.event_handlers[event_name] = [method]
                else:
                    self.event_handlers[event_name].append(
                        method.__get__(plugin, plugin_class))

            if hasattr(plugin, 'provides') and plugin.provides:
                for feature_name in plugin.provides:
                    if feature_name in registered:
                        raise Exception('A plugin already provides %s' %
                                        feature_name)
                    for method_name in features[feature_name]:
                        self.method_handlers[method_name] = getattr(plugin, method_name)
                    debug('registered %s as a %s provider',
                          plugin_class.__name__,
                          feature_name)
                    vim.register_provider(feature_name)
                    registered.add(feature_name)
            self.installed_plugins.append(plugin)


    def search_handler_for(self, name):
        for plugin in self.installed_plugins:
            methods = inspect.getmembers(plugin, inspect.ismethod)
            for method_name, method in methods:
                if method_name == name:
                    return method


    def on_request(self, name, args):
        if sys.version_info[0] > 2 and isinstance(name, bytes):
            # Python3 function names need to be Unicode, decode them
            # FIXME: for now I'm using utf8 here since &encoding
            # might not be right either
            name = name.decode('utf8')

        handler = self.method_handlers.get(name, None)
        if not handler:
            handler = self.search_handler_for(name)
            if handler:
                self.method_handlers[name] = handler
            else:
                msg = 'no method handlers for "%s" were found' % name
                debug(msg)
                raise Exception(msg)

        debug("running method handler for '%s %s'", name, args)
        rv = handler(*args)
        debug("method handler for '%s %s' returns: %s", name, args, rv)
        return rv


    def on_notification(self, name, args):
        handlers = self.event_handlers.get(name, None)
        if not handlers:
            debug("no event handlers registered for %s", name)
            return

        debug('running event handlers for %s', name)
        for handler in handlers:
            handler(*args)


    def on_error(self, err):
        warn('exiting due to error: %s', err)
        self.vim.loop_stop()


    def run(self):
        self.vim.loop_start(self.on_request,
                            self.on_notification,
                            self.on_error)


# This was copied/adapted from vim-python help
def path_hook(vim):
    def _get_paths():
        return discover_runtime_directories(vim)

    def _find_module(fullname, oldtail, path):
        idx = oldtail.find('.')
        if idx > 0:
            name = oldtail[:idx]
            tail = oldtail[idx+1:]
            fmr = find_module(name, path)
            module = load_module(fullname[:-len(oldtail)] + name, *fmr)
            return _find_module(fullname, tail, module.__path__)
        else:
            fmr = find_module(fullname, path)
            return load_module(fullname, *fmr)

    class VimModuleLoader(object):
        def __init__(self, module):
            self.module = module

        def load_module(self, fullname, path=None):
            return self.module

    class VimPathFinder(object):
        @classmethod
        def find_module(cls, fullname, path=None):
            try:
                return VimModuleLoader(
                    _find_module(fullname, fullname, path or _get_paths()))
            except ImportError:
                return None

        @classmethod
        def load_module(cls, fullname, path=None):
            return _find_module(fullname, fullname, path or _get_paths())

    def hook(path):
        if path == vim.VIM_SPECIAL_PATH:
            return VimPathFinder
        else:
            raise ImportError

    return hook


def discover_runtime_directories(vim):
    is_py3 = sys.version_info >= (3, 0)
    rv = []
    for path in vim.list_runtime_paths(decode_str=False):
        if not os.path.exists(path):
            continue
        path1 = os.path.join(path, b'pythonx')
        if is_py3:
            path2 = os.path.join(path, b'python3')
        else:
            path2 = os.path.join(path, b'python2')
        if os.path.exists(path1):
            rv.append(path1)
        if os.path.exists(path2):
            rv.append(path2)
    return rv
