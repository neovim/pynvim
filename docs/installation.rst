Installation
============

The Neovim Python client supports Python 3.7 or later.

Using uv or pipx
----------------

For automatic detection by Neovim, pynvim should be installed in a dedicated
Python virtual environment and the ``pynvim-python`` executable should be placed
on the ``PATH``.  The recommended approach for this is to use a tool like uv
(https://docs.astral.sh/uv/) or pipx (https://pipx.pypa.io/stable/); the
``--upgrade`` switch ensures installation of the latest version:

- Install using uv (recommended)::

    uv tool install --upgrade pynvim

- Install using pipx::

    pipx install --upgrade pynvim

**NOTE** For Neovim before v0.12.0, set the variable ``python3_host_prog`` in
``init.vim`` to point to ``pynvim-python``::

    let g:python3_host_prog = 'pynvim-python'

Using manually created Python virtual environment
-------------------------------------------------

Alternatively, you may manually create a Python virtual environment
(https://docs.python.org/3.13/library/venv.html)::

    python3 -m venv pynvim-venv

Then install pynvim into the virtual environment; the
``--upgrade`` switch ensures installation of the latest version::

- For Unix::

    pynvim-venv/bin/python -m pip install --upgrade pynvim

- For Windows::

    pynvim-venv\Scripts\python -m pip install --upgrade pynvim

Then copy the ``pynvim-python`` executable somewhere on the ``PATH``:

- For Unix::

    # Assuming `~/.local/bin` is on `PATH`:
    cp pynvim-venv/bin/pynvim-python ~/.local/bin/pynvim-python

- For Windows::

    REM Assuming `C:\apps` is on `PATH`:
    copy pynvim-venv\Scripts\pynvim-python.exe C:\apps\pynvim-python.exe

**NOTE** For Neovim before v0.12.0, set the variable ``python3_host_prog`` in
``init.vim`` to point to ``pynvim-python``::

    let g:python3_host_prog = 'pynvim-python'

Install from source
-------------------

Clone the repository somewhere on your disk and enter to the repository::

    git clone https://github.com/neovim/pynvim.git
    cd pynvim

Now you can install it following the instructions above, using ``.`` instead of
``pynvim``; the ``--upgrade`` switch ensures installation of the latest version:

- Install from source using uv::

    uv tool install --upgrade .

- Install from source using pipx::

    pipx install --upgrade .

- Install from source using manually created Python virtual environment:

  - Create ``pynvim-venv`` as above.

  - Install:

    - For Unix::

        pynvim-venv/bin/python -m pip install --upgrade .

    - For Windows::

        pynvim-venv\Scripts\python -m pip install --upgrade .

  - Copy ``pynvim-python`` executable as above.

**NOTE** For Neovim before v0.12.0, set the variable ``python3_host_prog`` in
``init.vim`` to point to ``pynvim-python``::

    let g:python3_host_prog = 'pynvim-python'

Upgrade pynvim when upgrading Neovim
------------------------------------

Make sure to upgrade ``pynvim`` when you upgrade Neovim.  Follow the previous
instructions; the ``--upgrade`` switch will ensure installation of the latest
version.

Explicitly choosing pynvim virtual environment
----------------------------------------------

As an alternative to exposing ``pynvim-python`` on ``PATH``, you may configure
Neovim to use a specific Python interpreter that has pynvim installed; this may
be useful when working on pynvim itself.

After installing into a virtual environment named ``pynvim-venv``, add the
following into Neovim's ``init.vim`` file:

- For Unix::

      let g:python3_host_prog = '/path/to/pynvim-venv/bin/python'

- For Windows::

      let g:python3_host_prog = 'c:\path\to\pynvim-venv\bin\python.exe'

Installing outside of a virtual environment is deprecated
---------------------------------------------------------

Installing into the per-user Python site package area is a deprecated practice
with recent Python versions.  For example, the following command fails on Ubuntu
24.04 with the error message ``error: externally-managed-environment``::

    pip install --user pynvim

Instead, always install into a virtual environment.
