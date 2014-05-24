# -*- coding: utf-8 -*-
import os
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup


@with_setup(setup=cleanup)
def test_receiving_events():
    vim.command('call send_event(%d, "test-event", [1,2,3])' % vim.channel_id)
    events = vim.expect('test-event', lambda e: set(e[1]) == set([1, 2, 3]))
    eq(events, [['test-event', [1, 2, 3]]])
    vim.command('au FileType python call send_event(%d, "py!", bufnr("$"))' %
                vim.channel_id)
    vim.command('set filetype=python')
    events = vim.expect('py!', lambda e: e[1] == vim.current.buffer.number)
    eq(events, [['py!', vim.current.buffer.number]])


