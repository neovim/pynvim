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
        integers.append(vim.next_message().arg)

    for i in xrange(count):
        ok(i in integers)


@with_setup(setup=cleanup)
def test_custom_messages():
    def produce(i):
        if i % 2 == 0:
            str = 'call send_event(%d, "nvim-message", 0)' % (vim.channel_id)
            vim.command(str)
        else:
            vim.push_message('custom-message', None)
        sleep(0.05 * random())

    count = 50
    for i in xrange(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    nvim_messages = []
    custom_messages = []
    while len(nvim_messages) < 25 or len(custom_messages) < 25 :
        message = vim.next_message()
        if message.name == 'nvim-message':
            nvim_messages.append(message)
        elif message.name == 'custom-message':
            custom_messages.append(message)

    eq(len(nvim_messages), 25)
    eq(len(custom_messages), 25)
