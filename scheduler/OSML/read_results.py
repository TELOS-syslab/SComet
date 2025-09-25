#!/usr/bin/env python3
import re
import sys
import glob
from statistics import mean
import os

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <name> <log_dir>")
    sys.exit(1)

name = sys.argv[1]       # benchmark 前缀，例如 masstree
log_dir = sys.argv[2]    # 日志目录

# 匹配时间
time_pattern = re.compile(r"^([\d.]+) seconds")
lat_pattern = re.compile(r"^(\S+)\s*-\s*(\S+)\s*-\s*.*% max load")
viol_pattern = re.compile(r"^Violation:\s*([\d.]+)")

benchmarks = {}

# 遍历日志
for logfile in glob.glob(f"{log_dir}/{name}.log"):
    time_value = None
    curr_bench = None
    curr_status = None

    with open(logfile, "r") as f:
        for line in f:
            line = line.strip()

            # 时间
            m = time_pattern.match(line)
            if m:
                time_value = m.group(1)
                continue

            # benchmark + latency
            m = lat_pattern.match(line)
            if m:
                curr_bench = m.group(1)
                latency_val = None if m.group(2) == "None" else m.group(2)
                curr_status = {
                    "latency": latency_val,
                    "violation": None,
                }
                if curr_bench not in benchmarks:
                    benchmarks[curr_bench] = []
                benchmarks[curr_bench].append(curr_status)
                continue

            # violation
            m = viol_pattern.match(line)
            if m and curr_status is not None:
                curr_status["violation"] = m.group(1)

    # 按 benchmark 输出单独文件
    for bench, runs in benchmarks.items():
        # latency
        with open(f"{logfile}_{bench}_latency.csv", "w") as f_lat:
            for r in runs:
                if r["latency"] is not None and r["latency"] != "nan":
                    f_lat.write(f"{r['latency']}\n")

        # violation
        with open(f"{logfile}_{bench}_violation.csv", "w") as f_viol:
            for r in runs:
                if r["violation"] is not None:
                    f_viol.write(f"{r['violation']}\n")

print("benchmark,avg_latency,avg_violation")
for bench, runs in benchmarks.items():
    latencies = [
        float(r["latency"]) for r in runs
        if r["latency"] is not None and r["latency"] != "nan"
    ]
    violations = [
        float(r["violation"]) for r in runs
        if r["violation"] is not None
    ]

    avg_latency = mean(latencies) if latencies else None
    avg_violation = mean(violations) if violations else None

    avg_latency_str = f"{avg_latency:.3f}" if avg_latency is not None else "None"
    avg_violation_str = f"{avg_violation:.3f}" if avg_violation is not None else "None"

    print(f"{bench},{avg_latency_str},{avg_violation_str}")

print("Per-benchmark latency and violation files generated.")
