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

test_time = 300
if '-t' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-t') + 1])

# 确保有足够的权限
def set_perf_permissions():
    try:
        # 设置性能事件偏执级别为-1（允许非root用户访问）
        subprocess.run("sudo sh -c 'echo -1 > /proc/sys/kernel/perf_event_paranoid'", shell=True, check=True)
        # 设置I/O调度器为性能模式
        subprocess.run("sudo sh -c 'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'", shell=True, check=True)
        print("已设置性能监控权限")
    except subprocess.CalledProcessError as e:
        print(f"设置权限失败: {e}")
        print("请确保你有sudo权限并且系统允许修改这些参数")

set_perf_permissions()

# 加载事件列表
def load_events():
    event_list = []
    for filename in os.listdir(EVENT_DIR):
        if filename.endswith(".json") and "metrics" not in filename and 'experimental' not in filename:
            filepath = os.path.join(EVENT_DIR, filename)
            try:
                with open(filepath, 'r') as file:
                    data = json.load(file)
                    if "Events" in data:
                        event_list += data["Events"]
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error reading {filepath}: {e}")
    
    # 过滤事件
    filtered_events = []
    for event in event_list:
        if event.get("Deprecated") == "0":
            if ('LOAD_LATENCY_GT_' in event["EventName"] or 
                'UNC_M_PRE_COUNT.' in event["EventName"] or 
                'CYCLES_MEM_ANY' in event["EventName"]):
                filtered_events.append(event)
    
    print(f"已加载 {len(filtered_events)} 个有效事件")
    return filtered_events

event_list = load_events()

# 获取基准测试列表
def get_benchmarks(benchmark_set):
    benchmark_path = f'../benchmarks/{benchmark_set}'
    benchmark_list = []
    
    script_dir = os.path.join(benchmark_path, 'script')
    if not os.path.exists(script_dir):
        print(f"脚本目录不存在: {script_dir}")
        return []
    
    for file in os.listdir(script_dir):
        if file.endswith('.sh'):
            benchmark_list.append(file.rsplit('.', 1)[0])
    
    benchmark_list.sort()
    print('Benchmark列表:')
    print(benchmark_list)
    return benchmark_list

benchmark_list = get_benchmarks(benchmark_set)

