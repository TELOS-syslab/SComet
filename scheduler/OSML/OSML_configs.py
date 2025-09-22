import os
import sys
import subprocess
import logging
import subprocess
from utils import shell_output
from utils import run_on_node
from utils import copy_from_node
from utils import nodes
from enum import Enum

logger = logging.getLogger(__name__)
if not os.path.exists("logs"):
    outs, errs = shell_output("mkdir logs", wait = True, output = False)
logging.basicConfig(filename = "logs/osml.log", filemode = "w", level = logging.INFO, format='==> %(asctime)s - %(name)s[%(lineno)d] - %(levelname)s - %(message)s')
logging.getLogger("tensorflow").setLevel(logging.ERROR)

# Mode of an application
# 0: Not launched
# 1: Unmanaged
# 2: Managed
# 3: Dead
# 4: Background
class MODE(Enum):
    Unlaunched = 0
    Unmanaged = 1
    Hungry = 2
    Managed = 3
    Dead = 4
    Background = 5


def init(ip):
    global ROOT, PRIORITY, SHARING, MAX_INVOLVED, ACCEPTABLE_SLOWDOWN, SCHEDULING_INTERVAL, PQOS_OUTPUT_ENABLED, AGGRESSIVE, HISTORY_LEN, PERF_INTERVAL, TOP_INTERVAL, LATENCY_INTERVAL, NAMES, NAME_2_PNAME, QOS_TARGET, MAX_LOAD, RPS_COLLECTED, SETUP_STR, LAUNCH_STR, WARMUP_TIME, LATENCY_STR, CHANGE_RPS_STR, ACTION_SPACE, ACTION_ID, ACTION_SPACE_ADD, ACTION_SPACE_SUB, ACTION_ID_ADD, ACTION_ID_SUB, N_FEATURES, A_FEATURES, A_SHADOW_FEATURES, A_LABELS, B_FEATURES, B_LABELS, B_SHADOW_FEATURES, B_SHADOW_LABELS, C_FEATURES, COLLECT_FEATURES, COLLECT_MUL_FEATURES, COLLECT_N_FEATURES, MAX_VAL, MIN_VAL, ALPHA, BES, LAUNCH_STR_BE, DOCKER_CONTAINER
    # Root path of the project
    ROOT = os.path.dirname(os.path.abspath(__file__))

    init_platform_conf(ip)
    init_docker(ip)

    # Prioritize the use of one type of resources
    # 0 for Default (Cores and LLC ways has the same priority)
    # 1 for Core (Cores are preferentially used)
    # 2 for Cache (LLC ways are preferentially used)
    PRIORITY = 0

    # Enable resource sharing
    # 0 for not enabled
    # 1 for enabled
    SHARING = 0

    # Maximum number of applications involved when enabling resource sharing or deprivation.
    MAX_INVOLVED = 3

    # Acceptable percentage of QoS slowdown. It is used when enabling Model-B or resource sharing.
    ACCEPTABLE_SLOWDOWN = 0.20

    # Scheduling interval (unit: s)
    SCHEDULING_INTERVAL = 1

    # Enable pqos output or not
    PQOS_OUTPUT_ENABLED = False

    # Enable aggressive deprivation
    AGGRESSIVE = True

    # Length of latency history and IPS history
    HISTORY_LEN = 5

    # Time interval between regular update sampling points of system performance monitor, in second
    PERF_INTERVAL = 0.2
    TOP_INTERVAL = 0.2
    LATENCY_INTERVAL = 1

    # Name of each application
    NAMES = ["masstree", "masstree-2500", "masstree-3000", "masstree-3500", "masstree-4000"]

    # Process name of each application
    NAME_2_PNAME = {
                    "masstree": "mttest_integrated",
                    "masstree-2500": "mttest_integrated",
                    "masstree-3000": "mttest_integrated",
                    "masstree-3500": "mttest_integrated",
                    "masstree-4000": "mttest_integrated",
                    }

    # QoS target of each application, in millisecond
    QOS_TARGET = {
                    "masstree": 6,
                    "masstree-2500": 6,
                    "masstree-3000": 6,
                    "masstree-3500": 6,
                    "masstree-4000": 6,
                  }

    # Max load that can satisfy QoS target. Note that the max load may vary on different platforms.
    MAX_LOAD = {
                "masstree": 5000,
                "masstree-2500": 2500,
                "masstree-3000": 3000,
                "masstree-3500": 3500,
                "masstree-4000": 4000,
    }

    # RPSs used for data collection
    RPS_COLLECTED = {
                     'masstree': [3000, 3400, 3800, 4200, 4600],
                        'masstree-2500': [3000, 3400, 3800, 4200, 4600],
                        'masstree-3000': [3000, 3400, 3800, 4200, 4600],
                        'masstree-3500': [3000, 3400, 3800, 4200, 4600],
                        'masstree-4000': [3000, 3400, 3800, 4200, 4600],
    }

    SETUP_STR = {}

    # Instructions for launching each application
    LAUNCH_STR = {
                  "masstree": "docker exec -itd " +  DOCKER_CONTAINER + " /home/OSML_Artifact/apps/tailbench-v0.9/masstree/run.sh {RPS} 2760000 {threads}",
        "masstree-2500": "docker exec -itd " + DOCKER_CONTAINER + " /home/OSML_Artifact/apps/tailbench-v0.9/masstree/run.sh {RPS} 2760000 {threads}",
        "masstree-3000": "docker exec -itd " + DOCKER_CONTAINER + " /home/OSML_Artifact/apps/tailbench-v0.9/masstree/run.sh {RPS} 2760000 {threads}",
        "masstree-3500": "docker exec -itd " + DOCKER_CONTAINER + " /home/OSML_Artifact/apps/tailbench-v0.9/masstree/run.sh {RPS} 2760000 {threads}",
        "masstree-4000": "docker exec -itd " + DOCKER_CONTAINER + " /home/OSML_Artifact/apps/tailbench-v0.9/masstree/run.sh {RPS} 2760000 {threads}",
                  }

    # BES = ["blackscholes", "bodytrack", "streamcluster"]
    # LAUNCH_STR_BE = "docker run spirals/parsec-3.0 -a run -p parsec.{} -i native -n 20 1>/dev/null 2>/dev/null & "
    BES = [
        "500.perlbench_r",
        "502.gcc_r",
        "505.mcf_r",
        "507.cactuBSSN_r",
        "519.lbm_r",
        "520.omnetpp_r",
        "526.blender_r",
        "541.leela_r",
        "544.nab_r",
        "557.xz_r"
    ]
    LAUNCH_STR_BE = "bash /home/wjy/SComet/benchmarks/spec2017/script/{}.sh"

    # Warmup time after launching an application, in second
    WARMUP_TIME = {
                   "masstree": 1,
        "masstree-2500": 1,
        "masstree-3000": 1,
        "masstree-3500": 1,
        "masstree-4000": 1,
    }

    # Instructions for getting response latency of each application
    LATENCY_STR = {
                   "masstree": "tail -n 1 "+VOLUME_PATH+"/tailbench-v0.9/masstree/latency_of_last_second.txt",
        "masstree-2500": "tail -n 1 " + VOLUME_PATH + "/tailbench-v0.9/masstree/latency_of_last_second.txt",
        "masstree-3000": "tail -n 1 " + VOLUME_PATH + "/tailbench-v0.9/masstree/latency_of_last_second.txt",
        "masstree-3500": "tail -n 1 " + VOLUME_PATH + "/tailbench-v0.9/masstree/latency_of_last_second.txt",
        "masstree-4000": "tail -n 1 " + VOLUME_PATH + "/tailbench-v0.9/masstree/latency_of_last_second.txt",

    }

    # Instructions for changing RPS of applications in tailbench
    CHANGE_RPS_STR = {
                      "masstree": "echo {RPS} > "+VOLUME_PATH+"/tailbench-v0.9/masstree/RPS_NOW",
        "masstree-2500": "echo {RPS} > " + VOLUME_PATH + "/tailbench-v0.9/masstree/RPS_NOW",
        "masstree-3000": "echo {RPS} > " + VOLUME_PATH + "/tailbench-v0.9/masstree/RPS_NOW",
        "masstree-3500": "echo {RPS} > " + VOLUME_PATH + "/tailbench-v0.9/masstree/RPS_NOW",
        "masstree-4000": "echo {RPS} > " + VOLUME_PATH + "/tailbench-v0.9/masstree/RPS_NOW",

    }

    # Action space of Model-C, [resource name, step]
    ACTION_SPACE = [("cores", 1), ("cores", -1), ("ways", 1), ("ways", -1), (None, 0)]

    N_FEATURES = ["MBL_N", "Allocated_Cache_N", "Allocated_Core_N"]

    # Features of Model-A
    A_FEATURES = ["CPU_Utilization", "Frequency", "IPC", "Misses", "MBL", "Virt_Memory", "Res_Memory", "Allocated_Cache", "Allocated_Core", "MBL_N", "Allocated_Cache_N", "Allocated_Core_N"]

    # Labels of Model-A and Model-A'
    if MBA_SUPPORT:
        A_LABELS = ["RCliff_Cache", "RCliff_Core", "OAA_Cache", "OAA_Core", "OAA_Bandwidth"]
    else:
        A_LABELS = ["RCliff_Cache", "RCliff_Core", "OAA_Cache", "OAA_Core"]

    # Features of Model-B
    B_FEATURES = ["CPU_Utilization", "Frequency", "IPC", "Misses", "MBL", "Virt_Memory", "Res_Memory", "Allocated_Cache", "Allocated_Core", "MBL_N", "Allocated_Cache_N", "Allocated_Core_N", "Target_Cache", "Target_Core"]

    # Labels of Model-B'
    B_LABELS = ["QoS"]

    # Features of Model-C
    C_FEATURES = {"s": ["CPU_Utilization", "Frequency", "IPC", "Misses", "MBL", "Allocated_Cache", "Allocated_Core", "QoS"],
                  "a": ["action_{}".format(i) for i in range(len(ACTION_SPACE))],
                  "r": ["Reward"],
                  "s_": ["CPU_Utilization_", "Frequency_", "IPC_", "Misses_", "MBL_", "Allocated_Cache_", "Allocated_Core_","QoS_"]}

    # Features for data collection when only one program is running
    COLLECT_FEATURES = ['CPU_Utilization', 'Frequency', 'IPC', 'Misses', 'MBL', 'Virt_Memory', 'Res_Memory', 'Allocated_Cache', 'Allocated_Core', 'Latency']

    # Features for data collection when multiple programs are running
    COLLECT_MUL_FEATURES = ["CPU_Utilization", "Frequency", "IPC", "Misses", "MBL", "Virt_Memory", "Res_Memory", "Allocated_Cache", "Allocated_Core", "MBL_N", "Allocated_Cache_N", "Allocated_Core_N", "Latency"]

    # Features collected from Neighbors
    COLLECT_N_FEATURES = ["MBL", "Allocated_Cache", "Allocated_Core"]

    # Max and min values used for input normalization
    MAX_VAL = { "CPU_Utilization":3200,
                "Frequency":3400,
                "IPC":3,
                "Misses":1e+10,
                "MBL":200000,
                "Virt_Memory":1e+12,
                "Res_Memory":1e+12,
                "Allocated_Cache":15,
                "Allocated_Core":32,
                "MBL_N":20000,
                "Allocated_Cache_N":15,
                "Allocated_Core_N":32,
                "Target_Cache":15,
                "Target_Core":32,
                "QoS":1
                }
    MIN_VAL = { "CPU_Utilization":0,
                "Frequency":0,
                "IPC":0,
                "Misses":0,
                "MBL":0,
                "Virt_Memory":0,
                "Res_Memory":0,
                "Allocated_Cache":0,
                "Allocated_Core":0,
                "MBL_N":0,
                "Allocated_Cache_N":0,
                "Allocated_Core_N":0,
                "Target_Cache":0,
                "Target_Core":0,
                "QoS":0
                }

