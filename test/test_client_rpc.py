# -*- coding: utf-8 -*-
import time


def test_call_and_reply(vim):
    cid = vim.channel_id
    def setup_cb():
        cmd = 'let g:result = rpcrequest(%d, "client-call", 1, 2, 3)' % cid
        vim.command(cmd)
        assert vim.vars['result'] == [4, 5, 6]
        vim.stop_loop()

    def request_cb(name, args):
        assert name == 'client-call'
        assert args == [1, 2, 3]
        return [4, 5, 6]

    vim.run_loop(request_cb, None, setup_cb)


def test_call_api_before_reply(vim):
    cid = vim.channel_id
    def setup_cb():
        cmd = 'let g:result = rpcrequest(%d, "client-call2", 1, 2, 3)' % cid
        vim.command(cmd)
        assert vim.vars['result'] == [7, 8, 9]
        vim.stop_loop()

    def request_cb(name, args):
        vim.command('let g:result2 = [7, 8, 9]')
        return vim.vars['result2']

    vim.run_loop(request_cb, None, setup_cb)

def test_async_call(vim):

    def request_cb(name, args):
        if name == "test-event":
            vim.vars['result'] = 17
        vim.stop_loop()

    # this would have dead-locked if not async
    vim.funcs.rpcrequest(vim.channel_id, "test-event", async_=True)
    vim.run_loop(request_cb, None, None)

    # TODO(blueyed): This sleep is required on Travis, where it hangs with
    # "Entering event loop" otherwise  (asyncio's EpollSelector._epoll.poll).
    time.sleep(0.1)

    assert vim.vars['result'] == 17


def test_recursion(vim):
    cid = vim.channel_id
    def setup_cb():
        vim.vars['result1'] = 0
        vim.vars['result2'] = 0
        vim.vars['result3'] = 0
        vim.vars['result4'] = 0
        cmd = 'let g:result1 = rpcrequest(%d, "call", %d)' % (cid, 2,)
        vim.command(cmd)
        assert vim.vars['result1'] == 4
        assert vim.vars['result2'] == 8
        assert vim.vars['result3'] == 16
        assert vim.vars['result4'] == 32
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
