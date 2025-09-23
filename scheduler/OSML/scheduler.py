import time
import numpy as np
import math
from copy import deepcopy

from utils import *
from OSML_configs import *
from allocator import *

def sin_value(max_val, min_val, theta):
    A = (max_val - min_val) / 2   # 振幅
    C = (max_val + min_val) / 2   # 中心值
    return C + A * math.sin(math.pi * theta)

LC_TASKS = 'masstree'
MY_LC_TASKS = ['masstree-2500', 'masstree-3000', 'masstree-3500', 'masstree-4000']

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
            if all([mgr.all_done() for mgr in mgrs]):
                break
            
        for mgr in mgrs:
            if len(list(mgr.programs.keys())) == 0:
                mgr.add_app(lc_tasks.pop(), "PCT", int(100 * sin_value(1, 1, (time.time() - start_time) / 1800)), 16, launch_time=0, end_time=600)
            for app in list(mgr.programs.keys()):
                if mgr.can_be_ended(app):
                    mgr.end(app)
                    mgr.add_app(app, "PCT", int(100 * sin_value(1, 1, (time.time() - start_time) / 1800)), 16, launch_time=0, end_time=600)
                if mgr.RPS_can_be_changed(app):
                    mgr.change_RPS(app)

            for be in mgr.BEs.BEs:
                if mgr.BEs.status[be] == "dead":
                    mgr.BEs.remove(be)

            if mgr.BEs.empty() and be_tasks:
                mgr.BEs.add(be_tasks.pop())
                print("\nBE left:", be_tasks)

            mgr.update_pending_queue()

        for mgr in mgrs:
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
                res=mgr.adjust_using_model_B(app,diff)

            mgr.report_latency()
            mgr.report_allocation()

            mgr.check_revert_event()

            under_provision_apps = mgr.get_under_provision_apps()
            over_provision_apps = mgr.get_over_provision_apps()

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
    mgrs = []
    for ip_ in nodes:
        # mgrs.append(program_mgr(config_path=ROOT + "/workload.txt", regular_update=True, enable_models=True, training=True, ip))
        mgrs.append(
            program_mgr(None, regular_update=True, enable_models=True, training=True, ip=ip_))
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
