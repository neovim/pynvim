import platform
import sys
import os

from setuptools import setup

install_requires = [
    'msgpack>=0.5.0',
]

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

setup_requires = [
] + pytest_runner,

tests_require = [
    'pytest>=3.4.0',
]

extras_require = {
    'pyuv': ['pyuv>=1.0.0'],
    'test': tests_require,
}

if sys.version_info < (3, 4):
    if os.name == 'nt':
        install_requires.append('pyuv>=1.0.0')
    else:
        # trollius is just a backport of 3.4 asyncio module
        install_requires.append('trollius')

if platform.python_implementation() != 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet')

setup(name='pynvim',
      version='0.4.3',
      description='Python client to neovim',
      url='http://github.com/neovim/pynvim',
      download_url='https://github.com/neovim/pynvim/archive/0.4.3.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='Apache',
      packages=['pynvim', 'pynvim.api', 'pynvim.msgpack_rpc',
                'pynvim.msgpack_rpc.event_loop', 'pynvim.plugin',
                'neovim', 'neovim.api'],
      install_requires=install_requires,
      setup_requires=setup_requires,
      tests_require=tests_require,
      extras_require=extras_require,
      zip_safe=False)
