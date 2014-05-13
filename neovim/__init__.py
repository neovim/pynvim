from client import Client
from uv_stream import UvStream

__all__ = ['connect']

def connect(address, port=None):
    client = Client(UvStream(address, port))
    client.discover_api()
    return client.vim
