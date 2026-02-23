#!/usr/bin/env python3
"""
分析外骨骼遥操作数据
对比无滤波 vs 带滤波的效果

使用方法：
python3 analyze_exo_data.py logs/exo_baseline_raw_*.jsonl logs/exo_ours_filtered_*.jsonl
"""
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

def load_data(jsonl_file):
    """加载JSONL数据"""
    data = []
    with open(jsonl_file, 'r') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def calculate_jerk(positions, dt=0.01):
    """
    计算Jerk（加加速度）

    Jerk = d³x/dt³
    """
    # 计算速度
    velocities = np.diff(positions, axis=0) / dt

    # 计算加速度
    accelerations = np.diff(velocities, axis=0) / dt

    # 计算Jerk
    jerks = np.diff(accelerations, axis=0) / dt

    # 计算Jerk的RMS（均方根）
    jerk_rms = np.sqrt(np.mean(jerks**2, axis=0))

    return jerk_rms, jerks

def analyze_data(baseline_file, filtered_file):
    """分析并对比两组数据"""
    print("="*60)
    print("外骨骼遥操作数据分析")
    print("="*60)

    # 加载数据
    print(f"\n加载数据...")
    print(f"Baseline: {baseline_file}")
    print(f"Filtered: {filtered_file}")

    baseline_data = load_data(baseline_file)
    filtered_data = load_data(filtered_file)

    print(f"✅ Baseline: {len(baseline_data)} 帧")
    print(f"✅ Filtered: {len(filtered_data)} 帧")

    # 提取位置数据
    baseline_pos = np.array([d['q_actual'] for d in baseline_data if d['q_actual']])
    filtered_pos = np.array([d['q_actual'] for d in filtered_data if d['q_actual']])

    # 计算Jerk
    print(f"\n计算Jerk（平滑度指标）...")
    baseline_jerk_rms, baseline_jerks = calculate_jerk(baseline_pos)
    filtered_jerk_rms, filtered_jerks = calculate_jerk(filtered_pos)

    # 打印结果
    print(f"\n{'关节':<8} | {'Baseline Jerk':<15} | {'Filtered Jerk':<15} | {'改善率':<10}")
    print("-" * 60)

    for i in range(7):
        improvement = (1 - filtered_jerk_rms[i] / baseline_jerk_rms[i]) * 100
        print(f"Joint {i:<2} | {baseline_jerk_rms[i]:>13.6f} | {filtered_jerk_rms[i]:>13.6f} | {improvement:>8.1f}%")

    avg_improvement = (1 - np.mean(filtered_jerk_rms) / np.mean(baseline_jerk_rms)) * 100
    print("-" * 60)
    print(f"平均改善率: {avg_improvement:.1f}%")

    # 绘图
    print(f"\n生成对比图...")
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    fig.suptitle('外骨骼遥操作：无滤波 vs 带滤波', fontsize=16)

    for i in range(7):
        row = i // 3
        col = i % 3
        ax = axes[row, col]

        # 绘制位置曲线
        time_baseline = np.arange(len(baseline_pos)) * 0.01
        time_filtered = np.arange(len(filtered_pos)) * 0.01

        ax.plot(time_baseline, np.degrees(baseline_pos[:, i]), 'r-',
                label='Baseline (无滤波)', alpha=0.7, linewidth=1)
        ax.plot(time_filtered, np.degrees(filtered_pos[:, i]), 'b-',
                label='Filtered (带滤波)', alpha=0.7, linewidth=1)

        ax.set_title(f'Joint {i}')
        ax.set_xlabel('时间 (s)')
        ax.set_ylabel('角度 (deg)')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # 删除多余的子图
    for i in range(7, 9):
        row = i // 3
        col = i % 3
        fig.delaxes(axes[row, col])

    plt.tight_layout()

    # 保存图片
    output_dir = Path(baseline_file).parent
    output_file = output_dir / "exo_comparison.png"
    plt.savefig(output_file, dpi=150)
    print(f"✅ 图片已保存: {output_file}")

    # 显示图片
    plt.show()

def main():
    if len(sys.argv) < 3:
        print("使用方法:")
        print("python3 analyze_exo_data.py <baseline_file> <filtered_file>")
        print("\n示例:")
        print("python3 analyze_exo_data.py logs/exo_baseline_raw_*.jsonl logs/exo_ours_filtered_*.jsonl")
        sys.exit(1)

    baseline_file = sys.argv[1]
    filtered_file = sys.argv[2]

    analyze_data(baseline_file, filtered_file)

if __name__ == '__main__':
    main()