#!/bin/sh -e

./scripts/disable_log_statements.sh
python setup.py sdist upload -r pypi
./scripts/enable_log_statements.sh
