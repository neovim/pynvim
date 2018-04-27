### Pynvim: Python client to [Neovim](https://github.com/neovim/neovim)

[![Build Status](https://travis-ci.org/neovim/python-client.svg?branch=master)](https://travis-ci.org/neovim/python-client)
[![Documentation Status](https://readthedocs.org/projects/pynvim/badge/?version=latest)](http://pynvim.readthedocs.io/en/latest/?badge=latest)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/neovim/python-client/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)
[![Code Coverage](https://scrutinizer-ci.com/g/neovim/python-client/badges/coverage.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)

Pynvim implements support for python plugins in Nvim. It also works as a library for
connecting to and scripting Nvim processes through its msgpack-rpc API.

#### Installation

Supports python 2.7, and 3.4 or later.

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

Pynvim supports python _remote plugins_ (via the language-agnostic Nvim rplugin
interface), as well as _Vim plugins_ (via the `:python[3]` interface). Thus when
pynvim is installed Neovim will report support for the `+python[3]` Vim feature.

The rplugin interface allows plugins to handle vimL function calls as well as
defining commands and autocommands, and such plugins can operate asynchronously
without blocking nvim.  For details on the new rplugin interface, 
see the [Remote Plugin](http://pynvim.readthedocs.io/en/latest/usage/remote-plugins.html) documentation.

Pynvim defines some extensions over the vim python API:

* Builtin and plugin vimL functions are available as `nvim.funcs`
* API functions are available as `vim.api` and for objects such as `buffer.api`
* Lua functions can be defined using `vim.exec_lua` and called with `vim.lua`
* Support for thread-safety and async requests.

See the [Python Plugin API](http://pynvim.readthedocs.io/en/latest/usage/python-plugin-api.html) documentation for usage of this new functionality.

#### Development

If you change the code, you need to run
```sh
pip2 install .
pip3 install .
```
for the changes to have effect. For instructions of testing and troubleshooting,
see the [development](http://pynvim.readthedocs.io/en/latest/development.html) documentation.

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
>>> buffer = nvim.current.buffer # Get the current buffer
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