def init_docker(ip):
    global DOCKER_IMAGE, PARSEC_IMAGE, DOCKER_CONTAINER, BIND_PATH, VOLUME_PATH
    DOCKER_IMAGE = "sysinventor/osml_benchmark:v1.0"
    DOCKER_CONTAINER = "benchmark_container"
    TAR_PATH = "/home/wjy/SComet/scheduler/OSML/osml_benchmark_v1.0.tar.gz"
    UNTAR_PATH = "/home/wjy/SComet/scheduler/OSML/osml_benchmark_v1.0.tar"
    cmd_check = f"docker images -q {DOCKER_IMAGE}"
    proc = run_on_node(ip, cmd_check)
    outs, errs = proc.communicate()
    outs = outs.decode().strip()
    errs = errs.decode().strip()
    if outs == "":
        cmd_check_tar = f"test -f {TAR_PATH} && echo 'exists' || echo 'not_exists'"
        proc_tar = run_on_node(ip, cmd_check_tar)
        tar_out, _ = proc_tar.communicate()
        tar_out = tar_out.decode().strip()
        if tar_out == "exists":
            logger.info(f"Docker image {DOCKER_IMAGE} not found on {ip}, loading from tar")
            cmd_unzip = f"gunzip -c {TAR_PATH} > {UNTAR_PATH}"
            proc_unzip = run_on_node(ip, cmd_unzip)
            unzip_out, unzip_err = proc_unzip.communicate()
            logger.info((unzip_out.decode(), unzip_err.decode()))
            cmd_load = f"docker load -i {TAR_PATH}"
            proc_load = run_on_node(ip, cmd_load)
            load_out, load_err = proc_load.communicate()
            logger.info((load_out.decode(), load_err.decode()))
        else:
            logger.warning(f"Docker image {DOCKER_IMAGE} not found and tar {TAR_PATH} does not exist on {ip}")
    else:
        logger.info(f"Docker image {DOCKER_IMAGE} already exists on {ip}")
    # PARSEC_IMAGE = "spirals/parsec-3.0:latest"
    BIND_PATH = None
    VOLUME_PATH = None
    # Start bechmark_container and get the volume path
    outs, errs = shell_output("docker pull {}".format(DOCKER_IMAGE), wait=True, output=False, ip=ip)
    logger.info((outs, errs))
    # outs, errs = shell_output("docker pull {}".format(PARSEC_IMAGE), wait=True, output=False, ip=ip)
    # logger.info((outs, errs))
    # os.system("mkdir -p {}/volume".format(ROOT))
    proc = run_on_node(ip, "mkdir -p {}/volume".format(ROOT))
    # os.system("mkdir -p {}/volume/mongodb".format(ROOT))
    proc = run_on_node(ip, "mkdir -p {}/volume/mongodb".format(ROOT))
    outs, errs = shell_output("docker run -idt -v {}/volume:/home/OSML_Artifact/volume:rw -v /home/OSML_Artifact/apps --name {} {} "
                              "/bin/bash".format(ROOT,DOCKER_CONTAINER, DOCKER_IMAGE), wait=True, output=False, ip=ip)
    logger.info((outs, errs))
    outs, errs = shell_output("docker start {}".format(DOCKER_CONTAINER), wait=True, output=False, ip=ip)
    logger.info((outs, errs))
    # inspect_info = eval(subprocess.check_output("docker inspect {}".format(DOCKER_CONTAINER), shell=True).decode().replace("false", "False").replace("null", "None").replace("true", "True"))
    proc = run_on_node(ip, f"docker inspect {DOCKER_CONTAINER}")
    outs, errs = proc.communicate()
    inspect_info = eval(
        outs.decode().replace("false", "False")
            .replace("true", "True")
            .replace("null", "None")
    )
    mount_info = inspect_info[0]["Mounts"]

    for item in mount_info:
        if item["Type"] == "volume":
            VOLUME_PATH = item["Source"]
        elif item["Type"] == "bind":
            BIND_PATH = item["Source"]


    def init_tailbench(ip):
        # Prepare inputs for tailbench
        # if not os.path.exists(BIND_PATH+"/tailbench.inputs"):
        proc = run_on_node(ip, f"test -e {BIND_PATH}/tailbench.inputs && echo 1 || echo 0")
        outs, errs = proc.communicate()
        exists = outs.decode().strip() == "1"

        if not exists:
            raise Exception("Please download the input of tailbench and put the \"tailbench.inputs\" folder in {}".format(BIND_PATH))

    '''def init_nginx():
        # Set this to point to the top level of the Nginx data directory
        PATH_NGINX_INPUTS = ROOT+"/apps/nginx/html/"
        # Prepare inputs for Nginx
        if not os.path.exists(PATH_NGINX_INPUTS):
            logger.info("Generating inputs for Nginx, wait a moment.")
            outs, errs = shell_output("sudo {}/apps/nginx/gen_html.sh".format(ROOT), wait = True, output = False)
            logger.info((outs, errs))
        if not os.path.exists(BIND_PATH+"/html"):
            logger.info("Copying html to docker volume, wait a moment.")
            outs, errs = shell_output("sudo cp -r /dev/shm/html "+BIND_PATH+"/html", wait = True, output = False)
            logger.info((outs, errs))
            outs, errs = shell_output("docker exec -itd " +  DOCKER_CONTAINER + " cp -r /home/OSML_Artifact/volume/html /dev/shm/", wait = True, output = False)
            logger.info((outs, errs))'''

    init_tailbench(ip)
    # init_nginx()