# 检查事件是否有效
def check_event_validity(event_name):
    try:
        # 尝试使用ocperf stat测试事件
        result = subprocess.run(
            f"sudo /home/wjy/pmu-tools/ocperf stat -e {event_name} -x, sleep 1",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 检查输出中是否有错误信息
        if "invalid" in result.stderr.lower() or "unknown" in result.stderr.lower():
            return False
        return True
    except Exception as e:
        print(f"检查事件 {event_name} 有效性时出错: {e}")
        return False

# 执行单个基准测试
def run_benchmark(benchmark, benchmark_path, events, test_time):
    output_log = f'{benchmark_path}/log/{benchmark}_latency.log'
    temp_log = 'temp.log'
    
    # 创建日志文件
    os.makedirs(os.path.dirname(output_log), exist_ok=True)
    try:
        with open(output_log, 'w'):
            pass  # 清空文件
    except IOError as e:
        print(f"创建日志文件失败: {e}")
        return {}
    
    # 构建ocperf命令
    event_args = ' '.join(f"-e {event['EventName']}" for event in events)
    instr = f"sudo /home/wjy/pmu-tools/ocperf stat -I 1000 {event_args} -o {temp_log} bash {benchmark_path}/script/{benchmark}.sh"
    instr_print = f"sudo /home/wjy/pmu-tools/ocperf stat --print {event_args}"
    
    # 打印事件信息用于调试
    print(f"测试基准: {benchmark}")
    print(f"使用事件: {', '.join(e['EventName'] for e in events)}")
    print(f"执行命令: {instr}")
    
    # 先执行print命令检查事件
    try:
        print_result = subprocess.run(
            instr_print,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print("事件检查输出:")
        print(print_result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"事件检查失败: {e.stderr}")
        return {}
    
    # 执行基准测试
    try:
        print("开始执行基准测试...")
        process = subprocess.Popen(
            instr,
            shell=True,
            preexec_fn=os.setsid,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待指定时间或直到进程完成
        try:
            stdout, stderr = process.communicate(timeout=test_time)
            print(f"进程提前完成，返回码: {process.returncode}")
            if process.returncode != 0:
                print(f"标准错误输出: {stderr}")
        except subprocess.TimeoutExpired:
            print(f"{test_time}秒已过，终止进程")
            # 终止进程组
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
                print("进程已成功终止")
            except Exception as e:
                print(f"终止进程时出错: {e}")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
                    print("进程已被强制终止")
                except Exception as e2:
                    print(f"强制终止进程时出错: {e2}")
        
        # 读取并解析结果
        results = {}
        try:
            with open(temp_log, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or 'time' in line.lower():
                        continue
                    
                    parts = re.split(r'\s+', line)
                    if len(parts) < 3:
                        continue
                    
                    try:
                        value = int(parts[0].replace(',', ''))
                        event_name = parts[2]
                        results[event_name] = value
                    except (ValueError, IndexError):
                        continue
        except IOError as e:
            print(f"读取临时日志文件失败: {e}")
            return {}
        
        # 将结果写入最终日志
        try:
            with open(output_log, 'a') as f:
                f.write(f"# 运行时间: {time.ctime()}\n")
                for event_name, value in results.items():
                    f.write(f"{event_name:<50} {value}\n")
                f.write("\n")
        except IOError as e:
            print(f"写入结果日志失败: {e}")
        
        return results
    
    except Exception as e:
        print(f"执行基准测试时出错: {e}")
        return {}
    finally:
        # 清理临时文件
        if os.path.exists(temp_log):
            os.remove(temp_log)

# 主测试逻辑
for benchmark in benchmark_list:
    print(f"\n===== 测试基准: {benchmark} =====")
    benchmark_path = f'../benchmarks/{benchmark_set}'
    
    # 分组处理事件
    max_events_per_group = 10  # 减少每组事件数量
    event_groups = []
    current_group = []
    msr_used = set()
    
    for event in event_list:
        # 检查事件是否需要单独测量
        if event.get("TakenAlone") == "1":
            event_groups.append([event])
        else:
            # 检查MSR冲突
            msr_index = event.get("MSRIndex", "0")
            if msr_index != "0" and msr_index in msr_used:
                continue
            
            # 检查组大小
            if len(current_group) >= max_events_per_group:
                event_groups.append(current_group)
                current_group = []
                msr_used = set()
            
            current_group.append(event)
            if msr_index != "0":
                msr_used.add(msr_index)
    
    # 添加最后一组
    if current_group:
        event_groups.append(current_group)
    
    print(f"将事件分为 {len(event_groups)} 组")
    
    # 测试每组事件
    for i, events in enumerate(event_groups):
        print(f"\n--- 测试事件组 {i+1}/{len(event_groups)} ---")
        results = run_benchmark(benchmark, benchmark_path, events, test_time)
        
        # 检查是否所有值都是零
        if results and all(v == 0 for v in results.values()):
            print("警告: 所有事件值都是零，可能存在问题")
            # 尝试单独测试每个事件
            print("尝试单独测试每个事件...")
            for event in events:
                single_results = run_benchmark(benchmark, benchmark_path, [event], test_time)
                if single_results.get(event["EventName"], 0) == 0:
                    print(f"事件 {event['EventName']} 仍然返回零值")
                    # 检查事件有效性
                    if not check_event_validity(event["EventName"]):
                        print(f"事件 {event['EventName']} 可能无效或不被支持")
                else:
                    print(f"事件 {event['EventName']} 单独测试成功")