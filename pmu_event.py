import json
import os
import sys
import time
import docker
import subprocess
import shlex
import signal
import re
from config import *  # 导入 config.py 中的所有配置

# PMU事件相关配置
EVENT_DIR = "./profiler/pmu-events"
PMU_TOOLS_PATH = "/home/wjy/pmu-tools/ocperf"
PMU_EVENTS_PER_RUN = 50  # 每次运行监控的最大事件数

client = docker.from_env()

HOST_WORK_DIR = ROOT
CONTAINER_WORK_DIR = ROOT
SPEC2017_HOST_DIR = "/home/wjy/spec2017"
SPEC2017_CONTAINER_DIR = "/home/wjy/spec2017"

VOLUMES = {
    HOST_WORK_DIR: {'bind': CONTAINER_WORK_DIR, 'mode': 'rw'},
    SPEC2017_HOST_DIR: {'bind': SPEC2017_CONTAINER_DIR, 'mode': 'rw'}
}

# 任务到端口的映射
TASK_PORTS = {
    "memcached": 11211,
    "nginx": 80,
    "masstree": None  # Masstree不使用网络端口
}

available_benchmark_set = ['parsec-benchmark', 'stream', 'iperf', 'spec2017', 'ecp']
LC_tasks = ["memcached", "nginx", "masstree"]  # 默认LC任务

print("=== 命令行参数 ===")
print(sys.argv)

if '--lc' in sys.argv:
    try:
        idx = sys.argv.index('--lc')
        lc_task_arg = sys.argv[idx + 1]
        print(f"检测到 --lc 参数，值为: {lc_task_arg}")
        if lc_task_arg in LC_tasks:
            LC_tasks = [lc_task_arg]
            print(f"LC_tasks 更新为: {LC_tasks}")
        else:
            print(f"错误：任务 '{lc_task_arg}' 不在支持列表中 ({LC_tasks})")
            sys.exit(1)
    except IndexError:
        print("--lc 参数缺少任务名称")
        sys.exit(1)
else:
    LC_tasks = [LC_tasks[0]]
    print(f"未指定 --lc，使用默认任务: {LC_tasks}")

print("=== LC任务列表 ===")
print(LC_tasks)


benchmark_set = "spec2017"
benchmark_list = ["500.perlbench_r", "502.gcc_r"]

# benchmark_list = ["519.lbm_r", "507.cactuBSSN_r", "500.perlbench_r", "502.gcc_r", "503.bwaves_r", "505.mcf_r", "508.namd_r", "510.parest_r", "520.omnetpp_r", "523.xalancbmk_r", "557.xz_r", "baseline"]
# benchmark_list = ["519.lbm_r", "511.povray_r", "521.wrf_r", "525.x264_r","526.blender_r", "527.cam4_r", "531.deepsjeng_r", "538.imagick_r", "541.leela_r", "544.nab_r", "548.exchange2_r", "549.fotonik3d_r", "554.roms_r"]
# benchmark_list = ["519.lbm_r", "507.cactuBSSN_r", "500.perlbench_r", "502.gcc_r", "503.bwaves_r", "505.mcf_r", "508.namd_r", "510.parest_r", "511.povray_r", "520.omnetpp_r", "521.wrf_r", "523.xalancbmk_r", "525.x264_r","526.blender_r", "527.cam4_r", "531.deepsjeng_r", "538.imagick_r", "541.leela_r", "544.nab_r", "548.exchange2_r", "549.fotonik3d_r", "554.roms_r", "557.xz_r", "baseline"]
# benchmark_set = "parsec-benchmark"
# benchmark_list = [
#     "blackscholes", "bodytrack", "facesim", "ferret",
#     "fluidanimate", "freqmine", "raytrace", "swaptions",
#     "vips", "x264", "baseline"
# ]



test_time = 60
if '-T' in sys.argv:
    test_time = int(sys.argv[sys.argv.index('-T') + 1])

# 线程配置：前两个为LC任务线程数，最后一个为BE任务线程数
threads = [8, 8, 24]
if '-t' in sys.argv:
    threads = sys.argv[sys.argv.index('-t') + 1].split(',')
    threads = [int(t) for t in threads]
LC_threads = threads[:-1]
BE_threads = threads[-1]

# core = []
# for i in range(len(threads)):
#     start = sum(threads[0:i])
#     end = sum(threads[0:i+1])
#     core_str = ','.join(CPU_cores['NUMA0'][start:end])
#     print(f"分配核心 {i}: {core_str}")
#     core.append(core_str)