def init_platform_conf(ip):
    global N_CORES, N_WAYS, MB_PER_WAY, N_COS, MBA_SUPPORT, MAX_THREADS, CORE_INDEX, WAY_INDEX, PHYSICAL_CORES
    # core_info_str = [line.strip() for line in subprocess.check_output("pqos -I -s | grep 'Core'", shell=True).decode().split("\n")]
    proc = run_on_node(ip, "pqos -I -s | grep 'Core'")
    outs, errs = proc.communicate()
    core_info_str = [line.strip() for line in outs.decode().split("\n") if line.strip()]
    core_info = []
    for line in core_info_str:
        if line == "" or line.startswith("Core information"):
            continue
        arr = line.split()
        core_idx = int(arr[1].rstrip(","))
        L2_idx = int(arr[3].rstrip(","))
        L3_idx = int(arr[5])
        core_info.append((core_idx, L2_idx, L3_idx))
    core_info.sort(key=lambda x: (x[2], x[1], x[0]))
    N_CORES = len([item for item in core_info if item[2] == 0])
    CORE_INDEX = list(range(0, N_CORES))
    # List of Physical cores. The hyper-threading is enabled. Two logical cores share the same physical core. e.g., logical cores with index 0 and 18 are on one physical core, they share the L1 and L2 cache.
    PHYSICAL_CORES = [item[0] for item in core_info if item[2] == 0]
    # N_WAYS = int(subprocess.check_output("cat /sys/devices/system/cpu/cpu0/cache/index3/ways_of_associativity", shell=True))
    # MB_PER_WAY = int(subprocess.check_output("cat /sys/devices/system/cpu/cpu0/cache/index3/size", shell=True).decode().rstrip("K\n")) / 1024 / N_WAYS
    # N_COS = int(subprocess.check_output("pqos -I -d | grep COS | awk {'print $3'}", shell=True))
    proc = run_on_node(ip, "cat /sys/devices/system/cpu/cpu0/cache/index3/ways_of_associativity")
    outs, errs = proc.communicate()
    N_WAYS = int(outs.decode().strip())
    proc = run_on_node(ip, "cat /sys/devices/system/cpu/cpu0/cache/index3/size")
    outs, errs = proc.communicate()
    MB_PER_WAY = int(outs.decode().strip().rstrip("K")) / 1024 / N_WAYS
    proc = run_on_node(ip, "pqos -I -d | grep COS | awk {'print $3'}")
    outs, errs = proc.communicate()
    lines = [int(x) for x in outs.decode().splitlines() if x.strip()]
    N_COS = min(lines)

    MBA_SUPPORT = False
    MAX_THREADS = N_CORES
    WAY_INDEX = list(range(N_WAYS))

for ip in nodes:
    run_on_node(ip, "rm -rf /var/lock/libpqos")
    init(ip)
