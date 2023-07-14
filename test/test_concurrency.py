from threading import Timer
from typing import List

from pynvim.api import Nvim


def test_interrupt_from_another_thread(vim: Nvim) -> None:
    timer = Timer(0.5, lambda: vim.async_call(lambda: vim.stop_loop()))
    timer.start()
    assert vim.next_message() is None


def test_exception_in_threadsafe_call(vim: Nvim) -> None:
    # an exception in a threadsafe_call shouldn't crash the entire host
    msgs: List[str] = []
    vim.async_call(
        lambda: [
            vim.eval("3"),
            undefined_variable  # type: ignore[name-defined] # noqa: F821
        ]
    )
    timer = Timer(0.5, lambda: vim.async_call(lambda: vim.stop_loop()))
    timer.start()
    vim.run_loop(None, None, err_cb=msgs.append)
    assert len(msgs) == 1
    msgs[0].index('NameError')
    msgs[0].index('undefined_variable')
