#!/bin/bash

for i in {1..1}; do
    echo "===== 第 $i 次运行 ====="

    python3 -u main.py test SComet > SComet_test.log 2>&1
    latest_scomet=$(ls -dt SComet*/ | head -n1)
    timestamp=$(date +"%Y%m%d_%H%M%S")
    mv SComet_test.log "${latest_scomet}/SComet_test_${timestamp}.log"

    python3 -u main.py test PARTIES > PARTIES_test.log 2>&1
    latest_parties=$(ls -dt PARTIES*/ | head -n1)
    timestamp=$(date +"%Y%m%d_%H%M%S")
    mv PARTIES_test.log "${latest_parties}/PARTIES_test_${timestamp}.log"


done
