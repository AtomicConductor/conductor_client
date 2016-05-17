#!/bin/bash -x

pushd $( dirname "${BASH_SOURCE[0]}" )
PATH=$PATH:./nsis/bin

mkdir -p ./Conductor

popd
