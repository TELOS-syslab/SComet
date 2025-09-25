import subprocess

num_runs = 1
base_command_1 = ["python3", "-u", "scheduler.py", "SComet"]
base_command_2 = ["python3", "-u", "scheduler.py"]

for i in range(1, num_runs + 1):
    log_file_1 = f"results/output-SComet-{i}.log"
    log_file_2 = f"results/output-osml-{i}.log"

    print(f"Running {base_command_1} -> {log_file_1}")
    with open(log_file_1, "w") as f:
        subprocess.run(base_command_1, stdout=f, stderr=subprocess.STDOUT)

    # print(f"Running {base_command_2} -> {log_file_2}")
    # with open(log_file_2, "w") as f:
    #     subprocess.run(base_command_2, stdout=f, stderr=subprocess.STDOUT)
