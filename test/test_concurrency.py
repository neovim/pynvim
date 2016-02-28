from nose.tools import with_setup, eq_ as eq
from test_common import vim, cleanup
from threading import Timer


@with_setup(setup=cleanup)
def test_interrupt_from_another_thread():
    session = vim.session
    timer = Timer(0.5, lambda: session.threadsafe_call(lambda: session.stop()))
    timer.start()
    eq(vim.session.next_message(), None)


@with_setup(setup=cleanup)
def test_exception_in_threadsafe_call():
    # an exception in a threadsafe_call shouldn't crash the entire host
    vim.session.threadsafe_call(lambda: [vim.eval("3"), undefined_variable])
    vim.session.threadsafe_call(lambda: vim.session.stop())
    vim.session.run(None, None)
