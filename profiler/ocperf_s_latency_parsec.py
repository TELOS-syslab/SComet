import os
import json
import sys
import subprocess
import time
import signal
import re

EVENT_DIR = "./pmu-events"

if len(sys.argv) > 1:
    benchmark_set = sys.argv[1]
else:
    print('Microbench name needed')
    exit(0)

test_time = 10
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

event_list = []

for filename in os.listdir(EVENT_DIR):
    if filename.endswith(".json") and "metrics" not in filename and 'experimental' not in filename:
        filepath = os.path.join(EVENT_DIR, filename)
        with open(filepath, 'r') as file:
            try:
                data = json.load(file)
                if "Events" in data.keys():
                    event_list += data["Events"]
            except json.JSONDecodeError as e:
                print(f"Error reading {filepath}: {e}")

# 筛选LATENCY事件和查找INST_RETIRED.ANY事件
latency_events = [e for e in event_list if e.get("Deprecated") == "0" and ('LOAD_LATENCY_GT_' in e["EventName"] or 'UNC_M_PRE_COUNT.' in e["EventName"] or 'CYCLES_MEM_ANY' in e["EventName"])]
print(f"LATENCY events count: {len(latency_events)}")

inst_event = None
for e in event_list:
    if e.get("EventName") == "INST_RETIRED.ANY" and e.get("Deprecated") == "0":
        inst_event = e
        break

if not inst_event:
    print("Error: INST_RETIRED.ANY event not found!")
    exit(1)

