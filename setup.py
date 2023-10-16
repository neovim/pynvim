"""setup.py for pynvim."""

import os.path
import platform
import sys

__PATH__ = os.path.abspath(os.path.dirname(__file__))

from setuptools import setup

install_requires = [
    'msgpack>=0.5.0',
]

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

setup_requires = [
] + pytest_runner

tests_require = [
    'pytest',
]

extras_require = {
    'pyuv': ['pyuv>=1.0.0'],
    'test': tests_require,
}

if platform.python_implementation() != 'PyPy':
    # pypy already includes an implementation of the greenlet module
    install_requires.append('greenlet>=3.0')

if sys.version_info < (3, 8):
    install_requires.append('typing-extensions')


# __version__: see pynvim/_version.py
with open(os.path.join(__PATH__, "pynvim/_version.py"),
          "r", encoding="utf-8") as fp:
    _version_env = {}
    exec(fp.read(), _version_env)  # pylint: disable=exec-used
    version = _version_env['__version__']


setup(name='pynvim',
      version=version,
      description='Python client for Neovim',
      url='http://github.com/neovim/pynvim',
      download_url=f'https://github.com/neovim/pynvim/archive/{version}.tar.gz',
      author='Neovim Authors',
      license='Apache',
      packages=['pynvim', 'pynvim.api', 'pynvim.msgpack_rpc',
                'pynvim.msgpack_rpc.event_loop', 'pynvim.plugin',
                'neovim', 'neovim.api'],
      python_requires=">=3.7",
      install_requires=install_requires,
      setup_requires=setup_requires,
      tests_require=tests_require,
      extras_require=extras_require,
      options={"bdist_wheel": {"universal": True}},
      )
