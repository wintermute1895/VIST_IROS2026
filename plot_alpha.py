#!/usr/bin/env python3
"""
Alpha 数据可视化工具
读取记录的 α 数据并生成可视化图表
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
from pathlib import Path

def plot_alpha_data(csv_file):
    """绘制 α 数据"""

    # 读取数据
    df = pd.read_csv(csv_file)

    # 计算相对时间
    df['elapsed_time'] = df['timestamp'] - df['timestamp'].iloc[0]

    print(f"数据统计:")
    print(f"  总记录数: {len(df)}")
    print(f"  时长: {df['elapsed_time'].max():.2f}秒")
    print(f"  采样率: {len(df) / df['elapsed_time'].max():.1f} Hz")
    print()
    print(f"α 统计:")
    print(f"  平均值: {df['alpha'].mean():.3f}")
    print(f"  标准差: {df['alpha'].std():.3f}")
    print(f"  最小值: {df['alpha'].min():.3f}")
    print(f"  最大值: {df['alpha'].max():.3f}")
    print()

    # 检查是否有Q、R、K数据
    has_covariance_data = 'Q_norm' in df.columns and 'R_norm' in df.columns and 'K_norm' in df.columns

    # 创建图表
    if has_covariance_data:
        fig, axes = plt.subplots(4, 1, figsize=(12, 14))
    else:
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    # 图1: α 总值
    axes[0].plot(df['elapsed_time'], df['alpha'], 'b-', linewidth=1, label='α (总意图因子)')
    axes[0].axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='中间值 (0.5)')
    axes[0].set_ylabel('α', fontsize=12)
    axes[0].set_title('VIST 意图因子变化', fontsize=14, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(-0.05, 1.05)

    # 图2: α 分量
    axes[1].plot(df['elapsed_time'], df['alpha_geo'], 'g-', linewidth=1, label='α_geo (几何)')
    axes[1].plot(df['elapsed_time'], df['alpha_vel'], 'r-', linewidth=1, label='α_vel (速度)')

    # 兼容两种列名格式
    if 'alpha_dir' in df.columns:
        axes[1].plot(df['elapsed_time'], df['alpha_dir'], 'm-', linewidth=1, label='α_dir (方向)')
    elif 'alpha_alignment' in df.columns:
        axes[1].plot(df['elapsed_time'], df['alpha_alignment'], 'm-', linewidth=1, label='α_align (对齐)')

    axes[1].set_ylabel('分量值', fontsize=12)
    axes[1].set_title('意图因子分量', fontsize=14, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_ylim(-0.05, 1.05)

    # 图3: α 变化率（震荡检测）
    alpha_diff = np.diff(df['alpha'])
    time_diff = np.diff(df['elapsed_time'])
    alpha_rate = alpha_diff / time_diff

    axes[2].plot(df['elapsed_time'][1:], alpha_rate, 'k-', linewidth=0.5, alpha=0.7)
    axes[2].axhline(y=0, color='r', linestyle='-', alpha=0.3)
    axes[2].set_xlabel('时间 (秒)', fontsize=12)
    axes[2].set_ylabel('dα/dt', fontsize=12)
    axes[2].set_title('意图因子变化率（震荡检测）', fontsize=14, fontweight='bold')
    axes[2].grid(True, alpha=0.3)

    # 标注高变化率区域
    high_rate_threshold = np.std(alpha_rate) * 3
    high_rate_mask = np.abs(alpha_rate) > high_rate_threshold
    if np.any(high_rate_mask):
        axes[2].scatter(df['elapsed_time'][1:][high_rate_mask],
                       alpha_rate[high_rate_mask],
                       c='r', s=10, alpha=0.5, label=f'高变化率 (>{high_rate_threshold:.2f})')
        axes[2].legend()

    # 图4: Q和R协方差范数（如果有数据）
    if has_covariance_data:
        ax_idx = 3
        axes[ax_idx].plot(df['elapsed_time'], df['Q_norm'], 'b-', linewidth=1, label='Q (过程噪声)', alpha=0.8)
        axes[ax_idx].plot(df['elapsed_time'], df['R_norm'], 'r-', linewidth=1, label='R (观测噪声)', alpha=0.8)
        axes[ax_idx].plot(df['elapsed_time'], df['K_norm'], 'g-', linewidth=1, label='K (卡尔曼增益)', alpha=0.8)
        axes[ax_idx].set_xlabel('时间 (秒)', fontsize=12)
        axes[ax_idx].set_ylabel('Frobenius范数', fontsize=12)
        axes[ax_idx].set_title('协方差和增益范数', fontsize=14, fontweight='bold')
        axes[ax_idx].set_yscale('log')  # 使用对数坐标
        axes[ax_idx].grid(True, alpha=0.3, which='both')
        axes[ax_idx].legend()

        print(f"\n协方差统计:")
        print(f"  Q范数: {df['Q_norm'].mean():.2e} ± {df['Q_norm'].std():.2e}")
        print(f"  R范数: {df['R_norm'].mean():.2e} ± {df['R_norm'].std():.2e}")
        print(f"  K范数: {df['K_norm'].mean():.2e} ± {df['K_norm'].std():.2e}")

    plt.tight_layout()

    # 保存图表
    output_file = csv_file.replace('.csv', '_plot.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {output_file}")

    # 显示图表
    plt.show()

    # 震荡分析
    print("\n震荡分析:")
    oscillation_count = np.sum(np.abs(alpha_rate) > high_rate_threshold)
    print(f"  高变化率事件: {oscillation_count} 次")
    print(f"  震荡比例: {oscillation_count / len(alpha_rate) * 100:.2f}%")

    if oscillation_count > len(alpha_rate) * 0.1:
        print("  ⚠️  警告: 检测到频繁震荡！")
    else:
        print("  ✓ α 变化平稳")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        # 查找最新的日志文件
        log_dir = Path.home() / "Dev/VIST/data/alpha_logs"
        if log_dir.exists():
            csv_files = sorted(log_dir.glob("alpha_log_*.csv"), key=lambda x: x.stat().st_mtime, reverse=True)
            if csv_files:
                csv_file = str(csv_files[0])
                print(f"使用最新日志文件: {csv_file}\n")
            else:
                print("错误: 未找到日志文件")
                print(f"请先运行: python3 log_alpha.py")
                sys.exit(1)
        else:
            print("错误: 日志目录不存在")
            sys.exit(1)
    else:
        csv_file = sys.argv[1]

    plot_alpha_data(csv_file)