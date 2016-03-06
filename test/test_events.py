# -*- coding: utf-8 -*-
from nose.tools import with_setup, eq_ as eq
from test_common import vim, cleanup


@with_setup(setup=cleanup)
def test_receiving_events():
    vim.command('call rpcnotify(%d, "test-event", 1, 2, 3)' % vim.channel_id)
    event = vim.next_message()
    eq(event[1], 'test-event')
    eq(event[2], [1, 2, 3])
    vim.command('au FileType python call rpcnotify(%d, "py!", bufnr("$"))' %
                vim.channel_id)
    vim.command('set filetype=python')
    event = vim.next_message()
    eq(event[1], 'py!')
    eq(event[2], [vim.current.buffer.number])

@with_setup(setup=cleanup)
def test_sending_notify():
    # notify after notify
    vim.command("let g:test = 3", async=True)
    cmd = 'call rpcnotify(%d, "test-event", g:test)' % vim.channel_id
    vim.command(cmd, async=True)
    event = vim.next_message()
    eq(event[1], 'test-event')
    eq(event[2], [3])

    # request after notify
    vim.command("let g:data = 'xyz'", async=True)
    eq(vim.eval('g:data'), 'xyz')


@with_setup(setup=cleanup)
def test_broadcast():
    vim.subscribe('event2')
    vim.command('call rpcnotify(0, "event1", 1, 2, 3)')
    vim.command('call rpcnotify(0, "event2", 4, 5, 6)')
    vim.command('call rpcnotify(0, "event2", 7, 8, 9)')
    event = vim.next_message()
    eq(event[1], 'event2')
    eq(event[2], [4, 5, 6])
    event = vim.next_message()
    eq(event[1], 'event2')
    eq(event[2], [7, 8, 9])
    vim.unsubscribe('event2')
    vim.subscribe('event1')
    vim.command('call rpcnotify(0, "event2", 10, 11, 12)')
    vim.command('call rpcnotify(0, "event1", 13, 14, 15)')
    msg = vim.next_message()
    eq(msg[1], 'event1')
    eq(msg[2], [13, 14, 15])
