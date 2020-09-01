.. _remote-plugins:

Remote (new-style) plugins
==========================

Neovim allows Python 3 plugins to be defined by placing python files or packages in ``rplugin/python3/`` (in a ``runtimepath`` folder).
Python 2 rplugins are also supported and placed in ``rplugin/python/``,
but are considered deprecated.
Further added library features will only be available on Python 3.
Rplugins follow the structure of this example:

.. code-block:: python

   import pynvim

   @pynvim.plugin
   class TestPlugin(object):

       def __init__(self, nvim):
           self.nvim = nvim

       @pynvim.function('TestFunction', sync=True)
       def testfunction(self, args):
           return 3

       @pynvim.command('TestCommand', nargs='*', range='')
       def testcommand(self, args, range):
           self.nvim.current.line = ('Command with args: {}, range: {}'
                                     .format(args, range))

       @pynvim.autocmd('BufEnter', pattern='*.py', eval='expand("<afile>")', sync=True)
       def on_bufenter(self, filename):
           self.nvim.out_write('testplugin is in ' + filename + '\n')

If ``sync=True`` is supplied Neovim will wait for the handler to finish
(this is required for function return values),
but by default handlers are executed asynchronously.

Normally async handlers (``sync=False``, the default)
are blocked while a synchronous handler is running.
This ensures that async handlers can call requests without Neovim confusing these requests with requests from a synchronous handler.
To execute an asynchronous handler even when other handlers are running,
add ``allow_nested=True`` to the decorator.
This handler must then not make synchronous Neovim requests,
but it can make asynchronous requests, i.e. passing ``async_=True``.

.. note::

    Plugin objects are constructed the first time any request of the class is
    invoked. Any error in ``__init__`` will be reported as an error from this
    first request. A well-behaved rplugin will not start executing until its
    functionality is requested by the user. Initialize the plugin when user
    invokes a command, or use an appropriate autocommand, e.g. FileType if it
    makes sense to automatically start the plugin for a given filetype. Plugins
    must not invoke API methods (or really do anything with non-trivial
    side-effects) in global module scope, as the module might be loaded as part
    of executing `UpdateRemotePlugins`.

You need to run ``:UpdateRemotePlugins`` in Neovim for changes in the specifications to have effect.
For details see ``:help remote-plugin`` in Neovim.

For local plugin development, it's a good idea to use an isolated vimrc:

.. code-block:: console

    cat vimrc
    let &runtimepath.=','.escape(expand('<sfile>:p:h'), '\,')

That appends the current directory to the Nvim runtime path so Nvim can
find your plugin. You can now invoke Neovim:

.. code-block:: console

    nvim -u ./vimrc

Then run ``:UpdateRemotePlugins`` and your plugin should be activated.

In case you run into some issues, you can list your loaded plugins from inside
Neovim by running ``:scriptnames`` like so.:

.. code-block:: vim

    :scriptnames
    1: ~/path/to/your/plugin-git-repo/vimrc
    2: /usr/share/nvim/runtime/filetype.vim
    ...
    25: /usr/share/nvim/runtime/plugin/zipPlugin.vim
    26: ~/path/to/your/plugin-git-repo/plugin/lucid.vim

You can also inspect the ``&runtimepath`` like this:

.. code-block:: vim

    :set runtimepath
    runtimepath=~/.config/nvim,/etc/xdg/nvim,~/.local/share/nvim/site,...,
    ,~/g/path/to/your/plugin-git-repo

    " Or alternatively
    :echo &rtp
