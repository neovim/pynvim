# -*- coding: utf-8 -*-
from nose.tools import with_setup, eq_ as eq
from test_common import vim, cleanup

cid = vim.channel_id


@with_setup(setup=cleanup)
def test_call_and_reply():
    def setup_cb():
        cmd = 'let g:result = rpcrequest(%d, "client-call", 1, 2, 3)' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [4, 5, 6])
        vim.stop_loop()

    def request_cb(name, args):
        eq(name, 'client-call')
        eq(args, [1, 2, 3])
        return [4, 5, 6]

    vim.run_loop(request_cb, None, setup_cb)


@with_setup(setup=cleanup)
def test_call_api_before_reply():
    def setup_cb():
        cmd = 'let g:result = rpcrequest(%d, "client-call2", 1, 2, 3)' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [7, 8, 9])
        vim.stop_loop()

    def request_cb(name, args):
        vim.command('let g:result2 = [7, 8, 9]')
        return vim.vars['result2']

    vim.run_loop(request_cb, None, setup_cb)

@with_setup(setup=cleanup)
def test_async_call():

    def request_cb(name, args):
        if name == "test-event":
            vim.vars['result'] = 17
        vim.stop_loop()

    # this would have dead-locked if not async
    vim.funcs.rpcrequest(vim.channel_id, "test-event", async=True)
    vim.run_loop(request_cb, None, None)
    eq(vim.vars['result'], 17)


@with_setup(setup=cleanup)
def test_recursion():
    def setup_cb():
        vim.vars['result1'] = 0
        vim.vars['result2'] = 0
        vim.vars['result3'] = 0
        vim.vars['result4'] = 0
        cmd = 'let g:result1 = rpcrequest(%d, "call", %d)' % (cid, 2,)
        vim.command(cmd)
        eq(vim.vars['result1'], 4)
        eq(vim.vars['result2'], 8)
        eq(vim.vars['result3'], 16)
        eq(vim.vars['result4'], 32)
        vim.stop_loop()

    def request_cb(name, args):
        n = args[0]
        n *= 2
        if n <= 16:
            if n == 4:
                cmd = 'let g:result2 = rpcrequest(%d, "call", %d)' % (cid, n,)
            elif n == 8:
                cmd = 'let g:result3 = rpcrequest(%d, "call", %d)' % (cid, n,)
            elif n == 16:
                cmd = 'let g:result4 = rpcrequest(%d, "call", %d)' % (cid, n,)
            vim.command(cmd)
        return n

    vim.run_loop(request_cb, None, setup_cb)
