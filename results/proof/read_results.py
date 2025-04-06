import os
import json
import sys
import re

def read_results(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            dicts = re.findall(r'\{.*?\}', f.read())
            parsed_data = [json.loads(d) for d in dicts]
            return parsed_data
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False
    return False

result_paths = sys.argv[1]

result = {}

for root, dirs, files in os.walk(result_paths):
    for file in files:
        if file.split('.')[-1] == 'json':
            dicts = read_results(result_paths + '/' + file)
            average_dicts = {}
            for key in dicts[0].keys():
                average_dicts[key] = []
                for j in range(len(dicts[0][key])):
                    sum = 0
                    for i in range(len(dicts)):
                        sum += dicts[i][key][j]
                    average_dicts[key].append(sum / len(dicts))
            result[file.split('.')[0]] = average_dicts

def extract_numbers(key):
    match = re.findall(r"(\d+)", key)  # 提取所有数字
    return tuple(map(int, match))  # 转换为整数元组

result = dict(sorted(result.items(), key=lambda x: extract_numbers(x[0])))

if '--check' in sys.argv:
    checked_param = sys.argv[sys.argv.index('--check') + 1]
    for key in result.keys():
        if checked_param in key.split('_'):
            print(key, result[key])
else:
    for item in result.items():
        print(item[0], item[1])



