#!/usr/bin/env python3
"""
视觉控制 vs 遥操臂性能对比分析
对比两个rosbag的性能指标
"""
import argparse
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='视觉控制 vs 遥操臂性能对比')
    parser.add_argument('--vision-bag', required=True, help='视觉控制rosbag路径')
    parser.add_argument('--exo-bag', required=True, help='遥操臂rosbag路径')
    parser.add_argument('--output', default='data/comparison', help='输出目录')
    parser.add_argument('--config', default='config/vision_vs_exo_analysis.yaml', help='配置文件')

    args = parser.parse_args()

    vision_bag = Path(args.vision_bag)
    exo_bag = Path(args.exo_bag)
    output_dir = Path(args.output)
    config_file = Path(args.config)

    # 检查输入
    if not vision_bag.exists():
        print(f"错误: 视觉控制rosbag不存在: {vision_bag}")
        return 1

    if not exo_bag.exists():
        print(f"错误: 遥操臂rosbag不存在: {exo_bag}")
        return 1

    if not config_file.exists():
        print(f"错误: 配置文件不存在: {config_file}")
        return 1

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("视觉控制 vs 遥操臂性能对比分析")
    print("="*60)
    print(f"视觉控制数据: {vision_bag}")
    print(f"遥操臂数据: {exo_bag}")
    print(f"输出目录: {output_dir}")
    print(f"配置文件: {config_file}")
    print("")

    # 分析视觉控制数据
    print("[1/3] 分析视觉控制数据...")
    vision_output = output_dir / "vision_control"
    vision_output.mkdir(exist_ok=True)

    # 需要source ROS2环境
    cmd = f"""
    source /opt/ros/humble/setup.bash && \
    source external_sdk/arm_teleop/install/setup.bash && \
    python3 scripts/analyze_all_metrics.py \
        --rosbag {vision_bag} \
        --config {config_file} \
        --output {vision_output}
    """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable='/bin/bash')
    if result.returncode != 0:
        print(f"错误: 视觉控制数据分析失败")
        print(result.stderr)
        return 1

    print("✓ 视觉控制数据分析完成")
    print("")

    # 分析遥操臂数据
    print("[2/3] 分析遥操臂数据...")
    exo_output = output_dir / "exo_arm"
    exo_output.mkdir(exist_ok=True)

    cmd = f"""
    source /opt/ros/humble/setup.bash && \
    source external_sdk/arm_teleop/install/setup.bash && \
    python3 scripts/analyze_all_metrics.py \
        --rosbag {exo_bag} \
        --config {config_file} \
        --output {exo_output}
    """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable='/bin/bash')
    if result.returncode != 0:
        print(f"错误: 遥操臂数据分析失败")
        print(result.stderr)
        return 1

    print("✓ 遥操臂数据分析完成")
    print("")

    # 生成对比报告
    print("[3/3] 生成对比报告...")
    generate_comparison_report(vision_output, exo_output, output_dir)

    print("")
    print("="*60)
    print("✓ 对比分析完成！")
    print(f"结果保存在: {output_dir}")
    print("="*60)

    return 0


