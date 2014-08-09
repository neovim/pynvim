# -*- coding: utf-8 -*-
import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup

cid = vim.channel_id


@with_setup(setup=cleanup)
def test_call_and_reply():
    errors = []

    def notification_cb(name, args):
        eq(name, 'setup')
        cmd = 'let g:result = send_call(%d, "client-call", [1,2,3])' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [4, 5, 6])
        vim.loop_stop()

    def request_cb(name, args):
        eq(name, 'client-call')
        eq(args, [1, 2, 3])
        return [4, 5, 6]

    def error_cb(err):
        errors.append(err)
        vim.loop_stop()

    vim.post('setup')
    vim.loop_start(request_cb, notification_cb, error_cb)
    if errors:
        raise errors[0]


@with_setup(setup=cleanup)
def test_call_api_before_reply():
    errors = []

    def notification_cb(name, args):
        eq(name, 'setup2')
        cmd = 'let g:result = send_call(%d, "client-call2", [1,2,3])' % cid
        vim.command(cmd)
        eq(vim.vars['result'], [7, 8, 9])
        vim.loop_stop()

    def request_cb(name, args):
        eq(name, 'client-call2')
        eq(args, [1, 2, 3])
        vim.command('let g:result2 = [7, 8, 9]')
        return vim.vars['result2']

    def error_cb(err):
        errors.append(err)
        vim.loop_stop()

    vim.post('setup2')
    vim.loop_start(request_cb, notification_cb, error_cb)
    if errors:
        raise errors[0]


@with_setup(setup=cleanup)
def test_recursion():
    errors = []

    def notification_cb(name, args):
        eq(name, 'setup3')
        vim.vars['result1'] = 0
        vim.vars['result2'] = 0
        vim.vars['result3'] = 0
        vim.vars['result4'] = 0
        cmd = 'let g:result1 = send_call(%d, "call", %d)' % (cid, 2,)
        vim.command(cmd)
        eq(vim.vars['result1'], 4)
        eq(vim.vars['result2'], 8)
        eq(vim.vars['result3'], 16)
        eq(vim.vars['result4'], 32)
        vim.loop_stop()

    def request_cb(name, n):
        n *= 2
        if n <= 16:
            if n == 4:
                cmd = 'let g:result2 = send_call(%d, "call", %d)' % (cid, n,)
            elif n == 8:
                cmd = 'let g:result3 = send_call(%d, "call", %d)' % (cid, n,)
            elif n == 16:
                cmd = 'let g:result4 = send_call(%d, "call", %d)' % (cid, n,)
            vim.command(cmd)
        return n

    def error_cb(err):
        errors.append(err)
        vim.loop_stop()

    vim.post('setup3')
    vim.loop_start(request_cb, notification_cb, error_cb)
    if errors:
        raise errors[0]

