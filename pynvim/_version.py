"""Specifies pynvim version."""
# pylint: disable=consider-using-f-string

from types import SimpleNamespace

# see also setup.py
VERSION = SimpleNamespace(major=0, minor=5, patch=0, prerelease="")

# e.g. "0.5.0", "0.5.0.dev0" (PEP-440)
__version__ = '{major}.{minor}.{patch}'.format(**vars(VERSION))

if VERSION.prerelease:
    __version__ += '.' + VERSION.prerelease
