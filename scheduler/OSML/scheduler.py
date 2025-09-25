import time
import numpy as np
import math
from copy import deepcopy

from utils import *
from OSML_configs import *
from allocator import *

SComet = False

interference_dict = {
    "519.lbm_r": 2.462280015,
    "507.cactuBSSN_r": 0.797576537,
    "500.perlbench_r": 0.040854815,
    "502.gcc_r": 0.024762225,
    "503.bwaves_r": 0,
    "505.mcf_r": 0.673663423,
    "508.namd_r": 0.042205266,
    "510.parest_r": 0.201912056,
    "511.povray_r": 0,
    "520.omnetpp_r": 0.486317134,
    "521.wrf_r": 0,
    "523.xalancbmk_r": 0.104899582,
    "525.x264_r": 0.016690667,
    "526.blender_r": 0.128601614,
    "527.cam4_r": 0,
    "531.deepsjeng_r": 0.015343912,
    "538.imagick_r": 0,
    "541.leela_r": 0.004873213,
    "544.nab_r": 0.005871788,
    "548.exchange2_r": 0,
    "549.fotonik3d_r": 0,
    "554.roms_r": 0,
    "557.xz_r": 0.263610953,
}

def sin_value(max_val, min_val, theta):
    A = (max_val - min_val) / 2   # 振幅
    C = (max_val + min_val) / 2   # 中心值
    return C + A * math.sin(math.pi * theta)

LC_TASKS = 'masstree'
MY_LC_TASKS = NAMES[1:]

benchmark_list = []
be_tasks = {}
for root, dirs, files in os.walk(f'/home/wjy/SComet/benchmarks/test/script'):
    for file in files:
        if file.split('.')[-1] == 'sh':
            benchmark_name = '.'.join(file.split('.')[0:-1])
            benchmark_list.append(benchmark_name)
            if LC_TASKS in benchmark_name:
                continue
            be_tasks[benchmark_name] = {
                "threads": 1,
                "commands": [f'bash /home/wjy/SComet/benchmarks/test/script/{file}'],
            }
print(be_tasks.keys())

def OSML(mgrs, lc_tasks_, be_tasks_, terminate_when_QoS_is_met=False, terminate_when_timeout=True, timeout=7200):
    start_time = time.time()
    lc_tasks = lc_tasks_
    be_tasks = be_tasks_
    while True:
        if not be_tasks:
            if all([mgr.all_be_done() for mgr in mgrs]):
                break
            
        for mgr in mgrs:
            if len(list(mgr.programs.keys())) == 0:
                app = lc_tasks.pop()
                if PHASE[app] >= 0:
                    phase = sin_value(1, 0.5, PHASE[app] + (time.time() - start_time) / 1800)
                else:
                    phase = 1
                mgr.add_app(app, "PCT", int(100 * phase), 16, launch_time=time.time(), end_time=time.time()+300)
            for app in list(mgr.programs.keys()):
                if mgr.can_be_ended(app):
                    mgr.end(app)
                    if PHASE[app] >= 0:
                        phase = sin_value(1, 0.5, PHASE[app] + (time.time() - start_time) / 1800)
                    else:
                        phase = 1
                    mgr.add_app(app, "PCT", int(100 * phase), 16, launch_time=time.time(), end_time=time.time()+300)
                if mgr.RPS_can_be_changed(app):
                    mgr.change_RPS(app)

            for be in mgr.BEs.BEs:
                if mgr.BEs.status[be] == "dead":
                    mgr.BEs.remove(be)

            if mgr.BEs.empty() and be_tasks:
                QoS = mgr.get_features(list(mgr.programs.keys()), "QoS")
                if not SComet:
                    if QoS:
                        mgr.BEs.add(be_tasks.pop())
                        print("\nBE left:", be_tasks)
                        mgr.propagate_allocation()
                if SComet:
                    # print("SComet")
                    be_tasks.sort(key=lambda x: interference_dict[x])
                    if QoS:
                        QoS = [v[0] for v in QoS.values()]
                        max_QoS = max(QoS)
                        if max_QoS > 2:
                            mgr.BEs.add(be_tasks.pop(-1))
                        else:
                            mgr.BEs.add(be_tasks.pop(0))
                        print("\nBE left:", be_tasks)
                        mgr.propagate_allocation()

            mgr.update_pending_queue()

            # Launch all applications in the pending queue
            for app in list(mgr.pending_queue.keys()):
                if not mgr.can_be_launched(app):
                    continue
                mgr.launch(app)

                # Start log threads
                if not mgr.log_thread_configs["running"]:
                    mgr.start_log_thread()

                # Allocate resources for the newly started application
                A_points = mgr.use_model_A(app)
                idle = mgr.resource_idle(exclude=app)
                if A_points["OAA"]["cores"]<=idle["cores"] and A_points["OAA"]["ways"]<=idle["ways"]:
                    A_solution=A_points["OAA"]
                else:
                    A_solution=A_points["RCliff"]
                diff={"cores":A_solution["cores"]-mgr.programs[app].core_len,"ways":A_solution["ways"]-mgr.programs[app].way_len}
                # print("Model A result: ", A_solution["cores"], A_solution["ways"])
                res=mgr.adjust_using_model_B(app,diff)

            mgr.report_latency()
            mgr.report_allocation()

            mgr.check_revert_event()

            under_provision_apps = mgr.get_under_provision_apps()
            # print("under_provision_apps", under_provision_apps)
            over_provision_apps = mgr.get_over_provision_apps()
            # print("over_provision_apps", over_provision_apps)

            under_provision_slack = {app: mgr.get_slack(app) for app in under_provision_apps}
            over_provision_slack = {app: mgr.get_slack(app) for app in over_provision_apps}

            under_provision_apps.sort(key=lambda x: under_provision_slack[x], reverse=True)
            over_provision_apps.sort(key=lambda x: over_provision_slack[x])

            for app in under_provision_apps:
                mgr.use_model_C(app)
            for app in over_provision_apps:
                mgr.use_model_C(app)

            if terminate_when_QoS_is_met and mgr.is_all_QoS_met() and time.time()-mgr.QoS_met_time > 10:
                print_color("Terminate because the QoS is met.", "green")
                logger.info("Terminate because the QoS is met.")
                time.sleep(5)  # record latency
                return

            if terminate_when_timeout and time.time() - start_time > timeout:
                print_color("Terminate because the time is out.", "green")
                logger.info("Terminate because the time is out.")
                return

        time_remaining = SCHEDULING_INTERVAL - time.time() % SCHEDULING_INTERVAL
        time.sleep(time_remaining)



def main():
    global SComet
    if len(sys.argv) > 1 and sys.argv[1] == "SComet":
        SComet = True
    mgrs = []
    for ip_ in nodes:
        # mgrs.append(program_mgr(config_path=ROOT + "/workload.txt", regular_update=True, enable_models=True, training=True, ip))
        mgrs.append(
            program_mgr(None, regular_update=True, enable_models=True, training=False, ip=ip_))
    try:
        OSML(mgrs, MY_LC_TASKS, list(be_tasks.keys()))
    except KeyboardInterrupt as e:
        raise e
    except Exception as e:
        for mgr in mgrs:
            mgr.end_log_thread()
            mgr.end_all()
        raise e
    for mgr in mgrs:
        mgr.end_log_thread()
        mgr.end_all()
    os.system("./reset.sh")



if __name__ == '__main__':
    main()
