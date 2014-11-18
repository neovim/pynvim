from nose.tools import with_setup, eq_ as eq
from common import vim, cleanup
from threading import Timer


@with_setup(setup=cleanup)
def test_interrupt_from_another_thread():
    session = vim.session
    timer = Timer(0.5, lambda: session.threadsafe_call(lambda: session.stop()))
    timer.start()
    eq(vim.session.next_message(), None)
