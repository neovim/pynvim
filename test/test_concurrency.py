from nose.tools import with_setup, eq_ as eq
from test_common import vim, cleanup
from threading import Timer

@with_setup(setup=cleanup)
def test_interrupt_from_another_thread():
    timer = Timer(0.5, lambda: vim.async_call(lambda: vim.stop_loop()))
    timer.start()
    eq(vim.next_message(), None)

@with_setup(setup=cleanup)
def test_exception_in_threadsafe_call():
    # an exception in a threadsafe_call shouldn't crash the entire host
    msgs = []
    vim.async_call(lambda: [vim.eval("3"), undefined_variable])
    timer = Timer(0.5, lambda: vim.async_call(lambda: vim.stop_loop()))
    timer.start()
    vim.run_loop(None, None, err_cb=msgs.append)
    eq(len(msgs), 1)
    msgs[0].index('NameError')
    msgs[0].index('undefined_variable')
