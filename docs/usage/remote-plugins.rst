.. _remote-plugins:

Remote (new-style) plugins
==========================

Neovim allows Python 3 plugins to be defined by placing python files or packages in ``rplugin/python3/`` (in a ``runtimepath`` folder).
Python 2 rplugins are also supported and placed in ``rplugin/python/``,
but are considered deprecated.
Further added library features will only be available on Python 3.
Rplugins follow the structure of this example:

.. code-block:: python

   import neovim

   @neovim.plugin
   class TestPlugin(object):

       def __init__(self, nvim):
           self.nvim = nvim

       @neovim.function('TestFunction', sync=True)
       def testfunction(self, args):
           return 3

       @neovim.command('TestCommand', nargs='*', range='')
       def testcommand(self, args, range):
           self.nvim.current.line = ('Command with args: {}, range: {}'
                                     .format(args, range))

       @neovim.autocmd('BufEnter', pattern='*.py', eval='expand("<afile>")', sync=True)
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
The handler must then not make synchronous Neovim requests,
but it can make asynchronous requests, i.e. passing ``async=True``.

You need to run ``:UpdateRemotePlugins`` in Neovim for changes in the specifications to have effect.
For details see ``:help remote-plugin`` in Neovim.

If you are working on your plugin locally, it may be desirable to run the
plugin from a git repository directly without the need of installing or
symlinking it.
For local plugin development, it's a good idea to use an isolated vimrc:

.. code-block:: console

    $ cat vimrc
    let &runtimepath.=','.escape(expand('<sfile>:p:h'), '\,')

It will append your current work directory to the runtime path so Neovim is
able to find and load your plugin. You can now invoke Neovim:

.. code-block:: console

    $ nvim -u ./vimrc

Then just run command ``:UpdateRemotePlugins`` and your plugin should be up and
running.

In case you run into some issues, you can list loaded plugins:

.. code-block:: console

    :scriptnames
      1: ~/path/to/your/plugin-git-repo/vimrc
      2: /usr/share/nvim/runtime/filetype.vim
      3: /usr/share/nvim/runtime/ftplugin.vim
      4: /usr/share/nvim/runtime/indent.vim
    <trimmed for clarity>
     25: /usr/share/nvim/runtime/plugin/zipPlugin.vim
     26: ~/path/to/your/plugin-git-repo/plugin/lucid.vim

You can also inspect the ``runtimepath`` like this:

.. code-block:: console

    :set runtimepath
      runtimepath=~/.config/nvim,/etc/xdg/nvim,~/.local/share/nvim/site, <snip>
    ,~/g/path/to/your/plugin-git-repo


