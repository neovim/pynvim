Python Plugin API
=================

Neovim has a new mechanism for defining plugins,
as well as a number of extensions to the python API.
The API extensions are accessible no matter if the traditional ``:python`` interface or the new mechanism is used,
as discussed on :docs:`Remote plugins`.

``vim.funcs``
-------------

Exposes vimscript functions (both builtin and global user defined functions) as a python namespace.
For instance to set the value of a register:

.. code-block:: python

   vim.funcs.setreg('0', ["some", "text"], 'l')

``vim.api``
-----------

Exposes Neovim API methods.
For instance to call ``nvim_strwidth``:

.. code-block:: python

   result = vim.api.strwidth("some text")

Note the initial ``nvim_`` is not included.
Also, object methods can be called directly on their object:

.. code-block:: python

   buf = vim.current.buffer
   len = buf.api.line_count()

calls ``nvim_buf_line_count``.
Alternatively msgpack requests can be invoked directly:

.. code-block:: python

   result = vim.request("nvim_strwith", "some text")
   len = vim.request("nvim_buf_line_count", buf)

Async calls
-----------

The API is not thread-safe in general.
However, ``vim.async_call`` allows a spawned thread to schedule code to be executed on the main thread.
This method could also be called from ``:python`` or a synchronous request handler,
to defer some execution that shouldn't block Neovim:

.. code-block:: vim

   :python vim.async_call(myfunc, args...)

Note that this code will still block the plugin host if it does long-running computations.
Intensive computations should be done in a separate thread (or process),
and ``vim.async_call`` can be used to send results back to Neovim.

Some methods accept an ``async`` keyword argument:
``vim.eval``, ``vim.command``, ``vim.request`` as well as the ``vim.funcs`` and ``vim.api`` wrappers.
When ``async=True`` is passed the client will not wait for Neovim to complete the request
(which also means that the return value is unavailable).
