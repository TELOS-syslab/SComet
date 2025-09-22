import os
import json
import sys

# 指定目录和长度
directory = sys.argv[1]
if len(sys.argv) > 2:
    n = int(sys.argv[2])
else:
    n = 0

for filename in os.listdir(directory):
    if filename.endswith(".txt"):
        filepath = os.path.join(directory, filename)
        with open(filepath, 'r') as f:
            try:
                data = json.load(f)  # 假设每个文件内容是一个 JSON 字典
            except json.JSONDecodeError:
                print(f"文件 {filename} 不是有效 JSON，跳过")
                continue

        averages = {}
        lengths = {}
        for k, v in data.items():
            # 先丢弃大于 1000 的值
            filtered = [x for x in v if x <= 1000]

            # 再根据 n 取前 n 个元素，n=0 取全部
            if n == 0 or n > len(filtered):
                subset = filtered
            else:
                subset = filtered[:n]

            avg = sum(subset)/len(subset) if len(subset) > 0 else 0
            averages[k] = avg
            lengths[k] = len(subset)

        print(f"{filename} {averages}")
