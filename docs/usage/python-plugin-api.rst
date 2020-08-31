Python Plugin API
=================

Neovim has a new mechanism for defining plugins,
as well as a number of extensions to the python API.
The API extensions are accessible no matter if the traditional ``:python`` interface or the new mechanism is used,
as discussed on :doc:`remote-plugins`.

Nvim API methods: ``vim.api``
-----------------------------

Exposes Neovim API methods.
For instance to call ``nvim_strwidth``:

.. code-block:: python

   result = vim.api.strwidth("some text")

Note the initial ``nvim_`` is not included.
Also, object methods can be called directly on their object:

.. code-block:: python

   buf = vim.current.buffer
   length = buf.api.line_count()

calls ``nvim_buf_line_count``.
Alternatively msgpack requests can be invoked directly:

.. code-block:: python

   result = vim.request("nvim_strwith", "some text")
   length = vim.request("nvim_buf_line_count", buf)

Both ``vim.api`` and ``vim.request`` can take an ``async_=True`` keyword argument
to instead send a msgpack notification. Nvim will execute the API method the
same way, but python will not wait for it to finish, so the return value is
unavailable.

Vimscript functions: ``vim.funcs``
----------------------------------

Exposes vimscript functions (both builtin and global user defined functions) as a python namespace.
For instance to set the value of a register:

.. code-block:: python

   vim.funcs.setreg('0', ["some", "text"], 'l')

These functions can also take the ``async_=True`` keyword argument, just like API
methods.

Lua integration
---------------

Python plugins can define and invoke lua code in Nvim's in-process lua
interpreter. This is especially useful in asynchronous contexts, where an async
event handler can schedule a complex operation with many api calls to be
executed by nvim without interleaved processing of user input or other event
sources (unless requested).

The recommended usage is the following pattern. First use ``vim.exec_lua(code)``
to define a module with lua functions:

.. code-block:: python

   vim.exec_lua("""
      local a = vim.api
      local function add(a,b)
          return a+b
      end

      local function buffer_ticks()
         local ticks = {}
         for _, buf in ipairs(a.nvim_list_bufs()) do
             ticks[#ticks+1] = a.nvim_buf_get_changedtick(buf)
         end
         return ticks
      end

      _testplugin = {add=add, buffer_ticks=buffer_ticks}
   """)

Alternatively, place the code in ``/lua/testplugin.lua`` under your plugin repo
root, and use ``vim.exec_lua("_testplugin = require('testplugin')")``.
In both cases, replace ``testplugin`` with a unique string based on your plugin
name.

Then, the module can be acessed as ``vim.lua._testplugin``.

.. code-block:: python

    mod = vim.lua._testplugin
    mod.add(2,3) # => 5
    mod.buffer_ticks() # => list of ticks

These functions can also take the ``async_=True`` keyword argument, just like API
methods.

It is also possible to pass arguments directly to a code block. Using
``vim.exec_lua(code, args...)``, the arguments will be available in lua as ``...``.

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

Some methods accept an ``async_`` keyword argument: ``vim.eval``,
``vim.command``, ``vim.request`` as well as the ``vim.funcs``, ``vim.api` and
``vim.lua``` wrappers.  When ``async_=True`` is passed the client will not wait
for Neovim to complete the request (which also means that the return value is
unavailable).
