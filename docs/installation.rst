Installation
============

The Neovim's Python client supports Python 2.7, and 3.3 or later.

Using pip
---------

You can install the package without being root by adding the ``--user`` flag::

    pip2 install neovim
    pip3 install neovim

.. note::
  
    If you only use one of python2 or python3,
    it is enough to install that version.

If you follow Neovim master,
make sure to upgrade the ``python-client`` when you upgrade Neovim::

    pip2 install --upgrade neovim
    pip3 install --upgrade neovim

Install from source
-------------------

Clone the repository somewhere on your disk and enter to the repository:: 

    git clone https://github.com/neovim/python-client.git
    cd python-client

Now you can install it on your system::

    pip2 install .
    pip3 install .
