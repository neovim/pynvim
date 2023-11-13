#!/bin/bash

set -e

cd pynvim
for f in $(find . -name '*.py'); do
    echo "Processing: $f"
    ../scripts/logging_statement_modifier.py "$f"
done
