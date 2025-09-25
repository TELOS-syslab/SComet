#!/bin/bash

if [[ -z "$1" || "$1" -lt 1 ]]; then
    RUNS=1
else
    RUNS=$1
fi

for ((i=1; i<=RUNS; i++)); do
    echo "===== 第 $i 次运行 ====="

    python3 -u main.py test SComet 1 > SComet_test.log 2>&1
    latest_scomet=$(ls -dt SComet*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_scomet" && -d "$latest_scomet" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv SComet_test.log "${latest_scomet}/SComet_test_${timestamp}.log"
    else
        echo "no SComet found, skip move"
    fi

<<COMMENT
    python3 -u main.py test PARTIES 1 > PARTIES_test.log 2>&1
    latest_parties=$(ls -dt PARTIES*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_parties" && -d "$latest_parties" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv PARTIES_test.log "${latest_parties}/PARTIES_test_${timestamp}.log"
    else
        echo "no PARTIES found, skip move"
    fi


    python3 -u main.py test Paragon 1 > Paragon_test.log 2>&1
    latest_paragon=$(ls -dt Paragon*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_paragon" && -d "$latest_paragon" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv Paragon_test.log "${latest_paragon}/Paragon_test_${timestamp}.log"
    else
        echo "no Paragon found, skip move"
    fi

    python3 -u main.py test SComet_Paragon 1 > SComet_Paragon_test.log 2>&1
    latest_scomet_paragon=$(ls -dt SComet_Paragon*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_scomet_paragon" && -d "$latest_scomet_paragon" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv SComet_Paragon_test.log "${latest_scomet_paragon}/SComet_Paragon_test_${timestamp}.log"
    else
        echo "no SComet_Paragon found, skip move"
    fi
COMMENT


done

for ((i=1; i<=RUNS; i++)); do
    echo "===== 第 $i 次运行 ====="
<<COMMENT
    python3 -u main.py test SComet 0 > SComet_test.log 2>&1
    latest_scomet=$(ls -dt SComet*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_scomet" && -d "$latest_scomet" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv SComet_test.log "${latest_scomet}/SComet_test_${timestamp}.log"
    else
        echo "no SComet found, skip move"
    fi

    python3 -u main.py test PARTIES 0 > PARTIES_test.log 2>&1
    latest_parties=$(ls -dt PARTIES*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_parties" && -d "$latest_parties" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv PARTIES_test.log "${latest_parties}/PARTIES_test_${timestamp}.log"
    else
        echo "no PARTIES found, skip move"
    fi

    python3 -u main.py test Paragon 0 > Paragon_test.log 2>&1
    latest_paragon=$(ls -dt Paragon*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_paragon" && -d "$latest_paragon" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv Paragon_test.log "${latest_paragon}/Paragon_test_${timestamp}.log"
    else
        echo "no Paragon found, skip move"
    fi

    python3 -u main.py test SComet_Paragon 0 > SComet_Paragon_test.log 2>&1
    latest_scomet_paragon=$(ls -dt SComet_Paragon*/ 2>/dev/null | head -n1)
    if [[ -n "$latest_scomet_paragon" && -d "$latest_scomet_paragon" ]]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv SComet_Paragon_test.log "${latest_scomet_paragon}/SComet_Paragon_test_${timestamp}.log"
    else
        echo "no SComet_Paragon found, skip move"
    fi
COMMENT
done