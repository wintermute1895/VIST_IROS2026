#!/usr/bin/env python3
"""
聚合分析脚本
读取 data/analysis 中所有实验的分析结果，计算平均值和统计信息
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse


def load_metrics_from_file(json_path):
    """从 JSON 文件加载指标"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"警告: 无法读取 {json_path}: {e}")
        return None


def aggregate_metrics(analysis_dir):
    """聚合所有实验的指标"""
    analysis_path = Path(analysis_dir)

    if not analysis_path.exists():
        print(f"错误: 分析目录不存在: {analysis_dir}")
        return None

    # 查找所有 all_metrics.json 文件
    metrics_files = list(analysis_path.glob('*/all_metrics.json'))

    if not metrics_files:
        print(f"错误: 在 {analysis_dir} 中未找到任何分析结果")
        return None

    print(f"\n找到 {len(metrics_files)} 个实验的分析结果:")
    for f in metrics_files:
        print(f"  - {f.parent.name}")
    print()

    # 收集所有实验的指标
    all_experiments = {}

    for metrics_file in metrics_files:
        experiment_name = metrics_file.parent.name
        metrics_data = load_metrics_from_file(metrics_file)

        if metrics_data:
            all_experiments[experiment_name] = metrics_data

    if not all_experiments:
        print("错误: 没有成功加载任何实验数据")
        return None

    # 按数据源分组收集指标
    # 数据源: command, feedback_raw, feedback_cleaned, exo_output
    aggregated = {}

    # 获取所有可能的数据源
    all_sources = set()
    for exp_data in all_experiments.values():
        all_sources.update(exp_data.keys())

    print(f"数据源: {', '.join(all_sources)}\n")

    # 对每个数据源进行聚合
    for source in all_sources:
        source_metrics = []

        # 收集该数据源在所有实验中的指标
        for exp_name, exp_data in all_experiments.items():
            if source in exp_data and 'metrics' in exp_data[source]:
                source_metrics.append(exp_data[source]['metrics'])

        if not source_metrics:
            continue

        # 计算统计信息
        aggregated[source] = {
            'label': all_experiments[list(all_experiments.keys())[0]][source].get('label', source),
            'num_experiments': len(source_metrics),
            'metrics': {}
        }

        # 对每个指标计算平均值、标准差、最小值、最大值
        metric_names = source_metrics[0].keys()

        for metric_name in metric_names:
            values = [m[metric_name] for m in source_metrics if metric_name in m]

            if values:
                aggregated[source]['metrics'][metric_name] = {
                    'mean': float(np.mean(values)),
                    'std': float(np.std(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'median': float(np.median(values)),
                    'count': len(values)
                }

    return {
        'timestamp': datetime.now().isoformat(),
        'num_experiments': len(all_experiments),
        'experiment_names': list(all_experiments.keys()),
        'aggregated_metrics': aggregated
    }


def print_aggregated_metrics(aggregated):
    """打印聚合后的指标"""
    print(f"{'='*80}")
    print(f"聚合分析结果")
    print(f"{'='*80}")
    print(f"实验数量: {aggregated['num_experiments']}")
    print(f"分析时间: {aggregated['timestamp']}")
    print()

    for source, data in aggregated['aggregated_metrics'].items():
        print(f"\n{data['label']} (基于 {data['num_experiments']} 个实验)")
        print(f"{'-'*80}")

        metrics = data['metrics']

        # 按类别组织指标
        frequency_metrics = ['frequency']
        velocity_metrics = ['avg_velocity', 'max_velocity', 'rms_velocity']
        acceleration_metrics = ['avg_acceleration', 'max_acceleration', 'rms_acceleration']
        jerk_metrics = ['avg_jerk', 'max_jerk', 'rms_jerk']
        quality_metrics = ['normalized_jerk', 'sparc']
        advanced_metrics = ['spatial_variance', 'orthogonal_vel_var', 'pca_energy_ratio']
        other_metrics = ['num_samples', 'duration']

        def print_metric_group(title, metric_list):
            print(f"\n  {title}:")
            for metric_name in metric_list:
                if metric_name in metrics:
                    m = metrics[metric_name]

                    # 根据指标类型选择格式
                    if metric_name in ['frequency', 'num_samples']:
                        fmt = '.2f'
                    elif metric_name in ['duration']:
                        fmt = '.2f'
                    elif 'velocity' in metric_name:
                        fmt = '.4f'
                        # 添加角度单位
                        deg_mean = m['mean'] * 57.3
                        deg_std = m['std'] * 57.3
                        print(f"    {metric_name:25s}: {m['mean']:{fmt}} ± {m['std']:{fmt}} rad/s "
                              f"({deg_mean:.2f} ± {deg_std:.2f} °/s)")
                        continue
                    elif 'acceleration' in metric_name:
                        fmt = '.4f'
                    elif 'jerk' in metric_name:
                        if metric_name == 'normalized_jerk':
                            fmt = '.2e'
                        else:
                            fmt = '.4f'
                    elif metric_name == 'sparc':
                        fmt = '.4f'
                    elif metric_name == 'spatial_variance':
                        fmt = '.2f'
                        print(f"    {metric_name:25s}: {m['mean']:{fmt}} ± {m['std']:{fmt}} mm² "
                              f"[{m['min']:{fmt}}, {m['max']:{fmt}}]")
                        continue
                    elif metric_name == 'orthogonal_vel_var':
                        fmt = '.6f'
                    elif metric_name == 'pca_energy_ratio':
                        fmt = '.2f'
                        print(f"    {metric_name:25s}: {m['mean']:{fmt}} ± {m['std']:{fmt}}% "
                              f"[{m['min']:{fmt}}, {m['max']:{fmt}}]")
                        continue
                    else:
                        fmt = '.2f'

                    print(f"    {metric_name:25s}: {m['mean']:{fmt}} ± {m['std']:{fmt}} "
                          f"[{m['min']:{fmt}}, {m['max']:{fmt}}]")

        print_metric_group("频率", frequency_metrics)
        print_metric_group("速度", velocity_metrics)
        print_metric_group("加速度", acceleration_metrics)
        print_metric_group("Jerk", jerk_metrics)
        print_metric_group("质量指标", quality_metrics)
        print_metric_group("高级统计指标", advanced_metrics)
        print_metric_group("其他", other_metrics)


def save_aggregated_metrics(aggregated, output_path):
    """保存聚合后的指标"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 聚合结果已保存到: {output_file}")


def generate_comparison_table(aggregated, output_path):
    """生成对比表格（Markdown格式）"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# 实验数据聚合分析报告\n\n")
        f.write(f"**分析时间**: {aggregated['timestamp']}\n\n")
        f.write(f"**实验数量**: {aggregated['num_experiments']}\n\n")
        f.write(f"**实验列表**:\n")
        for exp_name in aggregated['experiment_names']:
            f.write(f"- {exp_name}\n")
        f.write(f"\n---\n\n")

        # 生成对比表格
        f.write(f"## 指标对比\n\n")

        # 表头
        sources = list(aggregated['aggregated_metrics'].keys())
        f.write(f"| 指标 | " + " | ".join([aggregated['aggregated_metrics'][s]['label'] for s in sources]) + " |\n")
        f.write(f"|------|" + "|".join(["------" for _ in sources]) + "|\n")

        # 获取所有指标名称
        all_metric_names = set()
        for source_data in aggregated['aggregated_metrics'].values():
            all_metric_names.update(source_data['metrics'].keys())

        # 按类别排序
        metric_order = [
            'frequency', 'duration', 'num_samples',
            'avg_velocity', 'max_velocity', 'rms_velocity',
            'avg_acceleration', 'max_acceleration', 'rms_acceleration',
            'avg_jerk', 'max_jerk', 'rms_jerk',
            'normalized_jerk', 'sparc',
            'spatial_variance', 'orthogonal_vel_var', 'pca_energy_ratio'
        ]

        for metric_name in metric_order:
            if metric_name not in all_metric_names:
                continue

            row = [metric_name]
            for source in sources:
                if metric_name in aggregated['aggregated_metrics'][source]['metrics']:
                    m = aggregated['aggregated_metrics'][source]['metrics'][metric_name]

                    # 格式化
                    if metric_name == 'normalized_jerk':
                        value_str = f"{m['mean']:.2e} ± {m['std']:.2e}"
                    elif 'velocity' in metric_name:
                        value_str = f"{m['mean']:.4f} ± {m['std']:.4f}"
                    elif metric_name in ['frequency', 'duration']:
                        value_str = f"{m['mean']:.2f} ± {m['std']:.2f}"
                    elif metric_name == 'num_samples':
                        value_str = f"{m['mean']:.0f} ± {m['std']:.0f}"
                    else:
                        value_str = f"{m['mean']:.4f} ± {m['std']:.4f}"

                    row.append(value_str)
                else:
                    row.append("N/A")

            f.write(f"| {' | '.join(row)} |\n")

        f.write(f"\n---\n\n")
        f.write(f"*注: 表格中的值为 平均值 ± 标准差*\n")

    print(f"✓ 对比表格已保存到: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='聚合所有实验的分析结果')
    parser.add_argument('--input', default='data/analysis',
                        help='分析结果目录 (默认: data/analysis)')
    parser.add_argument('--output', default='data/analysis/aggregated_metrics.json',
                        help='输出文件路径 (默认: data/analysis/aggregated_metrics.json)')
    parser.add_argument('--table', default='data/analysis/comparison_table.md',
                        help='对比表格输出路径 (默认: data/analysis/comparison_table.md)')

    args = parser.parse_args()

    # 聚合指标
    aggregated = aggregate_metrics(args.input)

    if aggregated is None:
        return

    # 打印结果
    print_aggregated_metrics(aggregated)

    # 保存结果
    save_aggregated_metrics(aggregated, args.output)

    # 生成对比表格
    generate_comparison_table(aggregated, args.table)

    print(f"\n{'='*80}")
    print(f"聚合分析完成")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()