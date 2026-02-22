#!/usr/bin/env python3
"""
VIST 消融实验自动化脚本
自动运行不同滤波器配置的对比实验

Author: VIST Project
Date: 2026-02-22
"""

import os
import sys
import yaml
import json
import time
import subprocess
import numpy as np
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


class AblationStudy:
    """消融实验管理器"""

    def __init__(self, config_file="config/ablation_config.yaml"):
        """
        初始化消融实验

        Args:
            config_file: 消融实验配置文件路径
        """
        self.config_file = config_file
        self.config = self._load_config()

        # 创建输出目录
        self.output_dir = Path(self.config['ablation_study']['output_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 实验时间戳
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        print("=" * 80)
        print("🧪 VIST 消融实验")
        print("=" * 80)
        print(f"配置文件: {config_file}")
        print(f"输出目录: {self.output_dir}")
        print(f"实验时间: {self.timestamp}")
        print("=" * 80)

    def _load_config(self):
        """加载配置文件"""
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def run_single_experiment(self, experiment_name, repetition):
        """
        运行单个实验

        Args:
            experiment_name: 实验名称
            repetition: 重复次数索引

        Returns:
            results: 实验结果字典
        """
        exp_config = self.config[experiment_name]

        print(f"\n{'=' * 80}")
        print(f"🔬 实验: {exp_config['name']} (重复 {repetition + 1})")
        print(f"{'=' * 80}")
        print(f"描述: {exp_config['description']}")
        print(f"滤波器类型: {exp_config['filter']['type']}")

        # 创建临时配置文件
        temp_config = self._create_temp_config(exp_config)

        # 运行控制器
        results = self._run_controller(temp_config, experiment_name, repetition)

        # 清理临时文件
        os.remove(temp_config)

        return results

    def _create_temp_config(self, exp_config):
        """创建临时配置文件"""
        # 加载基础配置
        base_config_file = exp_config['inherit_from']
        with open(f"config/{base_config_file}", 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)

        # 合并滤波器配置
        if 'filter' not in base_config:
            base_config['filter'] = {}
        base_config['filter'].update(exp_config['filter'])

        # 保存临时配置
        temp_config_file = f"config/temp_ablation_{self.timestamp}.yaml"
        with open(temp_config_file, 'w', encoding='utf-8') as f:
            yaml.dump(base_config, f)

        return temp_config_file

    def _run_controller(self, config_file, experiment_name, repetition):
        """
        运行控制器并收集结果

        Args:
            config_file: 配置文件路径
            experiment_name: 实验名称
            repetition: 重复次数索引

        Returns:
            results: 实验结果字典
        """
        # 设置环境变量
        env = os.environ.copy()
        env['VIST_CONFIG'] = config_file

        # 构建命令
        if self.config['ablation_study']['use_recorded_data']:
            # 使用录制数据回放
            recorded_file = self.config['ablation_study']['recorded_data_file']

            # 启动控制器（后台）
            controller_proc = subprocess.Popen([
                sys.executable,
                "scripts/run_real_robot_vist_refactored.py",
                "--duration", "120",
                "--no-viz"
            ], env=env)

            # 等待控制器启动
            time.sleep(2)

            # 启动回放
            playback_proc = subprocess.Popen([
                sys.executable,
                "scripts/playback_vision_data.py",
                recorded_file
            ])

            # 等待完成
            playback_proc.wait()
            controller_proc.wait()

        else:
            # 使用真实硬件
            controller_proc = subprocess.Popen([
                sys.executable,
                "scripts/run_real_robot_vist_refactored.py",
                "--duration", "60",
                "--no-viz"
            ], env=env)

            controller_proc.wait()

        # 读取性能日志
        log_files = sorted(Path("logs").glob("performance_*.json"))
        if log_files:
            latest_log = log_files[-1]
            with open(latest_log, 'r') as f:
                results = json.load(f)

            # 添加实验元数据
            results['experiment_name'] = experiment_name
            results['repetition'] = repetition
            results['timestamp'] = time.time()

            return results
        else:
            print("⚠️  未找到性能日志")
            return None

    def run_all_experiments(self):
        """运行所有消融实验"""
        experiments = self.config['ablation_study']['experiments']
        repetitions = self.config['ablation_study']['repetitions']

        all_results = []

        for exp_name in experiments:
            for rep in range(repetitions):
                try:
                    results = self.run_single_experiment(exp_name, rep)
                    if results:
                        all_results.append(results)

                        # 保存中间结果
                        self._save_results(all_results)

                except Exception as e:
                    print(f"❌ 实验失败: {e}")
                    import traceback
                    traceback.print_exc()

        # 生成最终报告
        self._generate_report(all_results)

        print(f"\n{'=' * 80}")
        print("✅ 所有实验完成！")
        print(f"结果保存在: {self.output_dir}")
        print("=" * 80)

    def _save_results(self, results):
        """保存实验结果"""
        output_file = self.output_dir / f"ablation_results_{self.timestamp}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

    def _generate_report(self, results):
        """生成实验报告"""
        print(f"\n{'=' * 80}")
        print("📊 生成实验报告...")
        print("=" * 80)

        # 按实验分组
        grouped_results = {}
        for result in results:
            exp_name = result['experiment_name']
            if exp_name not in grouped_results:
                grouped_results[exp_name] = []
            grouped_results[exp_name].append(result)

        # 计算统计
        report = {}
        for exp_name, exp_results in grouped_results.items():
            exp_config = self.config[exp_name]

            # 提取指标
            metrics = {}
            for metric in self.config['ablation_study']['metrics']:
                values = [r.get(metric, 0) for r in exp_results if metric in r]
                if values:
                    metrics[metric] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'min': np.min(values),
                        'max': np.max(values)
                    }

            report[exp_name] = {
                'name': exp_config['name'],
                'description': exp_config['description'],
                'filter_type': exp_config['filter']['type'],
                'metrics': metrics
            }

        # 保存报告
        report_file = self.output_dir / f"ablation_report_{self.timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        # 打印摘要
        print("\n实验摘要:")
        for exp_name, exp_report in report.items():
            print(f"\n{exp_report['name']}:")
            print(f"  滤波器: {exp_report['filter_type']}")
            if 'success_rate' in exp_report['metrics']:
                sr = exp_report['metrics']['success_rate']
                print(f"  成功率: {sr['mean']:.1f}% ± {sr['std']:.1f}%")
            if 'normalized_jerk' in exp_report['metrics']:
                nj = exp_report['metrics']['normalized_jerk']
                print(f"  归一化 Jerk: {nj['mean']:.2f} ± {nj['std']:.2f}")

        # 生成对比图表
        if self.config['ablation_study']['generate_plots']:
            self._generate_plots(report)

    def _generate_plots(self, report):
        """生成对比图表"""
        try:
            import matplotlib.pyplot as plt

            print("\n📈 生成对比图表...")

            # 提取数据
            exp_names = [r['name'] for r in report.values()]
            metrics_to_plot = ['success_rate', 'normalized_jerk', 'tracking_error']

            fig, axes = plt.subplots(1, len(metrics_to_plot), figsize=(15, 5))

            for i, metric in enumerate(metrics_to_plot):
                means = []
                stds = []
                for exp_report in report.values():
                    if metric in exp_report['metrics']:
                        means.append(exp_report['metrics'][metric]['mean'])
                        stds.append(exp_report['metrics'][metric]['std'])
                    else:
                        means.append(0)
                        stds.append(0)

                axes[i].bar(range(len(exp_names)), means, yerr=stds, capsize=5)
                axes[i].set_xticks(range(len(exp_names)))
                axes[i].set_xticklabels(exp_names, rotation=45, ha='right')
                axes[i].set_ylabel(metric.replace('_', ' ').title())
                axes[i].set_title(f'{metric.replace("_", " ").title()} Comparison')
                axes[i].grid(True, alpha=0.3)

            plt.tight_layout()
            plot_file = self.output_dir / f"ablation_comparison_{self.timestamp}.png"
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            print(f"✅ 图表已保存: {plot_file}")

        except ImportError:
            print("⚠️  matplotlib 未安装，跳过图表生成")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VIST 消融实验自动化脚本")
    parser.add_argument("--config", type=str, default="config/ablation_config.yaml",
                        help="消融实验配置文件")

    args = parser.parse_args()

    # 创建消融实验管理器
    study = AblationStudy(config_file=args.config)

    # 运行所有实验
    study.run_all_experiments()


if __name__ == "__main__":
    main()