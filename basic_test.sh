#!/bin/sh

# For every *.asn file, run it through test.py and pipe
# the result back to Python.
# This checks two things:
# 1) All steps of parsing and codegen run without exceptions
# 2) The end result is valid Python
# Note that it does not say anything about correctness or
# completeness of the generated code.

set -e

export PYTHONPATH=`pwd`
for f in testdata/*.asn;
do
    echo "Checking $f";
    rm -rf _testdir/
    mkdir -p _testdir/
    python asn1ate/test.py --outdir=_testdir --gen $f
    # Run python over _testdir/*.py
    for m in _testdir/*.py;
    do
        python $m
    done
done
