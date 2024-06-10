# -*- coding: utf-8 -*-
from pynvim.api import Nvim


def test_receiving_events(vim: Nvim) -> None:
    vim.command('call rpcnotify(%d, "test-event", 1, 2, 3)' % vim.channel_id)
    event = vim.next_message()
    assert event[1] == 'test-event'
    assert event[2] == [1, 2, 3]
    vim.command('au FileType python call rpcnotify(%d, "py!", bufnr("$"))' %
                vim.channel_id)
    vim.command('set filetype=python')
    event = vim.next_message()
    assert event[1] == 'py!'
    assert event[2] == [vim.current.buffer.number]


def test_sending_notify(vim: Nvim) -> None:
    # notify after notify
    vim.command("let g:test = 3", async_=True)
    cmd = 'call rpcnotify(%d, "test-event", g:test)' % vim.channel_id
    vim.command(cmd, async_=True)
    event = vim.next_message()
    assert event[1] == 'test-event'
    assert event[2] == [3]

    # request after notify
    vim.command("let g:data = 'xyz'", async_=True)
    assert vim.eval('g:data') == 'xyz'


def test_async_error(vim: Nvim) -> None:
    # Invoke a bogus Ex command via notify (async).
    vim.command("lolwut", async_=True)
    event = vim.next_message()
    assert event[1] == 'nvim_error_event'


def test_broadcast(vim: Nvim) -> None:
    vim.command('call rpcnotify(0, "event1", 1, 2, 3)')
    vim.command('call rpcnotify(0, "event2", 4, 5, 6)')
    vim.command('call rpcnotify(0, "event2", 7, 8, 9)')
    event = vim.next_message()
    assert event[1] == 'event1'
    assert event[2] == [1, 2, 3]
    event = vim.next_message()
    assert event[1] == 'event2'
    assert event[2] == [4, 5, 6]
    vim.command('call rpcnotify(0, "event2", 10, 11, 12)')
    vim.command('call rpcnotify(0, "event1", 13, 14, 15)')
    msg = vim.next_message()
    assert msg[1] == 'event2'
    assert msg[2] == [7, 8, 9]