core = []
current_start = 0  # 从CPU核心0开始分配

for i in range(len(threads)-1, -1, -1):
    thread_count = threads[i]  # 当前线程组的线程数量
    start = current_start
    end = start + thread_count  # 计算结束索引
    
    # 从前往后分配核心
    core_str = ','.join(CPU_cores['NUMA0'][start:end])
    print(f"分配核心 {i}: {core_str}")
    core.append(core_str)
    
    current_start = end  # 更新下一组的起始位置

# 如果需要保持core列表与threads原始顺序对应，可反转结果
core.reverse()

LC_rps = []
if '-r' in sys.argv:
    LC_rps = sys.argv[sys.argv.index('-r') + 1].split(',')
    LC_rps = [int(r) for r in LC_rps]
    if len(LC_rps) != 1:
        print("错误：-r 参数应提供单个值", file=sys.stderr)
        sys.exit(1)
else:
    LC_rps = [59000]  # 默认值

cache_ways = [7, 7, 1]
if '-c' in sys.argv:
    cache_ways = sys.argv[sys.argv.index('-c') + 1].split(',')
    cache_ways = [int(c) for c in cache_ways]

memory_bandwidth_ratio = [50, 40, 10]
if '-m' in sys.argv:
    memory_bandwidth_ratio = sys.argv[sys.argv.index('-m') + 1].split(',')
    memory_bandwidth_ratio = [int(m) for m in memory_bandwidth_ratio]

# 初始化硬件资源隔离
def initialize_hardware_isolation():
    print("初始化硬件资源隔离...")
    try:
        subprocess.run('sudo rm -rf /var/lock/libpqos', shell=True, check=True)
        subprocess.run("sudo pqos -R", shell=True, check=True)
        
        check_cmd = "ps aux | grep pqos | grep -v grep"
        result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            subprocess.run("sudo pkill -f pqos", shell=True, check=True)
            print("pqos 进程已终止")
        else:
            print("未发现运行中的 pqos 进程")
        
        total_ways = get_cache_ways()
        print(f"系统 LLC 总路数: {total_ways}")
        
        cos_llc_masks = []
        start_bit = 0
        for ways in cache_ways:
            if ways:
                mask = ((1 << ways) - 1) << start_bit
                cos_llc_masks.append(f'0x{mask:0{total_ways//4}x}')
                start_bit += ways
            else:
                cos_llc_masks.append('0x0')
        
        for i in range(len(cos_llc_masks)):
            if cos_llc_masks[i] != '0x0':
                print(f"COS{i} LLC Mask: {cos_llc_masks[i]}, MBA: {memory_bandwidth_ratio[i]}%")
                cos_cmd = f'sudo pqos -e "llc:{i}={cos_llc_masks[i]};mba:{i}={memory_bandwidth_ratio[i]}"'
                print(f"执行: {cos_cmd}")
                subprocess.run(cos_cmd, shell=True, check=True)
        
        return cos_llc_masks
    except Exception as e:
        print(f"硬件隔离失败: {e}")
        return [None]*len(cache_ways)

cos_llc_masks = initialize_hardware_isolation()

