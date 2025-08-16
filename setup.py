"""setup.py for pynvim."""

import os.path
import platform
import sys

__PATH__ = os.path.abspath(os.path.dirname(__file__))

from setuptools import setup

install_requires = [
    'msgpack>=1.0.0',
    'greenlet>=3.0; python_implementation != "PyPy"',
    'typing-extensions>=4.5; python_version < "3.12"',
]

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)

setup_requires = [
]

tests_require = [
    'pytest',
    'pytest_timeout',
]

docs_require = [
    'sphinx',
    'sphinx-rtd-theme',
]

extras_require = {
    'test': tests_require,
    'docs': docs_require,
}


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
      entry_points={
              'console_scripts': [
                  'pynvim-python=pynvim.python:main',
              ],
          },
      )
