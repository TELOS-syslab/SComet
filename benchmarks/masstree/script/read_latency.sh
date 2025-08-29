#!/bin/bash

FILE=${1:-1}

cd /home/wjy/SComet/benchmarks/Tailbench/tailbench/masstree
python3 ../utilities/parselats.py lats.bin > ${FILE}