def wait_for_container_running(container, timeout=30):
    """等待容器完全启动并处于运行状态"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            container.reload()  # 刷新容器状态
            if container.status == 'running':
                time.sleep(2)
                return True
        except Exception as e:
            print(f"检查容器状态时出错: {e}")
        time.sleep(1)
    return False

def assign_container_to_cos(container_id, cos_id):
    try:
        palloc_base_path = "/sys/fs/cgroup/palloc"
        part_name = f"part_{container_id}"

        palloc_path = os.path.join(palloc_base_path, part_name)
        palloc_bins_file = os.path.join(palloc_path, "palloc.bins")

        if not os.path.exists(palloc_path):
            print(f"palloc路径不存在: {palloc_path}，尝试创建...")
            os.makedirs(palloc_path, exist_ok=True)

        if not os.path.exists(palloc_bins_file):
            print(f"{palloc_bins_file} 不存在，确认palloc cgroup挂载及配置是否正确")
            return False

        if cos_id == 0:
            bins_to_assign = "0-14"
        else:
            bins_to_assign = "15"

        with open(palloc_bins_file, "w") as f:
            f.write(bins_to_assign)

        pid = client.api.inspect_container(container_id)['State']['Pid']
        tasks_file = os.path.join(palloc_path, "tasks")
        with open(tasks_file, "a") as f:
            f.write(str(pid) + "\n")

        print(f"成功为容器 {container_id} 分配 palloc bins {bins_to_assign} 到 {palloc_path}")
    except Exception as e:
        print(f"palloc分配失败: {e}")

    if cos_id >= len(cos_llc_masks) or cos_llc_masks[cos_id] is None:
        print(f"警告：无法分配 COS{cos_id} 给容器 {container_id}")
        return False
    try:
        inspect_result = client.api.inspect_container(container_id)
        
        if inspect_result['State']['Status'] != 'running':
            print(f"错误：容器 {container_id} 未在运行状态")
            return False
        
        pid = inspect_result['State']['Pid']
        if pid == 0:
            print("错误：容器PID为0，容器未正常运行")
            return False
        
        print(f"容器 {container_id} 的PID: {pid}")
        
        try:
            pid_cmd = f"sudo pqos -a 'pid:{cos_id}={pid}'"
            print(f"尝试使用PID分配: {pid_cmd}")
            subprocess.run(pid_cmd, shell=True, check=True)
            print(f"成功使用PID分配 COS{cos_id} 给容器 {container_id}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"PID分配失败: {e}")
        
        try:
            pids_output = subprocess.check_output(
                f"docker exec {container_id} ps -eo pid --no-headers", 
                shell=True, 
                text=True
            ).strip()
            
            container_pids = []
            for line in pids_output.split('\n'):
                if line.strip():
                    container_pids.append(line.strip())
            
            print(f"容器内进程PIDs: {container_pids}")
            
            success_count = 0
            for container_pid in container_pids:
                try:
                    pid_assign_cmd = f"sudo pqos -a 'pid:{cos_id}={container_pid}'"
                    subprocess.run(pid_assign_cmd, shell=True, check=True)
                    success_count += 1
                except Exception as inner_e:
                    print(f"为PID {container_pid} 分配COS失败: {inner_e}")
                    continue
            
            if success_count > 0:
                print(f"成功为 {success_count} 个进程分配了 COS{cos_id}")
                return True
                
        except Exception as e:
            print(f"批量PID分配失败: {e}")
        
        try:
            cgroup_version = "v1"
            try:
                with open("/proc/mounts", "r") as f:
                    mounts = f.read()
                    if "cgroup2" in mounts:
                        cgroup_version = "v2"
            except:
                pass
            
            print(f"检测到cgroup版本: {cgroup_version}")
            
            if cgroup_version == "v1":
                possible_paths = [
                    f"/docker/{container_id}",
                    f"/docker/{container_id[:12]}",
                    f"/system.slice/docker-{container_id}.scope",
                    f"/docker.service/{container_id}",
                ]
                
                for cgroup_path in possible_paths:
                    try:
                        llc_cmd = f"sudo pqos -a 'llc:{cos_id}={cgroup_path}'"
                        print(f"尝试cgroup路径: {llc_cmd}")
                        subprocess.run(llc_cmd, shell=True, check=True)
                        print(f"成功使用cgroup路径 {cgroup_path} 分配 COS{cos_id}")
                        return True
                    except subprocess.CalledProcessError:
                        continue
            else:
                cgroup_path = f"/docker/{container_id}"
                llc_cmd = f"sudo pqos -a 'llc:{cos_id}={cgroup_path}'"
                print(f"尝试cgroup v2路径: {llc_cmd}")
                subprocess.run(llc_cmd, shell=True, check=True)
                print(f"成功使用cgroup v2路径分配 COS{cos_id}")
                return True
                
        except Exception as e:
            print(f"cgroup路径分配失败: {e}")
        
        try:
            print(f"尝试备选方案：使用核心亲和性模拟COS分配")
            if cos_id < len(core):
                target_cores = core[cos_id]
                taskset_cmd = f"sudo docker exec {container_id} taskset -a -c {target_cores} $$"
                subprocess.run(taskset_cmd, shell=True, check=True)
                print(f"使用备选方案成功绑定容器到核心 {target_cores}")
                return True
        except Exception as e:
            print(f"备选方案也失败: {e}")
        
        print(f"所有COS分配方法都失败，容器将继续运行但不受COS限制")
        return False
        
    except Exception as e:
        print(f"分配 COS{cos_id} 失败: {e}")
        return False

latency_dict = {}
pmu_results_dict = {}  # 存储PMU事件结果
ratio_results_dict = {}  # 存储比值结果（GE_X/GE_1）

# 加载PMU事件（只保留延迟事件）
def load_pmu_events():
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
                    print(f"读取{filepath}错误: {e}")
    
    # 只筛选延迟事件
    latency_events = [e for e in event_list if e.get("Deprecated") == "0" and ("OCR." in e["EventName"] or "MEM_INST" in e["EventName"] or "MEM_LOAD" in e["EventName"] or "MEMORY_" in e["EventName"] or "MEM_STORE" in e["EventName"]  or "LD_BLOCKS.ADDRESS_ALIAS" in e["EventName"] or "TOPDOWN.MEMORY_BOUND_SLOTS" in e["EventName"] or "EXE_ACTIVITY.BOUND_ON_LOADS" in e["EventName"])]
    print(f"LATENCY events count: {len(latency_events)}")
    
    
    return latency_events

def start_container(image, command, core, cos_id=None, detach=True, **kwargs):
    """通用容器启动函数"""
    container_config = {
        'image': image,
        'command': command,
        'volumes': VOLUMES,
        'cpuset_cpus': core,  # 绑定到指定核心
        'detach': detach,
        'network_mode': "host",
        'privileged': True,** kwargs
    }
    
    print(f"启动容器命令: {command}，绑定核心: {core}")
    try:
        if detach:
            container = client.containers.run(**container_config)
            print(f"容器 {container.short_id} 已启动，绑定核心: {core}")
            if cos_id is not None:
                if wait_for_container_running(container, timeout=30):
                    print(f"容器 {container.short_id} 已就绪，分配COS资源...")
                    if assign_container_to_cos(container.id, cos_id):
                        print(f"成功分配 COS{cos_id} 给容器 {container.short_id}")
                    else:
                        print(f"警告：COS{cos_id} 分配失败，但容器继续运行")
                else:
                    print(f"警告：容器 {container.short_id} 启动超时，但尝试继续运行")
            return container
        else:
            output = client.containers.run(** container_config)
            print(f"容器输出:\n{output.decode('utf-8')}")
            return True
    
    except docker.errors.ContainerError as e:
        print(f"容器错误（退出码 {e.exit_status}）:\n{e.stderr.decode('utf-8') if e.stderr else '无错误输出'}")
        return False
    except Exception as e:
        print(f"启动容器失败: {e}")
        return False

def safe_remove_container(container):
    """安全地删除容器"""
    try:
        if container:
            container.stop(timeout=10)
            container.remove(force=True)
            print(f"容器 {container.short_id} 已清理")
    except Exception as e:
        print(f"清理容器时出错: {e}")

def read_LC_latency_realtime(log_file):
    """读取每1ms输出的LC延迟统计日志，返回列表"""
    result = []
    if not os.path.exists(log_file):
        print(f"警告: 实时延迟日志 {log_file} 不存在")
        return result
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 解析格式: <timestamp> avg:<value> p95:<value> p99:<value> count:<value>
            try:
                parts = line.split()
                timestamp = float(parts[0])
                avg = float(parts[1].split(':')[1])
                p95 = float(parts[2].split(':')[1])
                p99 = float(parts[3].split(':')[1])
                count = int(parts[4].split(':')[1])
                result.append({
                    "timestamp": timestamp,
                    "avg": avg,
                    "p95": p95,
                    "p99": p99,
                    "count": count
                })
            except Exception as e:
                print(f"解析实时延迟日志行失败: {line}, 错误: {e}")
    return result

def collect_lc_tail_latency(benchmark, be_core, test_time, latency_events, lc_task, lc_core, lc_threads, lc_rps):
    """采集LC任务与BE任务同时运行时的尾延迟"""
    # 1. 初始化日志目录与文件
    lc_log_dir = f"{HOST_WORK_DIR}/benchmarks/{benchmark_set}/log/latency"
    os.makedirs(lc_log_dir, exist_ok=True)
    pmu_single_log = f"{lc_log_dir}/{benchmark}_ge1_pmu.log"
    
    # 延迟日志路径（固定，由masstree1.sh内部生成）
    lc_latency_log = f"{HOST_WORK_DIR}/benchmarks/masstree/QoS/lc_latency_realtime.log"
    
    # 清理历史日志
    subprocess.Popen(f'rm -rf {lc_latency_log} {pmu_single_log}', shell=True).wait()
    print(f"尾延迟测试日志路径: {lc_latency_log}")

    # 2. 筛选目标PMU事件（仅保留GE_1事件）
    ge1_event = None
    for event in latency_events:
        if 'MEM_LOAD_COMPLETED.L1_MISS_ANY' in event["EventName"].upper() and event.get("Deprecated") == "0":
            ge1_event = event
            break
    if not ge1_event:
        print("错误: 未找到LATENCY_GT_4事件，无法进行控制变量测试")
        return None
    print(f"使用单一PMU事件控制变量: {ge1_event['EventName']}")

    # 3. 构建BE容器命令
    if benchmark == "baseline":
        print(f"Baseline场景: BE容器仅运行PMU监控（无实际负载）")
        be_cmd = "sleep infinity"
    else:
        be_cmd = f"bash {CONTAINER_WORK_DIR}/benchmarks/{benchmark_set}/script/{benchmark}.sh {BE_threads} {be_core}"

    # 4. 启动BE容器（绑定核心16+COS分配）
    be_container = start_container(
        image="be_container:v1",
        command=be_cmd,
        core=be_core,  # 绑定到核心16
        cos_id=2,  # BE任务固定COS ID
        detach=True
    )
    if not be_container:
        print("BE容器启动失败，终止尾延迟测试")
        return None

    # 启动PMU采集进程，通过 -C 16 显式指定监控核心16
    ocperf_single_cmd = (
        f"HOME=/home/wjy {PMU_TOOLS_PATH} stat -I 1 -o {pmu_single_log} "
        f"-C {be_core} "  # 绑定到BE核心（16）
        f"-e {ge1_event['EventName']} "  # 仅监控GE_1事件
        f"sleep {test_time + 5}"  # 监控时长覆盖测试全程
    )
    print(f"PMU单一事件采集命令: {ocperf_single_cmd}")
    pmu_process = subprocess.Popen(
        ocperf_single_cmd,
        shell=True,
        preexec_fn=os.setsid,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # 6. 启动LC任务容器
    try:
        if lc_task != "masstree":
            print("警告: 当前函数仅针对masstree任务优化，其他LC任务可能不兼容")
            return None

        # 构建masstree1.sh命令
        mt_threads = lc_threads[0]
        mt_rps = lc_rps[0]
        mt_duration = test_time
        core_ids = lc_core[0].replace(",", " ")  # LC核心ID格式化
        lc_cmd = (
            f"bash {CONTAINER_WORK_DIR}/benchmarks/masstree/script/masstree_real_time.sh "
            f"{mt_threads} {mt_rps} {mt_duration} {core_ids}"
        )
        print(f"LC任务命令: {lc_cmd}")

        # 启动LC容器（同步运行）
        lc_success = start_container(
            image="lc_container:v1",
            command=lc_cmd,
            core=lc_core[0],
            cos_id=0,  # LC任务固定COS ID
            detach=False,
            mem_limit="8g",
            cpu_shares=2048
        )
        lc_container = None  # 同步模式下无容器对象，显式赋值为None

        if not lc_success:
            print("LC容器启动失败，终止测试")
            safe_remove_container(be_container)
            os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
            return None

    except Exception as e:
        print(f"LC任务启动异常: {e}")
        safe_remove_container(be_container)
        os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
        return None

    # 7. 等待测试完成
    print(f"开始尾延迟测试，持续{test_time}秒...")
    time.sleep(test_time + 5)  # 额外等待5秒确保日志写入

    # 8. 清理资源
    # 仅清理存在的容器对象（同步模式下lc_container为None）
    if lc_container is not None:
        safe_remove_container(lc_container)
    safe_remove_container(be_container)
    os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
    pmu_process.wait(timeout=5)
    print("测试资源清理完成")

    # 9. 验证日志生成
    if not os.path.exists(lc_latency_log):
        print(f"警告: LC延迟日志未生成，尝试从masstree.log获取")
        fallback_log = f"{HOST_WORK_DIR}/benchmarks/masstree/QoS/masstree.log"
        if os.path.exists(fallback_log):
            print(f"使用备选日志: {fallback_log}")
            return fallback_log
        print("错误: 所有可能的日志文件均不存在")
        return None

    print(f"尾延迟测试完成，LC延迟日志已保存至: {lc_latency_log}")
    return lc_latency_log

# 动态采集BE任务的PMU事件（绑定核心16）
def collect_be_pmu_events_dynamic(benchmark, be_core, test_time, latency_events, lc_task, lc_core, lc_threads, lc_rps):
    # 区分baseline和普通场景的BE命令
    if benchmark == "baseline":
        print(f"检测到baseline场景: BE容器仅用于PMU检测（不执行负载）")
        be_cmd = "sleep infinity"
    else:
        be_cmd = f"bash {CONTAINER_WORK_DIR}/benchmarks/{benchmark_set}/script/{benchmark}.sh {BE_threads} {be_core}"
    
    pmu_log_dir = f"{HOST_WORK_DIR}/benchmarks/{benchmark_set}/log"
    os.makedirs(pmu_log_dir, exist_ok=True)
    latency_log = f"{pmu_log_dir}/{benchmark}_latency_raw.log"
    subprocess.Popen(f'rm -rf {latency_log}', shell=True).wait()
    
    # 逐个处理事件（保持原日志格式）
    for event in latency_events:
        print(f"\n=== 开始测试事件: {event['EventName']} ===")
        
        # 临时日志（单事件专用，避免干扰）
        temp_log = "temp.log"  # 保持与原代码一致的临时文件名
        subprocess.Popen(f'rm -rf {temp_log}', shell=True).wait()
        
        # 检查是否需要单独采集（TakenAlone=1）
        if event.get("TakenAlone") == "1":
            print(f"事件 {event['EventName']} 需要单独采集（TakenAlone=1）")
        
        # 启动BE容器
        container_name = f"be_pmu_{benchmark}_{int(time.time())}"
        be_container = start_container(
            "be_container:v1",
            be_cmd,
            be_core,
            cos_id=2,
            detach=True,
            mem_limit="16g",
            cpu_shares=512,
            name=container_name
        )
        if not be_container:
            print(f"容器启动失败，跳过事件 {event['EventName']}")
            continue
        
        # 构建ocperf命令（仅包含当前事件）
        ocperf_cmd = f"HOME=/home/wjy {PMU_TOOLS_PATH} stat -I 1 -o {temp_log} -C {be_core}"
        ocperf_cmd += f" -e {event.get('EventName')}"
        
        # 启动PMU采集进程
        if benchmark == "baseline":
            full_cmd = f"{ocperf_cmd} sleep {test_time}"
        else:
            full_cmd = f"{ocperf_cmd}"
        
        print(f"当前采集命令: {ocperf_cmd}")
        pmu_process = subprocess.Popen(
            full_cmd,
            shell=True,
            preexec_fn=os.setsid,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 启动LC任务
        lc_container = None
        lc_success = False
        try:
            if lc_task == "masstree":
                mt_threads = lc_threads[0]
                mt_rps = lc_rps[0]
                mt_duration = test_time
                core_ids = lc_core[0].replace(",", " ")
                lc_cmd = f"bash {CONTAINER_WORK_DIR}/benchmarks/masstree/script/masstree.sh {mt_threads} {mt_rps} {mt_duration} {core_ids}"
                lc_success = start_container(
                    "lc_container:v1",
                    lc_cmd,
                    lc_core[0],
                    cos_id=0,
                    detach=False,
                    mem_limit="8g",
                    cpu_shares=2048
                )
                lc_container = None
            else:
                lc_server_threads = lc_threads[0]
                lc_client_threads = lc_threads[1]
                lc_rps_val = lc_rps[0]
                server_core = lc_core[0]
                client_core = lc_core[1]
                server_args = f"{lc_server_threads} {lc_rps_val} {test_time} {server_core}"
                client_args = f"{lc_client_threads} {lc_rps_val} {test_time} {len(client_core.split(','))} {client_core}"
                lc_cmd = f"""bash -c '
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/server.sh {server_args} &
                    SERVER_PID=$!
                    
                    if [ {TASK_PORTS[lc_task]} ]; then
                        timeout 60 bash -c "until nc -z 127.0.0.1 {TASK_PORTS[lc_task]}; do sleep 1; done"
                        if [ $? -ne 0 ]; then
                            echo "错误: 服务端启动失败" >&2
                            exit 1
                        fi
                    fi
                    
                    {CONTAINER_WORK_DIR}/benchmarks/{lc_task}/script/client.sh {client_args}
                    wait $SERVER_PID
                '"""
                lc_container = start_container(
                    "lc_container:v1",
                    lc_cmd,
                    f"{server_core},{client_core}",
                    cos_id=None,
                    detach=True,
                    mem_limit="8g",
                    cpu_shares=2048
                )
                lc_success = bool(lc_container)

            if not lc_success:
                print(f"LC任务启动失败，跳过当前事件")
                os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
                safe_remove_container(be_container)
                continue

        except Exception as e:
            print(f"LC任务启动失败: {e}")
            os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
            safe_remove_container(be_container)
            continue
        
        # 等待测试完成
        print(f"等待 {test_time} 秒（事件采集中）...")
        time.sleep(test_time)
        
        # 停止容器和进程
        if lc_container:
            safe_remove_container(lc_container)
        os.killpg(os.getpgid(pmu_process.pid), signal.SIGTERM)
        pmu_process.wait(timeout=10)
        safe_remove_container(be_container)
        
        # 解析临时日志（完全复用原代码的解析逻辑）
        latency_result = {}
        try:
            with open(temp_log, 'r') as f:
                logs = [line.strip() for line in f.readlines() if not line.startswith('#')]
                for line in logs:
                    if not line or 'time' in line:
                        continue
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    event_name = parts[2]  # 事件名在最后（与原代码一致）
                    count_str = parts[1].replace(',', '')  # 计数值在第二个字段（与原代码一致）
                    
                    if event_name not in latency_result:
                        latency_result[event_name] = []
                    
                    # 计数值处理逻辑（与原代码完全一致）
                    if count_str == '<not counted>':
                        count = 0
                    else:
                        try:
                            count = int(count_str)
                        except ValueError:
                            count = 0
                    latency_result[event_name].append(count)
            
            # 清理临时文件
            subprocess.Popen('rm -rf temp.log', shell=True).wait()
        except (FileNotFoundError, IOError) as e:
            print(f"解析临时日志失败: {e}")
            pass
        
        # 追加到主日志（保持原格式）
        with open(latency_log, 'a') as f:
            for event_name, counts in latency_result.items():
                # 保持与原代码一致的输出格式：事件名左对齐50字符，计数值空格分隔
                f.write(f"{event_name:<50} {' '.join(map(str, counts))}\n")
    
    return latency_log

