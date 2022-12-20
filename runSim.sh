#!/bin/sh
set -x

for i in {20..26}; do
    python sim.py $i > sim_out/out_${i}.txt;
done
