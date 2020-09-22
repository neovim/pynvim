Installation
============

The Neovim Python client supports Python 2.7, and 3.4 or later.

Using pip
---------

You can install the package without being root by adding the ``--user`` flag::

    python2 -m pip install --user pynvim
    python3 -m pip install --user pynvim

.. note::

    If you only use one of python2 or python3,
    it is enough to install that version.

If you follow Neovim HEAD, make sure to upgrade ``pynvim`` when you upgrade
Neovim::

    python2 -m pip install --upgrade pynvim
    python3 -m pip install --upgrade pynvim

Install from source
-------------------

Clone the repository somewhere on your disk and enter to the repository::

    git clone https://github.com/neovim/pynvim.git
    cd pynvim

Now you can install it on your system::

    python2 -m pip install .
    python3 -m pip install .
