#!/bin/bash

t_values=("8,8")
r0_values=(100000 105000 110000 115000 120000)
r1_values=(100000 102000 104000 106000 108000 110000)
c_values=("7,7")
m_values=("40,50" "50,40")

num_loops=10
test_time=30

for t in "${t_values[@]}"; do
    for r0 in "${r0_values[@]}"; do
        for r1 in "${r1_values[@]}"; do
            for c in "${c_values[@]}"; do
                for m in "${m_values[@]}"; do
                    for ((i=0; i<num_loops; i++)); do
                        sudo python3 prove_row_buffer_interference2.py -T ${test_time} -t $t -r0 $r0 -r1 $r1 -c $c -m $m
                    done
                done
            done
        done
    done
done
