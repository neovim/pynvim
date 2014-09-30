from time import sleep
from random import random
from nose.tools import with_setup, eq_ as eq
from common import vim, cleanup
from threading import Thread, Timer


@with_setup(setup=cleanup)
def test_custom_messages():
    def produce(i):
        vim.session.post('custom-message', None)
        sleep(0.05 * random())

    count = 50
    for i in range(count):
        t = Thread(target=produce, args=(i,))
        t.daemon = True
        t.start()

    custom_messages = []
    while len(custom_messages) < 50:
        custom_messages.append(vim.session.next_message())

    eq(len(custom_messages), 50)


@with_setup(setup=cleanup)
def test_interrupt_from_another_thread():
    timer = Timer(0.5, lambda: vim.session.post('timeout'))
    timer.start()
    msg = vim.session.next_message()
    eq(msg[0], 'notification')
    eq(msg[1], 'timeout')
