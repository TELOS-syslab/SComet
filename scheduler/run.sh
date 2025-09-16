#!/bin/bash

for i in {1..10}; do
    echo "===== 第 $i 次运行 ====="

    python3 -u main.py test SComet > SComet_test.log 2>&1
    latest_scomet=$(ls -dt SComet*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_scomet" && -d "$latest_scomet" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv SComet_test.log "${latest_scomet}/SComet_test_${timestamp}.log"
    else
        echo "no SComet found, skip move"
    fi

    python3 -u main.py test PARTIES > PARTIES_test.log 2>&1
    latest_parties=$(ls -dt PARTIES*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_parties" && -d "$latest_parties" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv PARTIES_test.log "${latest_parties}/PARTIES_test_${timestamp}.log"
    else
        echo "no PARTIES found, skip move"
    fi

done