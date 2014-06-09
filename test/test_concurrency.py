from time import sleep
from random import random
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup
from threading import Thread


@with_setup(setup=cleanup)
def test_concurrent_calls():
    vim.setup_done = True
    def produce(i):
        str = 'call send_event(%d, "integer", %d)' % (vim.channel_id, i,)
        sleep(0.05 * random())
        vim.command(str)

    vim.subscribe('integer')

    count = 50
    for i in xrange(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    integers = []
    while len(integers) < count:
        integers.append(vim.next_event()[1])

    vim.unsubscribe('integer')

    for i in xrange(count):
        ok(i in integers)

