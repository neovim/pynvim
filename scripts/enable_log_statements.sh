#!/bin/sh -e

cd neovim
find -name '*.py' | xargs -i{} ../scripts/logging_statement_modifier.py --restore {}
