# -*- coding: utf-8 -*-
from nose.tools import with_setup, eq_ as eq
from common import vim, cleanup

cid = vim.channel_id


@with_setup(setup=cleanup)
def test_call_and_reply():
    def notification_cb(name, args):
        eq(name, 'setup')
        cmd = 'let g:result = rpcrequest(%d, "client-call", 1, 2, 3)' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [4, 5, 6])
        vim.session.stop()

    def request_cb(name, args):
        eq(name, 'client-call')
        eq(args, [1, 2, 3])
        return [4, 5, 6]

    vim.session.post('setup')
    vim.session.run(request_cb, notification_cb)


@with_setup(setup=cleanup)
def test_call_api_before_reply():
    def notification_cb(name, args):
        eq(name, 'setup2')
        cmd = 'let g:result = rpcrequest(%d, "client-call2", 1, 2, 3)' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [7, 8, 9])
        vim.session.stop()

    def request_cb(name, args):
        eq(name, 'client-call2')
        eq(args, [1, 2, 3])
        vim.command('let g:result2 = [7, 8, 9]')
        return vim.vars['result2']

    vim.session.post('setup2')
    vim.session.run(request_cb, notification_cb)


@with_setup(setup=cleanup)
def test_recursion():
    def notification_cb(name, args):
        eq(name, 'setup3')
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
        vim.session.stop()

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

    vim.session.post('setup3')
    vim.session.run(request_cb, notification_cb)
