# -*- coding: utf-8 -*-
import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup

cid = vim.channel_id

@with_setup(setup=cleanup)
def test_python_command():
    vim.command('python vim.command("let set_by_python = [100,0]")')
    eq(vim.vars['set_by_python'], [100, 0])


@with_setup(setup=cleanup)
def test_python_nested_commands():
    nested = """python vim.command('python vim.command("python vim.command(\\'let set_by_nested_python = 555\\')")')"""
    vim.command(nested)
    eq(vim.vars['set_by_nested_python'], 555)


@with_setup(setup=cleanup)
def test_pyfile():
    fname = 'pyfile.py'
    text = 'vim.command("let set_by_pyfile = 123")'
    with open(fname, 'w') as f: f.write(text)
    vim.command('pyfile pyfile.py')
    eq(vim.vars['set_by_pyfile'], 123)
    os.unlink(fname)

@with_setup(setup=cleanup)
def test_pydo():
    # insert some text
    vim.command('normal iabc\ndef\nghi')
    eq(vim.current.buffer[:], ['abc', 'def', 'ghi'])
    # go to top and select and replace the first two lines
    vim.command('normal ggvj:pydo return linenr\n')
    eq(vim.current.buffer[:], ['1', '2', 'ghi'])

@with_setup(setup=cleanup)
def test_pyeval():
    vim.command('let python_expr = pyeval("[1, 2, 3]")')
    eq(vim.vars['python_expr'], [1, 2, 3])
