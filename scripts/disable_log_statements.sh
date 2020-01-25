#!/bin/sh -e

cd pynvim
find -name '*.py' | xargs -i{} ../scripts/logging_statement_modifier.py {}
