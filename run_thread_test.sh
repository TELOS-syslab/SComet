#!/bin/bash

THREAD_TEST_PY_PATH="./thread_tests.py"
rm -rf thread_test*.json

SERVICES=("memcached")

THREAD_COUNTS=(8)
RPSS=(70000)

for i in {1..10}; do
    for SERVICE in "${SERVICES[@]}"; do
        for THREAD_COUNT in "${THREAD_COUNTS[@]}"; do
            for RPS in "${RPSS[@]}"; do
                echo "Running thread_test.py with parameters: $SERVICE $THREAD_COUNT (Iteration $i)"
                python3 "$THREAD_TEST_PY_PATH" "${1:-spec2017}" --lc "$SERVICE" --lc-threads "$THREAD_COUNT" --lc-rps "$RPS" -t "${2:-30}"
            done
        done
    done
done