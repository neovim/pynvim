import neovim

import pynvim.api


@neovim.plugin
class SimplePlugin:
    def __init__(self, nvim: pynvim.api.Nvim):
        self.nvim = nvim

    @neovim.command("SimpleHelloWorld")
    def hello_world(self) -> None:
        self.nvim.command("echom 'SimplePlugin: Hello World!'")
