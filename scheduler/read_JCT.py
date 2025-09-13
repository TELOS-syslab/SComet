import re
import sys
import glob
import os

# 给定的目录
log_dir = sys.argv[1]

time_pattern = re.compile(r"time ([0-9.]+):")
be_pattern = re.compile(r"\[be_container\d+@([\d.]+)\]")

# 搜索目录下所有 .log 文件
log_files = glob.glob(os.path.join(log_dir, "*.log"))

for logfile in log_files:
    print(f"Processing {logfile}...")

    current_time = None
    last_seen = {}   # ip -> last time we saw BE
    total_time = {}  # ip -> total BE running time

    with open(logfile, "r") as f:
        for line in f:
            # 更新当前时间
            m = time_pattern.match(line.strip())
            if m:
                current_time = float(m.group(1))
                continue

            # 发现 BE 容器
            m = be_pattern.search(line)
            if m and current_time is not None:
                ip = m.group(1)
                if ip in last_seen:
                    # 累加时间差
                    total_time[ip] = total_time.get(ip, 0.0) + (current_time - last_seen[ip])
                # 更新最近一次看到的时间
                last_seen[ip] = current_time

    # 输出结果
    for ip, t in total_time.items():
        print(f"{ip} runtime {t:.3f} seconds")
    print()
