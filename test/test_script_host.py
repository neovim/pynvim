# -*- coding: utf-8 -*-
import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup

cid = vim.channel_id


def host_setup():
    cleanup()
    # Spawn the python host
    vim.command(
        'let pyhost_id = ' +
        'rpcstart("python", ["-c", "import neovim; neovim.start_host()"])')
    ok(vim.eval('g:pyhost_id'))
    # Use rpc_request to wait for the host setup(rpc_spawn will return a channel
    # id but only after a while the channel will register handlers for python_*
    # methods)
    ok(vim.eval('rpcrequest(g:pyhost_id, "python_eval", "10")') == 10)
    # Verify the feature
    ok(vim.eval('has("python")'))
    # Import the vim module
    vim.command('python import vim')
    # Ensure the python host was updated accordingly
    ok(vim.eval('pyeval("vim.channel_id") == g:pyhost_id'))


def host_teardown():
    ok(vim.eval('rpcstop(g:pyhost_id)'))
    # After the channel is closed, the feature should not be available
    ok(not vim.eval('has("python")'))


@with_setup(setup=host_setup, teardown=host_teardown)
def test_python_command():
    vim.command('python vim.command("let set_by_python = [100,0]")')
    eq(vim.vars['set_by_python'], [100, 0])


@with_setup(setup=host_setup, teardown=host_teardown)
def test_python_nested_commands():
    nested = """python vim.command('python vim.command("python vim.command(\\'let set_by_nested_python = 555\\')")')"""
    vim.command(nested)
    eq(vim.vars['set_by_nested_python'], 555)


@with_setup(setup=host_setup, teardown=host_teardown)
def test_pyfile():
    fname = 'pyfile.py'
    text = 'vim.command("let set_by_pyfile = 123")'
    with open(fname, 'w') as f: f.write(text)
    vim.command('pyfile pyfile.py')
    eq(vim.vars['set_by_pyfile'], 123)
    os.unlink(fname)


@with_setup(setup=host_setup, teardown=host_teardown)
def test_pydo():
    # insert some text
    vim.command('normal iabc\ndef\nghi')
    eq(vim.current.buffer[:], ['abc', 'def', 'ghi'])
    # go to top and select and replace the first two lines
    vim.command('normal ggvj:pydo return linenr\n')
    eq(vim.current.buffer[:], ['1', '2', 'ghi'])


@with_setup(setup=host_setup, teardown=host_teardown)
def test_pyeval():
    vim.command('let python_expr = pyeval("[1, 2, 3]")')
    eq(vim.vars['python_expr'], [1, 2, 3])
