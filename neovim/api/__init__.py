"""Nvim API subpackage.

This is a transition package. New projects should instead import pynvim.api.
"""
from pynvim import api
from pynvim.api import *

__all__ = api.__all__
