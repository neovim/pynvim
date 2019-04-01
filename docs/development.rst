Development
===========

If you change the code, you need to run::

    pip2 install .
    pip3 install .

for the changes to have effect.
Alternatively you could execute Neovim with the ``$PYTHONPATH`` environment variable::

    PYTHONPATH=/path/to/pynvim nvim

But note this is not completely reliable,
as installed packages can appear before ``$PYTHONPATH`` in the python search path.

You need to rerun this command if you have changed the code,
in order for Neovim to use it for the plugin host.

To run the tests execute::

    python -m pytest

This will run the tests in an embedded instance of Neovim, with the current
directory added to ``sys.path``.

If you want to test a different version than ``nvim`` in ``$PATH`` use::

    NVIM_CHILD_ARGV='["/path/to/nvim", "-u", "NONE", "--embed", "--headless"]' pytest

Alternatively, if you want to see the state of nvim, you could use::

    export NVIM_LISTEN_ADDRESS=/tmp/nvimtest
    xterm -e "nvim -u NONE"&
    python -m pytest

But note you need to restart Neovim every time you run the tests!
Substitute your favorite terminal emulator for ``xterm``.

Troubleshooting
---------------

You can run the plugin host in Neovim with logging enabled to debug errors::

    NVIM_PYTHON_LOG_FILE=logfile NVIM_PYTHON_LOG_LEVEL=DEBUG nvim

As more than one Python host process might be started,
the log filenames take the pattern ``logfile_pyX_KIND``
where ``X`` is the major python version (2 or 3)
and ``KIND`` is either "rplugin" or "script" (for the ``:python[3]`` script interface).

If the host cannot start at all,
the error could be found in ``~/.nvimlog`` if ``nvim`` was compiled with logging.

Usage through the Python REPL
-----------------------------

A number of different transports are supported,
but the simplest way to get started is with the python REPL.
First, start Neovim with a known address (or use the ``$NVIM_LISTEN_ADDRESS`` of a running instance)::

    NVIM_LISTEN_ADDRESS=/tmp/nvim nvim

In another terminal,
connect a python REPL to Neovim (note that the API is similar to the one exposed by the `python-vim bridge`_):

.. code-block:: python

    >>> from pynvim import attach
    # Create a python API session attached to unix domain socket created above:
    >>> nvim = attach('socket', path='/tmp/nvim')
    # Now do some work. 
    >>> buffer = nvim.current.buffer # Get the current buffer
    >>> buffer[0] = 'replace first line'
    >>> buffer[:] = ['replace whole buffer']
    >>> nvim.command('vsplit')
    >>> nvim.windows[1].width = 10
    >>> nvim.vars['global_var'] = [1, 2, 3]
    >>> nvim.eval('g:global_var')
    [1, 2, 3]

.. _`python-vim bridge`: http://vimdoc.sourceforge.net/htmldoc/if_pyth.html#python-vim

You can embed Neovim into your python application instead of binding to a running neovim instance:

.. code-block:: python

    >>> from pynvim import attach
    >>> nvim = attach('child', argv=["/bin/env", "nvim", "--embed", "--headless"])

The tests can be consulted for more examples.
