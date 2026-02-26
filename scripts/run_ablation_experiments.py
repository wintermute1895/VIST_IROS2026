#!/usr/bin/env python3
"""
VIST消融实验自动化脚本
自动运行所有消融实验配置，记录数据，生成对比报告
"""

import yaml
import subprocess
import time
from pathlib import Path
import sys
import argparse
from datetime import datetime

class AblationExperimentRunner:
    def __init__(self, config_path, duration=200):
        """
        初始化消融实验运行器

        Args:
            config_path: 消融实验配置文件路径
            duration: 每个实验的录制时长（秒）
        """
        self.config_path = Path(config_path)
        self.duration = duration
        self.results_dir = Path("data/ablation_experiments")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # 加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.experiments = self.config['experiments']
        self.execution_order = self.config['execution_order']

    def update_vist_filter_config(self, experiment_config):
        """更新VIST滤波节点配置"""
        filter_config_path = Path("config/vist_filter_config.yaml")

        with open(filter_config_path, 'r', encoding='utf-8') as f:
            filter_config = yaml.safe_load(f)

        # 更新参数
        params = filter_config['vist_filter_node']['ros__parameters']
        params['filter_type'] = experiment_config['filter_type']

        if 'ema_alpha' in experiment_config:
            params['ema_alpha'] = experiment_config['ema_alpha']

        if 'one_euro_min_cutoff' in experiment_config:
            params['one_euro_min_cutoff'] = experiment_config['one_euro_min_cutoff']
        if 'one_euro_beta' in experiment_config:
            params['one_euro_beta'] = experiment_config['one_euro_beta']

        params['enable_distance_factor'] = experiment_config['enable_distance_factor']
        params['enable_velocity_factor'] = experiment_config['enable_velocity_factor']
        params['enable_alignment_factor'] = experiment_config['enable_alignment_factor']
        params['enable_conflict_detection'] = experiment_config['enable_conflict_detection']

        # 保存配置
        with open(filter_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(filter_config, f, allow_unicode=True, default_flow_style=False)

        print(f"  ✓ 更新VIST滤波配置: {experiment_config['filter_type']}")

    def run_experiment(self, experiment_name):
        """运行单个实验"""
        experiment_config = self.experiments[experiment_name]

        print(f"\n{'='*60}")
        print(f"实验: {experiment_config['name']}")
        print(f"描述: {experiment_config['description']}")
        print(f"{'='*60}\n")

        # 更新配置
        self.update_vist_filter_config(experiment_config)

        # 创建实验目录（但不创建rosbag子目录，让ros2 bag record创建）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_dir = self.results_dir / f"{experiment_name}_{timestamp}"
        exp_dir.mkdir(parents=True, exist_ok=True)

        # 保存实验配置
        with open(exp_dir / "experiment_config.yaml", 'w', encoding='utf-8') as f:
            yaml.dump(experiment_config, f, allow_unicode=True, default_flow_style=False)

        print(f"实验目录: {exp_dir}")
        print(f"\n请按以下步骤操作：")
        print(f"1. 启动VIST滤波节点（如果还没启动）")
        print(f"2. 准备好遥操臂和真机")
        print(f"3. 按Enter开始录制{self.duration}秒数据...")

        input()

        # 开始录制
        print(f"\n开始录制 {self.duration} 秒...")
        rosbag_dir = exp_dir / "rosbag"

        # 录制命令（使用timeout限制时长）
        record_cmd = [
            "timeout", f"{self.duration}s",
            "ros2", "bag", "record",
            "-o", str(rosbag_dir),
            "/camera/color/image_raw",
            "/camera/color/camera_info",
            "/cb_left_hand_control_cmd",
            "/cb_left_hand_control_angle_cmd",
            "/filter_performance",
            "/filtered_left_joint_control",
            "/left_arm_joint_control",
            "/parameter_events",
            "/robot1/left_arm/joint_states",
            "/robot1/left_arm/joint_follow",
            "/robot1/left_arm/pose_states",
            "/vist_performance"
        ]

        try:
            # timeout命令会在指定时间后自动终止
            result = subprocess.run(record_cmd, check=False)
            # timeout命令返回124表示超时（正常），0表示正常结束
            if result.returncode in [0, 124]:
                print(f"✓ 录制完成")
            else:
                print(f"❌ 录制失败: 返回码 {result.returncode}")
                return False
        except subprocess.CalledProcessError as e:
            print(f"❌ 录制失败: {e}")
            return False

        # 分析数据
        print(f"\n分析数据...")
        analysis_cmd = [
            "./scripts/run_analysis.sh",
            "--rosbag", str(rosbag_dir),
            "--output", str(exp_dir / "analysis")
        ]

        try:
            # 分析步骤也设置超时（60秒应该足够）
            subprocess.run(analysis_cmd, check=True, timeout=60)
            print(f"✓ 分析完成")
        except subprocess.TimeoutExpired:
            print(f"❌ 分析超时: 执行时间超过 60 秒，任务失败")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ 分析失败: {e}")
            return False

        print(f"\n✓ 实验 '{experiment_config['name']}' 完成")
        print(f"  结果保存在: {exp_dir}")

        return True

    def run_all_experiments(self):
        """运行所有实验"""
        print(f"\n{'='*60}")
        print(f"VIST消融实验自动化")
        print(f"{'='*60}\n")
        print(f"将运行 {len(self.execution_order)} 个实验")
        print(f"每个实验录制 {self.duration} 秒")
        print(f"总预计时间: ~{len(self.execution_order) * (self.duration + 30)} 秒\n")

        print("实验列表:")
        for i, exp_name in enumerate(self.execution_order, 1):
            exp_config = self.experiments[exp_name]
            print(f"  {i}. {exp_config['name']}")

        print(f"\n按Enter开始实验...")
        input()

        results = {}
        for exp_name in self.execution_order:
            success = self.run_experiment(exp_name)
            results[exp_name] = success

            if not success:
                print(f"\n⚠️  实验 '{exp_name}' 失败，是否继续？(y/n)")
                if input().lower() != 'y':
                    break

            # 实验间隔
            if exp_name != self.execution_order[-1]:
                print(f"\n准备下一个实验...")
                print(f"请确保系统状态正常，按Enter继续...")
                input()

        # 打印总结
        print(f"\n{'='*60}")
        print(f"实验总结")
        print(f"{'='*60}\n")

        for exp_name, success in results.items():
            status = "✓ 成功" if success else "❌ 失败"
            print(f"  {self.experiments[exp_name]['name']}: {status}")

        print(f"\n所有结果保存在: {self.results_dir}")
        print(f"\n下一步：运行 generate_ablation_report.py 生成对比报告")

    def run_single_experiment(self, experiment_name):
        """运行单个指定的实验"""
        if experiment_name not in self.experiments:
            print(f"❌ 实验 '{experiment_name}' 不存在")
            print(f"可用实验: {list(self.experiments.keys())}")
            return False

        return self.run_experiment(experiment_name)


def main():
    parser = argparse.ArgumentParser(description='VIST消融实验自动化')
    parser.add_argument('--config', default='config/ablation_experiments.yaml',
                        help='消融实验配置文件路径')
    parser.add_argument('--duration', type=int, default=15,
                        help='每个实验的录制时长（秒）')
    parser.add_argument('--experiment', type=str, default=None,
                        help='只运行指定的实验（不指定则运行全部）')

    args = parser.parse_args()

    runner = AblationExperimentRunner(args.config, args.duration)

    if args.experiment:
        runner.run_single_experiment(args.experiment)
    else:
        runner.run_all_experiments()


if __name__ == '__main__':
    main()