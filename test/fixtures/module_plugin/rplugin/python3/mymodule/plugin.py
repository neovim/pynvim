"""Actual implement lies here."""
import pynvim as neovim
import pynvim.api


@neovim.plugin
class MyPlugin:
    def __init__(self, nvim: pynvim.api.Nvim):
        self.nvim = nvim

    @neovim.command("ModuleHelloWorld")
    def hello_world(self) -> None:
        self.nvim.command("echom 'MyPlugin: Hello World!'")
