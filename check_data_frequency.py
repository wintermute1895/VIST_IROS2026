#!/usr/bin/env python3
"""
检查录制数据的频率
"""
import json
import sys

if len(sys.argv) < 2:
    print("用法: python check_data_frequency.py <data_file.jsonl>")
    sys.exit(1)

data_file = sys.argv[1]

# 读取前100帧
timestamps = []
use_data_timestamp = False

with open(data_file, 'r') as f:
    for i, line in enumerate(f):
        if i >= 100:
            break
        d = json.loads(line)

        # 优先使用data内部的timestamp（视觉节点时间戳）
        if i == 0:
            if 'data' in d and 'timestamp' in d['data']:
                use_data_timestamp = True
                print("检测到视觉节点时间戳（data.timestamp），使用该时间戳\n")
            else:
                print("使用录制时间戳（timestamp）\n")

        if use_data_timestamp and 'data' in d and 'timestamp' in d['data']:
            timestamps.append(d['data']['timestamp'])
        else:
            timestamps.append(d['timestamp'])

# 计算间隔
intervals = [(timestamps[i+1] - timestamps[i]) * 1000 for i in range(len(timestamps)-1)]

print(f"数据文件: {data_file}")
print(f"总帧数: {i+1}")
print(f"\n时间戳间隔统计（前100帧）:")
print(f"  平均间隔: {sum(intervals)/len(intervals):.2f}ms")
print(f"  最小间隔: {min(intervals):.2f}ms")
print(f"  最大间隔: {max(intervals):.2f}ms")
print(f"  对应频率: {1000/(sum(intervals)/len(intervals)):.1f}Hz")
print()

if sum(intervals)/len(intervals) < 10:
    print("⚠️  警告：时间戳间隔太小（<10ms），数据可能有问题！")
    print("   正常应该是25-40ms（对应25-40Hz）")
elif sum(intervals)/len(intervals) > 50:
    print("⚠️  警告：时间戳间隔太大（>50ms），频率太低！")
else:
    print("✅ 时间戳间隔正常")