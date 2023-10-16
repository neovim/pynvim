import pynvim


def test_version() -> None:
    assert pynvim.__version__
    assert isinstance(pynvim.__version__, str)
    print(f"pynvim.__version__ = '{pynvim.__version__}'")