# 解析PMU日志（适配动态采集的统一日志）
def parse_pmu_log(log_file):
    if not os.path.exists(log_file):
        print(f"警告：日志文件 {log_file} 不存在")
        return {}
    
    results = {}
    with open(log_file, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or 'time' in line:
                continue
            if len(line) < 50:
                continue
            
            event_name = line[0:50].strip()
            counts_str = line[50:].strip()
            
            if not event_name or not counts_str:
                continue
            
            counts = []
            for c_str in counts_str.split():
                c_str = c_str.replace(',', '')
                if c_str == '<not counted>':
                    counts.append(0)
                else:
                    try:
                        counts.append(int(c_str))
                    except ValueError:
                        counts.append(0)
            
            if event_name in results:
                results[event_name].extend(counts)
            else:
                results[event_name] = counts
    
    return results

# # 计算比值（GE_X / GE_1）
# def calculate_ratios(benchmark, latency_log):
#     if not os.path.exists(latency_log):
#         print(f"延迟日志不存在，跳过比值计算: {latency_log}")
#         return None
    
#     ratio_log = f"{os.path.dirname(latency_log)}/{benchmark}_latency_ratio.log"
#     subprocess.Popen(f'rm -rf {ratio_log}', shell=True).wait()
    
#     # 解析延迟数据
#     latency_counts = parse_pmu_log(latency_log)
#     if not latency_counts:
#         print("延迟数据解析失败")
#         return None
    
#     # 找到GE_1事件
#     ge1_event = None
#     for event in latency_counts:
#         if 'frontend_retired_latency_ge_1' in event:
#             ge1_event = event
#             break
    
#     if not ge1_event:
#         print("Error: LATENCY_GE_1 event not found!")
#         return None
    
#     ge1_samples = latency_counts[ge1_event]
#     print(f"使用 {ge1_event} 作为比值计算的分母")
    
#     # 计算所有GE_X与GE_1的比值
#     ratio_result = {}
#     for event, samples in latency_counts.items():
#         if 'latency_ge' not in event:
#             continue
        
#         ratio_result[event] = []
#         min_len = min(len(samples), len(ge1_samples))
#         for i in range(min_len):
#             if ge1_samples[i] == 0:
#                 ratio_result[event].append(0.0)
#             else:
#                 ratio_result[event].append(samples[i] / ge1_samples[i])
    
#     # 写入比值日志
#     with open(ratio_log, 'w') as f:
#         for event, ratios in ratio_result.items():
#             f.write(f"{event:<50} { ' '.join(f'{r:.6f}' for r in ratios) }\n")
    
#     print(f"GE_X/GE_1比值计算完成，结果保存至: {ratio_log}")
#     return ratio_log

try:
    # 权限配置
    subprocess.Popen("sudo sh -c 'echo -1 > /proc/sys/kernel/perf_event_paranoid'", shell=True).wait()
    
    # 加载PMU事件（只包含延迟事件）
    latency_events = load_pmu_events()
    print(f"共加载 {len(latency_events)} 个LATENCY事件，准备动态采集")
    
    for lc_task in LC_tasks:
        print(f"\n=== 测试 LC 任务: {lc_task} ===")
        latency_dict[lc_task] = {}
        pmu_results_dict[lc_task] = {}
        ratio_results_dict[lc_task] = {}
        
        for benchmark in benchmark_list:
            print(f"\n--- 测试组合: {lc_task} + {benchmark} ---")
            time.sleep(5)
            
            # 动态采集PMU事件（与LC任务同步运行）
            # latency_log = collect_be_pmu_events_dynamic(
            #     benchmark, 
            #     core[2],  # BE核心（固定为16）
            #     test_time, 
            #     latency_events,
            #     lc_task,  # 当前LC任务
            #     core,  # LC核心（包含server和client核心）
            #     LC_threads,  # LC线程数
            #     LC_rps  # LC请求率
            # )
            

            # if not os.path.exists(latency_log):
            #     print("LATENCY事件采集失败，跳过后续步骤")
            #     continue
            
            # # 计算GE_X/GE_1比值
            # print("\n--- 计算比值 ---")
            # ratio_log = calculate_ratios(benchmark, latency_log)
            # if ratio_log:
            #     ratio_results_dict[lc_task][benchmark] = ratio_log
            # else:
            #     print("比值计算失败")
            
            print(f"\n--- 开始尾延迟测试: {lc_task} + {benchmark} ---")
            lc_latency_log = collect_lc_tail_latency(
                benchmark=benchmark,
                be_core=core[2],  # BE核心（固定为16）
                test_time=test_time,
                latency_events=latency_events,
                lc_task=lc_task,
                lc_core=core,
                lc_threads=LC_threads,
                lc_rps=LC_rps
            )

            # 解析尾延迟日志
            if lc_latency_log and os.path.exists(lc_latency_log):
                print("\n--- 解析尾延迟结果 ---")
                latency_dict[lc_task][benchmark] = []
                realtime_stats = read_LC_latency_realtime(lc_latency_log)
                for stat in realtime_stats:
                    latency_dict[lc_task][benchmark].append({
                        "timestamp": stat['timestamp'],
                        "p95": stat['p95']*1000,  # 转换为微秒
                        "avg": stat['avg']*1000,
                        "p99": stat['p99']*1000,
                        "count": stat['count']
                    })
                    print(f"时间戳：{stat['timestamp']}，95th尾延迟: {stat['p95']*1000:.2f} 微秒，99th尾延迟: {stat['p99']*1000:.2f} 微秒")
            else:
                print("尾延迟测试失败，未生成日志")
        
        # 写入延迟结果
        output_filename = f"{HOST_WORK_DIR}/results_docker/proof/{LC_tasks[0]}_t{threads}_r{LC_rps[0]}_c{cache_ways}_m{memory_bandwidth_ratio}.json"
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
        with open(output_filename, 'a') as f:
            json.dump(latency_dict, f)
            f.write('\n')
        print(f"延迟结果已追加至: {output_filename}")
        

except KeyboardInterrupt:
    print("\n用户中断，清理容器...")
    for container in client.containers.list(all=True):
        try:
            container.stop(timeout=10)
            container.remove(force=True)
        except:
            pass
    for proc in subprocess.Popen("ps aux | grep ocperf | grep -v grep", shell=True, stdout=subprocess.PIPE).stdout:
        pid = int(proc.split()[1])
        try:
            os.kill(pid, signal.SIGTERM)
        except:
            pass
    sys.exit(0)

except Exception as e:
    print(f"致命错误: {e}", file=sys.stderr)
    for container in client.containers.list(all=True):
        try:
            container.stop(timeout=10)
            container.remove(force=True)
        except:
            pass
    for proc in subprocess.Popen("ps aux | grep ocperf | grep -v grep", shell=True, stdout=subprocess.PIPE).stdout:
        pid = int(proc.split()[1])
        try:
            os.kill(pid, signal.SIGTERM)
        except:
            pass
    sys.exit(1)