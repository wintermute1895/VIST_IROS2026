#!/usr/bin/env python3
"""
高真实度模拟结果可视化分析
包括: 3D轨迹、α演化、参数敏感性分析
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from mpl_toolkits.mplot3d import Axes3D

# 设置绘图风格
plt.rcParams['figure.figsize'] = (15, 10)

def load_simulation_results(results_file):
    """加载模拟结果"""
    with open(results_file, 'r') as f:
        return json.load(f)

def plot_alpha_evolution(results, output_dir):
    """可视化α因子随时间的演化"""
    print("\n📊 生成α演化图...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Intent Factor α Evolution Analysis', fontsize=16, y=0.995)

    # 提取数据 - 使用实际的method和noise_level组合
    methods = {}
    for exp in results:
        key = f"{exp['method']}"  # 直接使用method名称
        methods[key] = exp['results']

    # 定义颜色映射
    colors = {}
    for method_name in methods.keys():
        if 'Sigmoid' in method_name and '高噪声' not in method_name:
            colors[method_name] = 'blue'
        elif '论文' in method_name and '高噪声' not in method_name:
            colors[method_name] = 'red'
        elif 'Sigmoid' in method_name and '高噪声' in method_name:
            colors[method_name] = 'lightblue'
        elif '论文' in method_name and '高噪声' in method_name:
            colors[method_name] = 'lightcoral'

    # 1. α轨迹对比 (所有试验)
    ax = axes[0, 0]

    for method_name, trials in methods.items():
        for i, trial in enumerate(trials[:5]):  # 只显示前5个试验
            alpha_traj = trial['alpha_trajectory']
            time = np.arange(len(alpha_traj)) * 0.02  # 假设50Hz
            ax.plot(time, alpha_traj, color=colors.get(method_name, 'gray'),
                   alpha=0.3, linewidth=1)

    # 添加图例
    for method_name, color in colors.items():
        ax.plot([], [], color=color, label=method_name, linewidth=2)

    ax.set_xlabel('Time (s)', fontsize=12)
    ax.set_ylabel('Intent Factor α', fontsize=12)
    ax.set_title('α Trajectories (First 5 Trials per Method)', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1])

    # 2. α平均值和标准差
    ax = axes[0, 1]
    method_names = list(methods.keys())
    alpha_means = []
    alpha_stds = []

    for method_name in method_names:
        trials = methods[method_name]
        all_alphas = []
        for trial in trials:
            all_alphas.extend(trial['alpha_trajectory'])
        alpha_means.append(np.mean(all_alphas))
        alpha_stds.append(np.std(all_alphas))

    x_pos = np.arange(len(method_names))
    bars = ax.bar(x_pos, alpha_means, yerr=alpha_stds, capsize=5,
                  color=[colors.get(name, 'gray') for name in method_names],
                  alpha=0.7)

    ax.set_xlabel('Method', fontsize=12)
    ax.set_ylabel('Mean α ± Std', fontsize=12)
    ax.set_title('Average Intent Factor Across All Trials', fontsize=13)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([name.replace(' ', '\n') for name in method_names],
                       fontsize=9, rotation=0)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, 1])

    # 3. α分布直方图
    ax = axes[1, 0]
    for method_name, color in colors.items():
        trials = methods[method_name]
        all_alphas = []
        for trial in trials:
            all_alphas.extend(trial['alpha_trajectory'])
        ax.hist(all_alphas, bins=30, alpha=0.5, label=method_name,
               color=color, density=True)

    ax.set_xlabel('Intent Factor α', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.set_title('α Distribution Across All Trials', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. α vs 距离关系
    ax = axes[1, 1]
    for method_name, color in colors.items():
        trials = methods[method_name]
        all_alphas = []
        all_distances = []
        for trial in trials[:10]:  # 前10个试验
            all_alphas.extend(trial['alpha_trajectory'])
            all_distances.extend(trial['distance_trajectory'])

        ax.scatter(all_distances, all_alphas, alpha=0.3, s=10,
                  color=color, label=method_name)

    ax.set_xlabel('Distance to Target (m)', fontsize=12)
    ax.set_ylabel('Intent Factor α', fontsize=12)
    ax.set_title('α vs Distance Relationship', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_dir / "alpha_evolution_analysis.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'alpha_evolution_analysis.png'}")
    plt.close()

def plot_trajectory_analysis(results, output_dir):
    """可视化轨迹分析"""
    print("\n📊 生成轨迹分析图...")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Trajectory Analysis', fontsize=16, y=0.995)

    # 提取数据
    methods = {}
    for exp in results:
        key = f"{exp['method']}"
        methods[key] = exp['results']

    # 定义颜色映射
    colors = {}
    for method_name in methods.keys():
        if 'Sigmoid' in method_name and '高噪声' not in method_name:
            colors[method_name] = 'blue'
        elif '论文' in method_name and '高噪声' not in method_name:
            colors[method_name] = 'red'
        elif 'Sigmoid' in method_name and '高噪声' in method_name:
            colors[method_name] = 'lightblue'
        elif '论文' in method_name and '高噪声' in method_name:
            colors[method_name] = 'lightcoral'

    # 1. 距离随时间变化
    ax = axes[0, 0]
    for method_name, trials in methods.items():
        for i, trial in enumerate(trials[:5]):
            dist_traj = trial['distance_trajectory']
            time = np.arange(len(dist_traj)) * 0.02
            ax.plot(time, dist_traj, color=colors.get(method_name, 'gray'),
                   alpha=0.3, linewidth=1)

    for method_name, color in colors.items():
        ax.plot([], [], color=color, label=method_name, linewidth=2)

    ax.set_xlabel('Time (s)', fontsize=12)
    ax.set_ylabel('Distance to Target (m)', fontsize=12)
    ax.set_title('Distance Convergence (First 5 Trials)', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 2. 速度随时间变化
    ax = axes[0, 1]
    for method_name, trials in methods.items():
        for i, trial in enumerate(trials[:5]):
            vel_traj = trial['velocity_trajectory']
            time = np.arange(len(vel_traj)) * 0.02
            ax.plot(time, vel_traj, color=colors.get(method_name, 'gray'),
                   alpha=0.3, linewidth=1)

    for method_name, color in colors.items():
        ax.plot([], [], color=color, label=method_name, linewidth=2)

    ax.set_xlabel('Time (s)', fontsize=12)
    ax.set_ylabel('Velocity (m/s)', fontsize=12)
    ax.set_title('Velocity Profile (First 5 Trials)', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 3. 距离-速度相图
    ax = axes[1, 0]
    for method_name, trials in methods.items():
        all_dists = []
        all_vels = []
        for trial in trials[:10]:
            all_dists.extend(trial['distance_trajectory'])
            all_vels.extend(trial['velocity_trajectory'])

        ax.scatter(all_dists, all_vels, alpha=0.3, s=10,
                  color=colors.get(method_name, 'gray'),
                  label=method_name)

    ax.set_xlabel('Distance to Target (m)', fontsize=12)
    ax.set_ylabel('Velocity (m/s)', fontsize=12)
    ax.set_title('Distance-Velocity Phase Portrait', fontsize=13)
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)

    # 4. 收敛速率对比
    ax = axes[1, 1]
    method_names = list(methods.keys())
    convergence_rates = []

    for method_name in method_names:
        trials = methods[method_name]
        rates = []
        for trial in trials:
            dist_traj = trial['distance_trajectory']
            if len(dist_traj) > 1:
                # 计算指数衰减率
                initial_dist = dist_traj[0]
                final_dist = dist_traj[-1]
                time_span = len(dist_traj) * 0.02
                if initial_dist > 0:
                    rate = -np.log(final_dist / initial_dist) / time_span
                    rates.append(rate)
        convergence_rates.append(np.mean(rates))

    x_pos = np.arange(len(method_names))
    bars = ax.bar(x_pos, convergence_rates,
                  color=[colors.get(name, 'gray') for name in method_names],
                  alpha=0.7)

    ax.set_xlabel('Method', fontsize=12)
    ax.set_ylabel('Convergence Rate (1/s)', fontsize=12)
    ax.set_title('Average Convergence Rate', fontsize=13)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([name.replace(' ', '\n') for name in method_names],
                       fontsize=9, rotation=0)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / "trajectory_analysis.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'trajectory_analysis.png'}")
    plt.close()

def plot_method_comparison(results, output_dir):
    """详细的方法对比分析"""
    print("\n📊 生成方法对比图...")

    # 分离Sigmoid和论文方法 - 使用正常噪声的结果
    sigmoid_normal = next((r for r in results if 'Sigmoid' in r['method'] and '高噪声' not in r['method']), None)
    paper_normal = next((r for r in results if '论文' in r['method'] and '高噪声' not in r['method']), None)

    if not sigmoid_normal or not paper_normal:
        print("❌ 未找到正常噪声条件下的Sigmoid和论文方法结果")
        return

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Sigmoid vs Paper Method Comparison (Normal Noise)', fontsize=16, y=0.995)

    # 选择一个代表性试验
    sigmoid_trial = sigmoid_normal['results'][0]
    paper_trial = paper_normal['results'][0]

    # 1. α轨迹对比
    ax = axes[0, 0]
    time_s = np.arange(len(sigmoid_trial['alpha_trajectory'])) * 0.02
    time_p = np.arange(len(paper_trial['alpha_trajectory'])) * 0.02
    ax.plot(time_s, sigmoid_trial['alpha_trajectory'], 'b-', label='Sigmoid', linewidth=2)
    ax.plot(time_p, paper_trial['alpha_trajectory'], 'r--', label='Paper', linewidth=2)
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('α', fontsize=11)
    ax.set_title('Intent Factor Evolution', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. 距离轨迹对比
    ax = axes[0, 1]
    ax.plot(time_s, sigmoid_trial['distance_trajectory'], 'b-', label='Sigmoid', linewidth=2)
    ax.plot(time_p, paper_trial['distance_trajectory'], 'r--', label='Paper', linewidth=2)
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('Distance (m)', fontsize=11)
    ax.set_title('Distance to Target', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 3. 速度轨迹对比
    ax = axes[0, 2]
    ax.plot(time_s, sigmoid_trial['velocity_trajectory'], 'b-', label='Sigmoid', linewidth=2)
    ax.plot(time_p, paper_trial['velocity_trajectory'], 'r--', label='Paper', linewidth=2)
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel('Velocity (m/s)', fontsize=11)
    ax.set_title('Velocity Profile', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 4. α vs 距离
    ax = axes[1, 0]
    ax.scatter(sigmoid_trial['distance_trajectory'], sigmoid_trial['alpha_trajectory'],
              c='blue', alpha=0.5, s=20, label='Sigmoid')
    ax.scatter(paper_trial['distance_trajectory'], paper_trial['alpha_trajectory'],
              c='red', alpha=0.5, s=20, label='Paper')
    ax.set_xlabel('Distance (m)', fontsize=11)
    ax.set_ylabel('α', fontsize=11)
    ax.set_title('α vs Distance', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 5. α vs 速度
    ax = axes[1, 1]
    ax.scatter(sigmoid_trial['velocity_trajectory'], sigmoid_trial['alpha_trajectory'],
              c='blue', alpha=0.5, s=20, label='Sigmoid')
    ax.scatter(paper_trial['velocity_trajectory'], paper_trial['alpha_trajectory'],
              c='red', alpha=0.5, s=20, label='Paper')
    ax.set_xlabel('Velocity (m/s)', fontsize=11)
    ax.set_ylabel('α', fontsize=11)
    ax.set_title('α vs Velocity', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 6. 相关性分析
    ax = axes[1, 2]
    # 计算α的相关性
    min_len = min(len(sigmoid_trial['alpha_trajectory']), len(paper_trial['alpha_trajectory']))
    alpha_s = sigmoid_trial['alpha_trajectory'][:min_len]
    alpha_p = paper_trial['alpha_trajectory'][:min_len]
    correlation = np.corrcoef(alpha_s, alpha_p)[0, 1]

    ax.scatter(alpha_s, alpha_p, alpha=0.5, s=30, c='purple')
    ax.plot([0, 1], [0, 1], 'k--', linewidth=2, label='Perfect correlation')
    ax.set_xlabel('Sigmoid α', fontsize=11)
    ax.set_ylabel('Paper α', fontsize=11)
    ax.set_title(f'α Correlation (r={correlation:.4f})', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])

    plt.tight_layout()
    plt.savefig(output_dir / "method_comparison.png", dpi=150, bbox_inches='tight')
    print(f"✅ 保存: {output_dir / 'method_comparison.png'}")
    plt.close()

def main():
    """主函数"""
    print("=" * 60)
    print("高真实度模拟结果可视化分析")
    print("=" * 60)

    # 加载结果
    results_file = Path("logs/high_fidelity_sim/simulation_results.json")
    output_dir = Path("logs/high_fidelity_sim")

    if not results_file.exists():
        print(f"❌ 结果文件不存在: {results_file}")
        return

    print(f"\n📂 加载结果: {results_file}")
    results = load_simulation_results(results_file)
    print(f"✅ 加载了 {len(results)} 个实验结果")

    # 生成各种可视化
    plot_alpha_evolution(results, output_dir)
    plot_trajectory_analysis(results, output_dir)
    plot_method_comparison(results, output_dir)

    print("\n" + "=" * 60)
    print("✅ 所有可视化完成!")
    print("=" * 60)
    print(f"\n查看结果:")
    print(f"  - α演化分析: {output_dir / 'alpha_evolution_analysis.png'}")
    print(f"  - 轨迹分析: {output_dir / 'trajectory_analysis.png'}")
    print(f"  - 方法对比: {output_dir / 'method_comparison.png'}")

if __name__ == "__main__":
    main()

