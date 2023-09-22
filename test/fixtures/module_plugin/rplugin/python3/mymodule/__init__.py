"""The `mymodule` package for the fixture module plugin."""
# pylint: disable=all

# Somehow the plugin might be using relative imports.
from .plugin import MyPlugin as MyPlugin

# ... or absolute import (assuming this is the root package)
import mymodule.plugin  # noqa: I100
assert mymodule.plugin.MyPlugin is MyPlugin
