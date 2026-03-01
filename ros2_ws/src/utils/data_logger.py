"""
VIST实验数据记录器 - IROS标准
确保所有实验数据可复现
"""

import numpy as np
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class VISTDataLogger:
    """
    VIST实验数据记录器（IROS可复现性标准）

    功能：
    1. 自动生成唯一的实验ID（timestamp + experiment_name）
    2. 保存配置快照（config_snapshot.json）
    3. 记录所有关键数据（human_input, filtered_output, α, Q, R, P）
    4. 自动化文件命名（防止覆盖）
    5. 支持多次trial记录
    """

    def __init__(
        self,
        experiment_name: str,
        config: Any,
        save_dir: str = 'data/experiments',
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        初始化数据记录器

        Args:
            experiment_name: 实验名称（如 'peg_in_hole', 'usb_insertion'）
            config: VISTConfig实例
            save_dir: 数据保存目录
            metadata: 额外的元数据（如操作员姓名、实验条件等）
        """
        self.experiment_name = experiment_name
        self.config = config
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.metadata = metadata or {}

        # 生成唯一的实验ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.experiment_id = f"{experiment_name}_{timestamp}"

        # 创建实验目录
        self.exp_dir = self.save_dir / self.experiment_id
        self.exp_dir.mkdir(exist_ok=True)

        # 保存配置快照（关键！）
        self._save_config_snapshot()

        # 数据缓冲区
        self.data_buffer = {
            'timestamps': [],
            'human_input': [],      # z_human (关节空间或任务空间)
            'filtered_output': [],  # x_hat (滤波后的状态)
            'alpha_values': [],     # α(t) 意图因子
            'Q_matrices': [],       # Q(t) 过程噪声协方差
            'R_matrices': [],       # R(t) 观测噪声协方差
            'P_matrices': [],       # P(t) 状态协方差（可选）
            'virtual_guidance': [], # 虚拟引导（可选）
        }

        # 统计信息
        self.frame_count = 0
        self.trial_count = 0

        print(f"✅ [DataLogger] 实验ID: {self.experiment_id}")
        print(f"   数据目录: {self.exp_dir}")

    def _save_config_snapshot(self):
        """
        保存配置快照（IROS可复现性要求）

        这是最关键的功能！确保每次实验都记录了使用的参数。
        """
        config_snapshot = {
            'experiment_id': self.experiment_id,
            'experiment_name': self.experiment_name,
            'timestamp': datetime.now().isoformat(),
            'metadata': self.metadata,

            # 论文核心参数（Eq. 2-5）
            'paper_parameters': {
                'W_task': self.config.vist_w_task,
                'alpha_beta': self.config.vist_alpha_beta,
                'w_geo': self.config.vist_w_geo,
                'w_vel': self.config.vist_w_vel,
                'alpha_alignment_power': self.config.vist_alpha_alignment_power,
            },

            # Kalman滤波参数
            'kalman_parameters': {
                'position_variance': self.config.vist_position_variance,
                'velocity_variance': self.config.vist_velocity_variance,
                'human_base_variance': self.config.vist_human_base_variance,
                'human_max_variance': self.config.vist_human_max_variance,
                'virtual_base_variance': self.config.vist_virtual_base_variance,
                'virtual_min_variance': self.config.vist_virtual_min_variance,
                'conflict_gain': self.config.vist_conflict_gain,
            },

            # 控制参数
            'control_parameters': {
                'control_frequency': self.config.control_frequency,
                'control_dt': self.config.control_dt,
                'max_joint_velocity': self.config.max_joint_velocity,
                'max_joint_acceleration': self.config.max_joint_acceleration,
                'ik_strategy': self.config.ik_strategy,
                'ik_gain': self.config.ik_gain,
            },

            # 机器人参数
            'robot_parameters': {
                'n_joints': self.config.vist_n_joints,
                'shoulder_position': self.config.robot_shoulder_position.tolist(),
                'arm_lengths': self.config.robot_arm_lengths,
            },
        }

        # 保存为JSON
        config_file = self.exp_dir / 'config_snapshot.json'
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_snapshot, f, indent=2, ensure_ascii=False)

        print(f"   配置快照: {config_file.name}")

    def log_frame(
        self,
        timestamp: float,
        human_input: np.ndarray,
        filtered_output: np.ndarray,
        alpha: float,
        Q: np.ndarray,
        R: np.ndarray,
        P: Optional[np.ndarray] = None,
        virtual_guidance: Optional[np.ndarray] = None
    ):
        """
        记录单帧数据

        Args:
            timestamp: 时间戳（秒）
            human_input: 人类输入（关节角度或任务空间位置）
            filtered_output: 滤波输出
            alpha: 意图因子
            Q: 过程噪声协方差矩阵
            R: 观测噪声协方差矩阵
            P: 状态协方差矩阵（可选）
            virtual_guidance: 虚拟引导（可选）
        """
        self.data_buffer['timestamps'].append(timestamp)
        self.data_buffer['human_input'].append(human_input.copy())
        self.data_buffer['filtered_output'].append(filtered_output.copy())
        self.data_buffer['alpha_values'].append(alpha)
        self.data_buffer['Q_matrices'].append(Q.copy())
        self.data_buffer['R_matrices'].append(R.copy())

        if P is not None:
            self.data_buffer['P_matrices'].append(P.copy())

        if virtual_guidance is not None:
            self.data_buffer['virtual_guidance'].append(virtual_guidance.copy())

        self.frame_count += 1

    def save(self, trial_number: Optional[int] = None, notes: str = ""):
        """
        保存数据到文件

        Args:
            trial_number: 试验编号（如果是多次试验）
            notes: 备注信息

        Returns:
            保存的文件路径
        """
        if self.frame_count == 0:
            print("⚠️ [DataLogger] 没有数据可保存")
            return None

        # 文件名：{experiment_id}_trial{N}.npz
        if trial_number is not None:
            filename = f"{self.experiment_id}_trial{trial_number:03d}.npz"
            self.trial_count = trial_number
        else:
            self.trial_count += 1
            filename = f"{self.experiment_id}_trial{self.trial_count:03d}.npz"

        filepath = self.exp_dir / filename

        # 转换为numpy数组
        data_to_save = {
            'timestamps': np.array(self.data_buffer['timestamps']),
            'human_input': np.array(self.data_buffer['human_input']),
            'filtered_output': np.array(self.data_buffer['filtered_output']),
            'alpha_values': np.array(self.data_buffer['alpha_values']),
            'Q_matrices': np.array(self.data_buffer['Q_matrices']),
            'R_matrices': np.array(self.data_buffer['R_matrices']),
        }

        # 可选数据
        if self.data_buffer['P_matrices']:
            data_to_save['P_matrices'] = np.array(self.data_buffer['P_matrices'])

        if self.data_buffer['virtual_guidance']:
            data_to_save['virtual_guidance'] = np.array(self.data_buffer['virtual_guidance'])

        # 保存为压缩的npz文件
        np.savez_compressed(filepath, **data_to_save)

        # 保存trial元数据
        trial_metadata = {
            'trial_number': self.trial_count,
            'timestamp': datetime.now().isoformat(),
            'frame_count': self.frame_count,
            'duration': data_to_save['timestamps'][-1] - data_to_save['timestamps'][0],
            'notes': notes,
        }

        metadata_file = self.exp_dir / f"{filename.replace('.npz', '_metadata.json')}"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(trial_metadata, f, indent=2, ensure_ascii=False)

        # 打印统计信息
        file_size = filepath.stat().st_size / (1024 * 1024)
        print(f"\n✅ [DataLogger] 数据已保存")
        print(f"   文件: {filepath.name}")
        print(f"   大小: {file_size:.2f} MB")
        print(f"   帧数: {self.frame_count}")
        print(f"   时长: {trial_metadata['duration']:.2f}s")

        return filepath

    def clear_buffer(self):
        """清空缓冲区（用于多次trial）"""
        for key in self.data_buffer:
            self.data_buffer[key] = []
        self.frame_count = 0
        print(f"🔄 [DataLogger] 缓冲区已清空")

    def get_summary(self) -> Dict[str, Any]:
        """获取实验摘要"""
        return {
            'experiment_id': self.experiment_id,
            'experiment_name': self.experiment_name,
            'exp_dir': str(self.exp_dir),
            'trial_count': self.trial_count,
            'current_frame_count': self.frame_count,
        }

    def __repr__(self):
        return (f"VISTDataLogger(experiment_id='{self.experiment_id}', "
                f"trials={self.trial_count}, frames={self.frame_count})")


def load_experiment_data(experiment_dir: str, trial_number: int = 1) -> Dict[str, np.ndarray]:
    """
    加载实验数据

    Args:
        experiment_dir: 实验目录路径
        trial_number: 试验编号

    Returns:
        包含所有数据的字典
    """
    exp_path = Path(experiment_dir)

    # 查找trial文件
    trial_files = list(exp_path.glob(f"*_trial{trial_number:03d}.npz"))

    if not trial_files:
        raise FileNotFoundError(f"未找到trial {trial_number}的数据文件")

    data_file = trial_files[0]
    print(f"📂 [DataLoader] 加载数据: {data_file.name}")

    # 加载数据
    data = np.load(data_file)

    # 加载元数据
    metadata_file = data_file.parent / f"{data_file.stem}_metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        print(f"   帧数: {metadata['frame_count']}")
        print(f"   时长: {metadata['duration']:.2f}s")

    # 加载配置快照
    config_file = exp_path / 'config_snapshot.json'
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            config_snapshot = json.load(f)
        print(f"   配置: {config_file.name}")

    return dict(data)


# 使用示例
if __name__ == '__main__':
    # 示例：如何使用DataLogger
    print("="*60)
    print("VIST DataLogger 使用示例")
    print("="*60)

    # 模拟配置对象
    class MockConfig:
        vist_w_task = [10.0, 10.0, 10.0, 1.0, 1.0, 1.0]
        vist_alpha_beta = 1.0
        vist_w_geo = 0.5
        vist_w_vel = 0.5
        vist_alpha_alignment_power = 2.0
        vist_position_variance = 1e-4
        vist_velocity_variance = 1e-3
        vist_human_base_variance = 1e-2
        vist_human_max_variance = 1e-1
        vist_virtual_base_variance = 1e-4
        vist_virtual_min_variance = 1e-5
        vist_conflict_gain = 0.5
        control_frequency = 60
        control_dt = 1/60
        max_joint_velocity = 1.0
        max_joint_acceleration = 5.0
        ik_strategy = 'differential'
        ik_gain = 1.0
        vist_n_joints = 7
        robot_shoulder_position = np.array([0, 0, 0.5])
        robot_arm_lengths = {'upper': 0.3, 'forearm': 0.3}

    config = MockConfig()

    # 创建logger
    logger = VISTDataLogger(
        experiment_name='example_test',
        config=config,
        metadata={'operator': 'Test User', 'condition': 'Simulation'}
    )

    # 模拟记录数据
    print("\n模拟记录100帧数据...")
    for i in range(100):
        timestamp = i * 0.01
        human_input = np.random.randn(7)
        filtered_output = np.random.randn(7)
        alpha = np.random.rand()
        Q = np.eye(14) * 0.01
        R = np.eye(7) * 0.1

        logger.log_frame(timestamp, human_input, filtered_output, alpha, Q, R)

    # 保存数据
    logger.save(trial_number=1, notes="测试trial")

    print("\n" + "="*60)
    print("✅ 示例完成！")
    print("="*60)
