Pynvim: Python client to [Neovim](https://github.com/neovim/neovim)
===================================================================

[![Documentation Status](https://readthedocs.org/projects/pynvim/badge/?version=latest)](https://readthedocs.org/projects/pynvim/builds/)
[![Code coverage](https://codecov.io/gh/neovim/pynvim/branch/master/graph/badge.svg)](https://codecov.io/gh/neovim/pynvim)

Pynvim implements support for python plugins in Nvim. It also works as a library for
connecting to and scripting Nvim processes through its msgpack-rpc API.

Install
-------

Supports python 3.7 or later.

    pip3 install pynvim

You can install the package without being root by adding the `--user` flag.
Anytime you upgrade Neovim, make sure to upgrade pynvim as well:

    pip3 install --upgrade pynvim

Alternatively, you can install the development version by cloning this
repository and executing the following at the top level:

    pip3 install .

Python Plugin API
-----------------

Pynvim supports python _remote plugins_ (via the language-agnostic Nvim rplugin
interface), as well as _Vim plugins_ (via the `:python3` interface). Thus when
pynvim is installed Neovim will report support for the `+python3` Vim feature.

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

### Known Issues
- Vim evaluates `'v:<bool>'` to `<class 'bool'>`, whereas neovim evaluates to `<class 'str'>`. This is expected behaviour due to the way booleans are implemented in python as explained [here](https://github.com/neovim/pynvim/issues/523#issuecomment-1495502011).

Development
-----------

Use (and activate) a local virtualenv, for example:

    python3 -m virtualenv venv
    source venv/bin/activate

If you change the code, you must reinstall for the changes to take effect:

    pip install .

Use `pytest` to run the tests. Invoking with `python -m` prepends the current
directory to `sys.path` (otherwise `pytest` might find other versions!):

    python -m pytest

For details about testing and troubleshooting, see the
[development](http://pynvim.readthedocs.io/en/latest/development.html)
documentation.

### Usage from the Python REPL

A number of different transports are supported, but the simplest way to get
started is with the python REPL. First, start Nvim with a known address:

```sh
$ nvim --listen /tmp/nvim.sock
```

Or alternatively, note the `v:servername` address of a running Nvim instance.

In another terminal, connect a python REPL to Nvim (note that the API is similar
to the one exposed by the [python-vim
bridge](http://vimdoc.sourceforge.net/htmldoc/if_pyth.html#python-vim)):

```python
>>> import pynvim
# Create a session attached to Nvim's address (`v:servername`).
>>> nvim = pynvim.attach('socket', path='/tmp/nvim.sock')
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

You can embed Neovim into your python application instead of connecting to
a running Neovim instance.

```python
>>> import pynvim
>>> nvim = pynvim.attach('child', argv=["/usr/bin/env", "nvim", "--embed", "--headless"])
```

- The `--headless` argument tells `nvim` not to wait for a UI to connect.
- Alternatively, use `--embed` _without_ `--headless` if your client is a UI
  and you want `nvim` to wait for your client to `nvim_ui_attach` before
  continuing startup.

See the [tests](https://github.com/neovim/pynvim/tree/master/test) for more examples.

Release
-------

1. Create a release commit with title `Pynvim x.y.z`
   - list significant changes in the commit message
   - bump the version in `pynvim/_version.py`
2. Make a release on GitHub with the same commit/version tag and copy the message.
3. Run `scripts/disable_log_statements.sh`
4. Run `python -m build`
    - diff the release tarball `dist/pynvim-x.y.z.tar.gz` against the previous one.
5. Run `twine upload -r pypi dist/*`
    - Assumes you have a pypi account with permissions.
6. Run `scripts/enable_log_statements.sh` or `git reset --hard` to restore the working dir.
7. Bump up to the next development version in `pynvim/_version.py`, with `prerelease` suffix `dev0`.

License
-------

[Apache License 2.0](https://github.com/neovim/pynvim/blob/master/LICENSE)
