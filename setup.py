import platform
import sys

from setuptools import setup

install_requires = [
    'msgpack-python',
]

if sys.version_info < (3, 4):
    # trollius is just a backport of 3.4 asyncio module
    install_requires.append('trollius')

if not platform.python_implementation() == 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet')

setup(name='neovim',
      version='0.0.17',
      description='Python client to neovim',
      url='http://github.com/neovim/python-client',
      download_url='https://github.com/neovim/python-client/archive/0.0.17.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='MIT',
      packages=['neovim'],
      install_requires=install_requires,
      zip_safe=False)
