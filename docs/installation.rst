Installation
============

The Neovim Python client supports Python 3.6 or later.

Using pip
---------

You can install the package without being root by adding the ``--user`` flag::

    pip3 install --user pynvim

If you follow Neovim HEAD, make sure to upgrade ``pynvim`` when you upgrade
Neovim::

    pip3 install --upgrade pynvim

Install from source
-------------------

Clone the repository somewhere on your disk and enter to the repository::

    git clone https://github.com/neovim/pynvim.git
    cd pynvim

Now you can install it on your system::

    pip3 install .
