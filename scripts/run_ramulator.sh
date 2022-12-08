#!/bin/sh

config=""
trace=""

/ramulator-pim/ramulator/ramulator --config $config \
    --disable-perf-scheduling true --mode=cpu --stats host.stats \
    --trace $trace --core-org=outOrder --number-cores=4 \
    --trace-format=zsim --split-trace=true
