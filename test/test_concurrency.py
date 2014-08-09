from time import sleep
from random import random
from nose.tools import with_setup, eq_ as eq, ok_ as ok
from common import vim, cleanup
from threading import Thread


@with_setup(setup=cleanup)
def test_custom_messages():
    def produce(i):
        vim.post('custom-message', None)
        sleep(0.05 * random())

    count = 50
    for i in xrange(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    custom_messages = []
    while len(custom_messages) < 50:
        custom_messages.append(vim.next_message())

    eq(len(custom_messages), 50)
