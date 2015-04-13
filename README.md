### Python client to [Neovim](https://github.com/neovim/neovim)

[![Build Status](https://travis-ci.org/neovim/python-client.svg?branch=master)](https://travis-ci.org/neovim/python-client)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/neovim/python-client/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)
[![Code Coverage](https://scrutinizer-ci.com/g/neovim/python-client/badges/coverage.png?b=master)](https://scrutinizer-ci.com/g/neovim/python-client/?branch=master)

Library for scripting Nvim processes through its msgpack-rpc API.

#### Installation

```sh
pip install neovim
```

#### Usage through the python REPL

A number of different transports are supported, but the simplest way to get
started is with the python REPL. First, start Nvim with a known address (or
use the `$NVIM_LISTEN_ADDRESS` of a running instance): 

```sh
$ NVIM_LISTEN_ADDRESS=/tmp/nvim nvim
```

In another terminal, connect a python REPL to Nvim (note that the API is
similar to the one exposed by the [python-vim
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

The tests can be consulted for more examples.
