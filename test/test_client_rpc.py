# -*- coding: utf-8 -*-
import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup

cid = vim.channel_id

@with_setup(setup=cleanup)
def test_call_and_reply():
    cmd = 'let g:result = send_call(%d, "client-call", [1,2,3])' % cid
    promise = vim.send_command(cmd)
    call = vim.next_message()
    eq(call.name, 'client-call')
    eq(call.arg, [1, 2, 3])
    call.reply([4, 5, 6])
    promise.wait()
    eq(vim.vars['result'], [4, 5, 6])


@with_setup(setup=cleanup)
def test_call_api_before_reply():
    cmd = 'let g:result = send_call(%d, "client-call", [1,2,3])' % cid
    promise = vim.send_command(cmd)
    call = vim.next_message()
    eq(call.arg, [1, 2, 3])
    vim.command('let g:result2 = [7, 8, 9]')
    call.reply(vim.vars['result2'])
    promise.wait()
    eq(vim.vars['result'], [7, 8, 9])


@with_setup(setup=cleanup)
def test_recursion():
    vim.vars['result1'] = 0
    vim.vars['result2'] = 0
    vim.vars['result3'] = 0
    vim.vars['result4'] = 0
    cmd = 'let g:result1 = send_call(%d, "client-call", %d)' % (cid, 2,)
    promise1 = vim.send_command(cmd)
    call1 = vim.next_message()
    arg = call1.arg * 2
    cmd = 'let g:result2 = send_call(%d, "client-call", %d)' % (cid, arg,)
    promise2 = vim.send_command(cmd)
    call2 = vim.next_message()
    arg = call2.arg * 2
    cmd = 'let g:result3 = send_call(%d, "client-call", %d)' % (cid, arg,)
    promise3 = vim.send_command(cmd)
    call3 = vim.next_message()
    arg = call3.arg * 2
    cmd = 'let g:result4 = send_call(%d, "client-call", %d)' % (cid, arg,)
    promise3 = vim.send_command(cmd)
    call4 = vim.next_message()
    # start responding the calls and asserting variable values
    eq(vim.vars['result4'], 0)
    call4.reply(call4.arg)
    eq(vim.vars['result4'], 16)
    eq(vim.vars['result3'], 0)
    call3.reply(call3.arg)
    eq(vim.vars['result3'], 8)
    eq(vim.vars['result2'], 0)
    call2.reply(call2.arg)
    eq(vim.vars['result2'], 4)
    eq(vim.vars['result1'], 0)
    call1.reply(call1.arg)
    eq(vim.vars['result1'], 2)