def generate_comparison_report(vision_dir, exo_dir, output_dir):
    """生成对比报告"""
    import json
    import matplotlib.pyplot as plt
    import numpy as np

    # 读取指标数据
    vision_metrics_file = vision_dir / 'all_metrics.json'
    exo_metrics_file = exo_dir / 'all_metrics.json'

    if not vision_metrics_file.exists() or not exo_metrics_file.exists():
        print("警告: 无法找到指标文件，跳过对比报告生成")
        return

    with open(vision_metrics_file, 'r') as f:
        vision_data = json.load(f)

    with open(exo_metrics_file, 'r') as f:
        exo_data = json.load(f)

    # 提取关键指标
    vision_metrics = vision_data.get('command', {}).get('metrics', {})
    exo_metrics = exo_data.get('exo_output', {}).get('metrics', {})

    if not vision_metrics or not exo_metrics:
        print("警告: 指标数据不完整")
        return

    # 生成对比表格
    report_lines = []
    report_lines.append("# 视觉控制 vs 遥操臂性能对比报告\n")
    report_lines.append("## 性能指标对比\n")
    report_lines.append("| 指标 | 视觉控制 | 遥操臂 | 改善率 |")
    report_lines.append("|------|----------|--------|--------|")

    metrics_to_compare = [
        ('avg_velocity', '平均速度 (rad/s)', False),
        ('max_velocity', '最大速度 (rad/s)', False),
        ('avg_acceleration', '平均加速度 (rad/s²)', False),
        ('max_acceleration', '最大加速度 (rad/s²)', False),
        ('avg_jerk', '平均Jerk (rad/s³)', True),
        ('max_jerk', '最大Jerk (rad/s³)', True),
        ('rms_jerk', 'RMS Jerk (rad/s³)', True),
    ]

    improvements = {}

    for key, label, lower_is_better in metrics_to_compare:
        vision_val = vision_metrics.get(key, 0)
        exo_val = exo_metrics.get(key, 0)

        if exo_val != 0:
            if lower_is_better:
                improvement = (exo_val - vision_val) / exo_val * 100
            else:
                improvement = (vision_val - exo_val) / exo_val * 100
            improvements[key] = improvement

            sign = "↓" if lower_is_better else "↑"
            color = "🟢" if improvement > 0 else "🔴"

            report_lines.append(
                f"| {label} | {vision_val:.4f} | {exo_val:.4f} | "
                f"{color} {improvement:+.1f}% {sign} |"
            )
        else:
            report_lines.append(
                f"| {label} | {vision_val:.4f} | {exo_val:.4f} | N/A |"
            )

    # 添加总结
    report_lines.append("\n## 总结\n")

    jerk_improvement = improvements.get('avg_jerk', 0)
    if jerk_improvement > 0:
        report_lines.append(f"✅ **Jerk降低**: 视觉控制的平均Jerk比遥操臂降低了 **{jerk_improvement:.1f}%**\n")
    else:
        report_lines.append(f"⚠️ **Jerk增加**: 视觉控制的平均Jerk比遥操臂增加了 **{-jerk_improvement:.1f}%**\n")

    rms_jerk_improvement = improvements.get('rms_jerk', 0)
    if rms_jerk_improvement > 0:
        report_lines.append(f"✅ **RMS Jerk降低**: 视觉控制的RMS Jerk比遥操臂降低了 **{rms_jerk_improvement:.1f}%**\n")

    # 保存报告
    report_file = output_dir / 'COMPARISON_REPORT.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"✓ 对比报告已保存: {report_file}")

    # 生成对比柱状图
    generate_comparison_chart(vision_metrics, exo_metrics, output_dir)


def generate_comparison_chart(vision_metrics, exo_metrics, output_dir):
    """生成对比柱状图"""
    import matplotlib.pyplot as plt
    import numpy as np

    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    metrics = [
        ('avg_jerk', 'Avg Jerk (rad/s³)'),
        ('max_jerk', 'Max Jerk (rad/s³)'),
        ('rms_jerk', 'RMS Jerk (rad/s³)'),
        ('avg_velocity', 'Avg Velocity (rad/s)'),
        ('max_velocity', 'Max Velocity (rad/s)'),
        ('avg_acceleration', 'Avg Accel (rad/s²)'),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    for idx, (key, label) in enumerate(metrics):
        ax = axes[idx]

        vision_val = vision_metrics.get(key, 0)
        exo_val = exo_metrics.get(key, 0)

        x = np.arange(2)
        values = [vision_val, exo_val]
        colors = ['#2E86AB', '#06A77D']

        bars = ax.bar(x, values, color=colors, alpha=0.8, edgecolor='black')

        # 添加数值标签
        for i, (bar, val) in enumerate(zip(bars, values)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{val:.4f}',
                   ha='center', va='bottom', fontsize=9)

        ax.set_ylabel(label)
        ax.set_xticks(x)
        ax.set_xticklabels(['Vision Control', 'Exo Arm'])
        ax.grid(axis='y', alpha=0.3)

        # 计算改善率
        if exo_val != 0:
            if 'jerk' in key.lower():
                improvement = (exo_val - vision_val) / exo_val * 100
            else:
                improvement = (vision_val - exo_val) / exo_val * 100

            color = 'green' if improvement > 0 else 'red'
            ax.set_title(f'{label}\n({improvement:+.1f}%)', color=color, fontsize=10)

    plt.tight_layout()
    chart_file = output_dir / 'comparison_chart.png'
    plt.savefig(chart_file, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ 对比图表已保存: {chart_file}")


if __name__ == '__main__':
    sys.exit(main())