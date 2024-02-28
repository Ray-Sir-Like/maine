#!/bin/bash

# Ignore E006 -- line length greater than 80 char

ROOT=$(cd "$(dirname $0)/.." && echo "$(pwd -P)")
find $ROOT -not -wholename \*.tox/\* -and -not -wholename \*.test/\* \
    -and -not -wholename \*.env/\* \
    -and -name \*.sh -print0 | xargs -0 bashate -v --ignore E006
