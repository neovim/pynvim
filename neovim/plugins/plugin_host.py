import inspect
import logging
import os
import os.path
import sys
from imp import find_module, load_module
from traceback import format_exc

from ..compat import IS_PYTHON3


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
    Class that transforms the python interpreter into a plugin host for
    Neovim. It takes care of discovering plugins and routing events/calls
    sent by Neovim to the appropriate handlers(registered by plugins)
    """
    def __init__(self, nvim, preloaded=[]):
        self.nvim = nvim
        self.method_handlers = {}
        self.event_handlers = {}
        self.discovered_plugins = list(preloaded)
        self.installed_plugins = []

    def __enter__(self):
        nvim = self.nvim
        info('install import hook/path')
        self.hook = path_hook(nvim)
        sys.path_hooks.append(self.hook)
        nvim.VIM_SPECIAL_PATH = '_vim_path_'
        sys.path.append(nvim.VIM_SPECIAL_PATH)
        info('redirect sys.stdout and sys.stderr')
        self.saved_stdout = sys.stdout
        self.saved_stderr = sys.stderr
        sys.stdout = RedirectStream(lambda data: nvim.out_write(data))
        sys.stderr = RedirectStream(lambda data: nvim.err_write(data))
        debug('installing plugins')
        self.install_plugins()
        return self

    def __exit__(self, type, value, traceback):
        for plugin in self.installed_plugins:
            if hasattr(plugin, 'on_teardown'):
                plugin.teardown()
        nvim = self.nvim
        info('uninstall import hook/path')
        sys.path.remove(nvim.VIM_SPECIAL_PATH)
        sys.path_hooks.remove(self.hook)
        info('restore sys.stdout and sys.stderr')
        sys.stdout = self.saved_stdout
        sys.stderr = self.saved_stderr

    def discover_plugins(self):
        loaded = set()
        for directory in discover_runtime_directories(self.nvim):
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
                    for name, value in inspect.getmembers(module,
                                                          inspect.isclass):
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
        nvim = self.nvim
        features = nvim.metadata['features']
        registered = set()
        for plugin_class in self.discovered_plugins:
            cls_name = plugin_class.__name__
            debug('inspecting class %s', plugin_class.__name__)
            try:
                plugin = plugin_class(self.nvim)
            except:
                err_str = format_exc(5)
                warn('constructor for %s failed: %s', cls_name, err_str)
                continue
            methods = inspect.getmembers(plugin, inspect.ismethod)
            debug('registering event handlers for %s', plugin_class.__name__)
            for method_name, method in methods:
                if not method_name.startswith('on_'):
                    continue
                # event handler
                # Store all handlers with bytestring keys, since thats how
                # msgpack will deserialize method names
                event_name = method_name[3:].encode('utf-8')
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
                        # encode for the same reason as above
                        enc_name = method_name.encode('utf-8')
                        self.method_handlers[enc_name] = getattr(
                            # Python 3 attributes need to be unicode instances
                            # so use `method_name` here
                            plugin, method_name)
                    debug('registered %s as a %s provider',
                          plugin_class.__name__,
                          feature_name)
                    nvim.register_provider(feature_name)
                    registered.add(feature_name)
            self.installed_plugins.append(plugin)

    def search_handler_for(self, name):
        for plugin in self.installed_plugins:
            methods = inspect.getmembers(plugin, inspect.ismethod)
            for method_name, method in methods:
                if method_name == name:
                    return method

    def on_request(self, name, args):
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

    def run(self):
        self.nvim.session.run(self.on_request, self.on_notification)


# This was copied/adapted from nvim-python help
def path_hook(nvim):
    def _get_paths():
        return discover_runtime_directories(nvim)

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
        if path == nvim.VIM_SPECIAL_PATH:
            return VimPathFinder
        else:
            raise ImportError

    return hook


def discover_runtime_directories(nvim):
    rv = []
    for path in nvim.list_runtime_paths():
        if not os.path.exists(path):
            continue
        path1 = os.path.join(path, b'pythonx')
        if IS_PYTHON3:
            path2 = os.path.join(path, b'python3')
        else:
            path2 = os.path.join(path, b'python2')
        if os.path.exists(path1):
            rv.append(path1)
        if os.path.exists(path2):
            rv.append(path2)
    return rv
