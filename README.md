### Python client to [Neovim](https://github.com/neovim/neovim)

[![Build Status](https://travis-ci.org/neovim/python-client.svg?branch=master)](https://travis-ci.org/neovim/python-client)

Library aims to emulate the current python-vim interface through Neovim
msgpack-rpc API

#### Installation

```sh
pip install neovim
```

#### Usage

Start Neovim with a known address or query the value of $NEOVIM_LISTEN_ADRESS
after startup: 

```sh
$ NEOVIM_LISTEN_ADDRESS=/tmp/neovim nvim
```

Open the python REPL with another terminal connect to Neovim:

```
>>> import neovim
>>> vim = neovim.connect('/tmp/neovim')
>>> buffer = vim.buffers[0] # get the first buffer
>>> buffer[0] = 'replace first line'
>>> buffer[:] = ['replace whole buffer']
>>> vim.command('vsplit')
>>> vim.windows[1].width = 10
>>> vim.vars['global_var'] = [1, 2, 3]
>>> vim.eval('g:global_var')
[1, 2, 3]
```

See the test subdirectory for more examples

This is still alpha and incomplete, use only for testing purposes
