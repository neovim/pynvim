### Python client to [Neovim](https://github.com/neovim/neovim)

[![Build Status](https://travis-ci.org/neovim/python-client.svg?branch=master)](https://travis-ci.org/neovim/python-client)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/neovim/python-client/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)
[![Code Coverage](https://scrutinizer-ci.com/g/neovim/python-client/badges/coverage.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)

Implements support for python plugins in Nvim. Also works as a library for
connecting to and scripting Nvim processes through its msgpack-rpc API.

#### Installation

```sh
pip2 install neovim
pip3 install neovim
```

If you only use one of python2 or python3, it is enough to install that
version. You can install the package without being root by adding the `--user`
flag.

If you follow Neovim master, make sure to upgrade the python-client when you
upgrade neovim:
```sh
pip2 install --upgrade neovim
pip3 install --upgrade neovim
```

Alternatively, the master version could be installed by executing the following
in the root of this repository:
```sh
pip2 install .
pip3 install .
```

#### Python Plugin API

Neovim has a new mechanism for defining plugins, as well as a number of
extensions to the python API. The API extensions are accessible no matter if the
traditional `:python` interface or the new mechanism is used, as discussed
below.

* `vim.funcs` exposes vimscript functions (both builtin and global user defined
  functions) as a python namespace. For instance to set the value of the value
  of a register

    `vim.funcs.setreg('0', ["some", "text"], 'l')`

* The API is not thread-safe in general. However, `vim.async_call` allows a
  spawned thread to schedule code to be executed on the main thread. This method
  could also be called from `:python` or a synchronous request handler, to defer
  some execution that shouldn't block nvim.

    `:python vim.async_call(myfunc, args...)`

  Note that this code will still block the plugin host if it does long-running
  computations. Intensive computations should be done in a separate thread (or
  process), and `vim.async_call` can be used to send results back to nvim.

* Some methods accept an extra keyword-only argument `async`: `vim.eval`,
  `vim.command` as well as the `vim.funcs` wrappers. The python host will not
  wait for nvim to complete the request, which also means that the return value
  is unavailable.

#### Remote (new-style) plugins

Neovim allows python plugins to be defined by placing python files or packages
in `rplugin/python3/` (in a runtimepath folder). These follow the structure of
this example:

```python
import neovim

@neovim.plugin
class TestPlugin(object):

    def __init__(self, nvim):
        self.nvim = nvim

    @neovim.function("TestFunction", sync=True)
    def testfunction(self, args):
        return 3

    @neovim.command("TestCommand", range='', nargs='*')
    def testcommand(self, args, range):
        self.nvim.current.line = ('Command with args: {}, range: {}'
                                  .format(args, range))

    @neovim.autocmd('BufEnter', pattern='*.py', eval='expand("<afile>")', sync=True)
    def on_bufenter(self, filename):
        self.nvim.out_write("testplugin is in " + filename + "\n")
```

If `sync=True` is supplied nvim will wait for the handler to finish (this is
required for function return values), but by default handlers are executed
asynchronously.

You need to run `:UpdateRemotePlugins` in nvim for changes in the specifications
to have effect. For details see `:help remote-plugin` in nvim.

#### Development

If you change the code, you need to run
```sh
pip2 install .
pip3 install .
```
for the changes to have effect. Alternatively you could execute neovim
with the `$PYTHONPATH` environment variable
```
PYTHONPATH=/path/to/python-client nvim
```
But note this is not completely reliable as installed packages can appear before
`$PYTHONPATH` in the python search path.

You need to rerun this command if you have changed the code, in order for nvim
to use it for the plugin host.

To run the tests execute

```sh
nosetests
```

This will run the tests in an embedded instance of nvim.
If you want to test a different version than `nvim` in `$PATH` use
```sh
NVIM_CHILD_ARGV='["/path/to/nvim", "-u", "NONE", "--embed"]' nosetests
```

Alternatively, if you want to see the state of nvim, you could use

```sh
export NVIM_LISTEN_ADDRESS=/tmp/nvimtest
xterm -e "nvim -u NONE"&
nosetests
```

But note you need to restart nvim every time you run the tests! Substitute your
favorite terminal emulator for `xterm`.

#### Troubleshooting

You can run the plugin host in nvim with logging enabled to debug errors:
```
NVIM_PYTHON_LOG_FILE=logfile NVIM_PYTHON_LOG_LEVEL=DEBUG nvim
```
As more than one python host process might be started, the log filenames take
the pattern `logfile_PID` where `PID` is the process id.

If the host cannot start at all, the error could be found in `~/.nvimlog` if
`nvim` was compiled with logging.

#### Usage through the python REPL

A number of different transports are supported, but the simplest way to get
started is with the python REPL. First, start Nvim with a known address (or use
the `$NVIM_LISTEN_ADDRESS` of a running instance): 

```sh
$ NVIM_LISTEN_ADDRESS=/tmp/nvim nvim
```

In another terminal, connect a python REPL to Nvim (note that the API is similar
to the one exposed by the [python-vim
bridge](http://vimdoc.sourceforge.net/htmldoc/if_pyth.html#python-vim)):

```python
>>> from neovim import attach
# Create a python API session attached to unix domain socket created above:
>>> nvim = attach('socket', path='/tmp/nvim')
# Now do some work. 
>>> buffer = nvim.buffers[0] # Get the first buffer
>>> buffer[0] = 'replace first line'
>>> buffer[:] = ['replace whole buffer']
>>> nvim.command('vsplit')
>>> nvim.windows[1].width = 10
>>> nvim.vars['global_var'] = [1, 2, 3]
>>> nvim.eval('g:global_var')
[1, 2, 3]
```

You can embed neovim into your python application instead of binding to a
running neovim instance.

```python
>>> from neovim import attach
>>> nvim = attach('child', argv=["/bin/env", "nvim", "--embed"])
```

The tests can be consulted for more examples.
