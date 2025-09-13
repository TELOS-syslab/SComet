#!/bin/bash

# 使用方法: ./run_readers.sh target_string

if [ $# -ne 1 ]; then
    echo "Usage: $0 <target_string>"
    exit 1
fi

target=$1

# 遍历当前目录下所有包含 target 的目录
for dir in */; do
    if [[ "$dir" == *"$target"* && -d "$dir" ]]; then
        echo "Processing $dir ..."
        (
            cd "$dir" || exit
            python3 ../read_latency.py ./
            python3 ../read_JCT.py ./
        )
    fi
done
