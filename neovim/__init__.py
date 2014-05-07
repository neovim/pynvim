from client import Client
from uv_stream import UvStream

__all__ = ['Client', 'UvStream', 'c']

c = Client(UvStream('/tmp/neovim'))
c.discover_api()
