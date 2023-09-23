import platform
import sys

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

if platform.python_implementation() != 'PyPy':
    # pypy already includes an implementation of the greenlet module
    if sys.version_info >= (3, 12):
        install_requires.append('greenlet>=3.0.0rc3')
    else:
        install_requires.append('greenlet')

if sys.version_info < (3, 8):
    install_requires.append('typing-extensions')

setup(name='pynvim',
      version='0.4.3',
      description='Python client for Neovim',
      url='http://github.com/neovim/pynvim',
      download_url='https://github.com/neovim/pynvim/archive/0.4.3.tar.gz',
      author='Thiago de Arruda',
      author_email='tpadilha84@gmail.com',
      license='Apache',
      packages=['pynvim', 'pynvim.api', 'pynvim.msgpack_rpc',
                'pynvim.msgpack_rpc.event_loop', 'pynvim.plugin',
                'neovim', 'neovim.api'],
      python_requires=">=3.6",
      install_requires=install_requires,
      setup_requires=setup_requires,
      tests_require=tests_require,
      extras_require=extras_require,
      options={"bdist_wheel": {"universal": True}},
      )