# 获取基准测试列表
benchmark_list = []
benchmark_path = f'../benchmarks/{benchmark_set}'
for root, dirs, files in os.walk(f'{benchmark_path}/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_list.append('.'.join(file.split('.')[0:-1]))
benchmark_list.sort()
print('benchmark list:')
print(benchmark_list)

# 调整perf_event_paranoid设置
subprocess.Popen("sudo sh -c 'echo -1 > /proc/sys/kernel/perf_event_paranoid'", shell=True).wait()

# 处理每个基准测试（采集+计算比值一体化）
for benchmark in benchmark_list:
    print(f"\nProcessing benchmark: {benchmark}")
    
    # 1. 采集INST_RETIRED.ANY事件
    inst_log = f"{benchmark_path}/log/{benchmark}_inst_retired.log"
    subprocess.Popen(f'rm -rf {inst_log}', shell=True).wait()
    
    print(f"Collecting INST_RETIRED.ANY for {benchmark}")
    subprocess.Popen('touch inst_temp.log', shell=True).wait()
    subprocess.Popen('rm -rf inst_temp.log', shell=True).wait()
    
    instr = f'HOME=/home/wjy /home/wjy/pmu-tools/ocperf stat -I 1 -e {inst_event["EventName"]} -o inst_temp.log bash {benchmark_path}/script/{benchmark}.sh'
    print(instr)
    
    cmd_result = subprocess.Popen(instr, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
    try:
        stdout_data, stderr_data = cmd_result.communicate(timeout=1)
        if 'event syntax error' in stderr_data:
            print(f"Event error, skipping {benchmark}: {stderr_data}")
            continue
    except subprocess.TimeoutExpired:
        pass

    print("Waiting for perf...")
    if test_time <= 0:
        cmd_result.wait()
    else:
        time.sleep(test_time)
        print(f"{test_time} second passed...")

    os.killpg(os.getpgid(cmd_result.pid), signal.SIGTERM)
    cmd_result.wait()

    # 解析INST_RETIRED.ANY采样数据（处理<not counted>）
    inst_result = {}
    try:
        with open("inst_temp.log", mode='r') as log_f:
            logs = log_f.readlines()
            for i in range(3, len(logs)):
                line = logs[i]
                if 'time' in line:
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                event_name = parts[2]
                if event_name not in inst_result:
                    inst_result[event_name] = []
                # 处理<not counted>情况
                count_str = parts[1].replace(',', '')
                if count_str == '<not counted>':
                    count = 0
                else:
                    try:
                        count = int(count_str)
                    except ValueError:
                        count = 0
                inst_result[event_name].append(count)
        subprocess.Popen('rm -rf inst_temp.log', shell=True).wait()
    except (FileNotFoundError, IOError) as e:
        print(f"Error reading inst_temp.log: {e}")
    
    # 写入INST_RETIRED.ANY日志
    with open(inst_log, 'a') as output_f:
        for event, counts in inst_result.items():
            output_f.write(f"{event:<50} { ' '.join(str(x) for x in counts) }\n")
    
    # 2. 采集LATENCY事件
    latency_log = f"{benchmark_path}/log/{benchmark}_latency_raw.log"
    subprocess.Popen(f'rm -rf {latency_log}', shell=True).wait()
    
    not_test = [1] * len(latency_events)
    while any(not_test):
        print(f"Remaining LATENCY events: {sum(not_test)}")
        subprocess.Popen('touch temp.log', shell=True).wait()
        subprocess.Popen('rm -rf temp.log', shell=True).wait()

        instr = 'HOME=/home/wjy /home/wjy/pmu-tools/ocperf stat -I 1'
        instr_print = 'HOME=/home/wjy /home/wjy/pmu-tools/ocperf stat --print'
        events = []
        msr_used = []
        
        for n in range(len(latency_events)):
            if len(events) >= 50:
                break
            if not_test[n] == 0:
                continue
            if latency_events[n].get("TakenAlone") == "0":
                msr = latency_events[n].get("MSRIndex")
                if msr in ["0", "0x00", None]:
                    not_test[n] = 0
                    events.append(latency_events[n])
                elif msr not in msr_used:
                    not_test[n] = 0
                    events.append(latency_events[n])
                    msr_used.append(msr)
                else:
                    continue
            elif len(events) == 0:
                not_test[n] = 0
                events.append(latency_events[n])
                break
            else:
                break

        for event in events:
            instr += f" -e {event.get('EventName')}"
            instr_print += f" -e {event.get('EventName')}"
        instr += f" -o temp.log bash {benchmark_path}/script/{benchmark}.sh"

        process = subprocess.run(instr_print, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        perf_events = []
        for full_event in process.stdout.strip().split('-e'):
            perf_events += re.split(r'name=|/', full_event.strip())

        cmd_result = subprocess.Popen(instr, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, preexec_fn=os.setsid)
        try:
            stdout_data, stderr_data = cmd_result.communicate(timeout=1)
            if 'event syntax error' in stderr_data:
                print(f"Event error, jump {instr}")
                continue
        except subprocess.TimeoutExpired:
            pass

        print(instr)
        print("Waiting for perf...")
        if test_time <= 0:
            cmd_result.wait()
        else:
            time.sleep(test_time)
            print(f"{test_time} second passed...")

        os.killpg(os.getpgid(cmd_result.pid), signal.SIGTERM)
        cmd_result.wait()

        # 解析LATENCY采样数据（处理<not counted>）
        latency_result = {}
        try:
            with open("temp.log", mode='r') as log_f:
                logs = log_f.readlines()
                for i in range(3, len(logs)):
                    if 'time' in logs[i]:
                        continue
                    parts = logs[i].split()
                    if len(parts) < 3:
                        continue
                    event_name = parts[2]
                    if event_name not in latency_result:
                        latency_result[event_name] = []
                    # 处理<not counted>情况
                    count_str = parts[1].replace(',', '')
                    if count_str == '<not counted>':
                        count = 0
                    else:
                        try:
                            count = int(count_str)
                        except ValueError:
                            count = 0
                    latency_result[event_name].append(count)
            subprocess.Popen('rm -rf temp.log', shell=True).wait()
        except (FileNotFoundError, IOError):
            pass
        
        # 写入LATENCY日志
        with open(latency_log, 'a') as output_f:
            for event, counts in latency_result.items():
                output_f.write(f"{event:<50} { ' '.join(str(x) for x in counts) }\n")
    
    print(f"Finished collecting raw data for {benchmark}")
    
    # 3. 计算当前基准测试的比值（修复日志读取逻辑）
    print(f"\nCalculating ratio for {benchmark}...")
    ratio_log = f"{benchmark_path}/log/{benchmark}_latency_ratio.log"
    
    if not os.path.exists(inst_log) or not os.path.exists(latency_log):
        print(f"Skipping ratio calculation for {benchmark}: missing raw data files")
        continue
    
    # 读取INST_RETIRED.ANY数据（严格匹配写入格式）
    inst_counts = {}
    try:
        with open(inst_log, 'r') as f:
            for line in f:
                # 关键修复：事件名固定左对齐50字符，因此前50字符为事件名（含填充空格）
                # 从第51字符开始为采样值（跳过事件名后的空格）
                event_name = line[0:50].strip()  # 提取事件名（去除填充空格）
                counts_str = line[50:].strip()   # 提取采样值部分
                if not event_name or not counts_str:
                    continue
                # 转换采样值为整数列表
                inst_counts[event_name] = [int(c) for c in counts_str.split()]
    except (FileNotFoundError, IOError, ValueError) as e:
        print(f"Error reading {inst_log}: {e}")
        continue
    
    if "inst_retired_any" not in inst_counts:
        print(f"Skipping ratio calculation for {benchmark}: no INST_RETIRED.ANY data")
        continue
    inst_samples = inst_counts["inst_retired_any"]
    
    # 读取LATENCY数据（同样匹配左对齐50字符的格式）
    latency_counts = {}
    try:
        with open(latency_log, 'r') as f:
            for line in f:
                event_name = line[0:50].strip()  # 提取事件名
                counts_str = line[50:].strip()   # 提取采样值
                if not event_name or not counts_str:
                    continue
                latency_counts[event_name] = [int(c) for c in counts_str.split()]
    except (FileNotFoundError, IOError, ValueError) as e:
        print(f"Error reading {latency_log}: {e}")
        continue
    
    # 计算比值
    ratio_result = {}
    for event, lat_samples in latency_counts.items():
        ratio_result[event] = []
        min_len = min(len(inst_samples), len(lat_samples))
        for i in range(min_len):
            if inst_samples[i] == 0:
                ratio_result[event].append(0.0)
            else:
                ratio_result[event].append(lat_samples[i] / inst_samples[i])
    
    # 写入比值日志（保持相同格式）
    with open(ratio_log, 'w') as f:
        for event, ratios in ratio_result.items():
            f.write(f"{event:<50} { ' '.join(f'{r:.6f}' for r in ratios) }\n")
    
    print(f"Ratio calculation completed for {benchmark}, results saved to {ratio_log}")

print("All benchmarks processed successfully!")