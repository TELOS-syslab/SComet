import json
import re

# 读取输入文件
with open("input.txt", "r") as f:
    results = f.readlines()

total_dict = {}

for result in results:
    result = result.replace("'", '"')
    data = json.loads(result)
    for key in data.keys():
        if key not in total_dict.keys():
            total_dict[key] = []
        if type(data[key]) != list:
            total_dict[key] += [data[key]]
        else:
            total_dict[key] += data[key]

print(total_dict)
for key in total_dict:
    result = total_dict[key]
    average = []
    for i in range(9):
        average.append(sum(result[i * 10: i * 10 + 10]) / 10)
    print(average)

