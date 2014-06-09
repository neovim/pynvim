from time import sleep
from random import random
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup
from threading import Thread


@with_setup(setup=cleanup)
def test_concurrent_calls():
    def produce(i):
        str = 'call send_event(%d, "integer", %d)' % (vim.channel_id, i,)
        sleep(0.05 * random())
        vim.command(str)

    count = 50
    for i in xrange(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    integers = []
    while len(integers) < count:
        integers.append(vim.next_event()[1])

    for i in xrange(count):
        ok(i in integers)


@with_setup(setup=cleanup)
def test_custom_events():
    def produce(i):
        if i % 2 == 0:
            str = 'call send_event(%d, "nvim-event", 0)' % (vim.channel_id)
            vim.command(str)
        else:
            vim.push_event('custom-event', None)
        sleep(0.05 * random())

    count = 50
    for i in xrange(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    nvim_events = []
    custom_events = []
    while len(nvim_events) < 25 or len(custom_events) < 25 :
        event = vim.next_event()
        if event[0] == 'nvim-event':
            nvim_events.append(event)
        elif event[0] == 'custom-event':
            custom_events.append(event)

    eq(len(nvim_events), 25)
    eq(len(custom_events), 25)
