#!/usr/bin/env python3
"""
完整实验数据采集脚本 (Python 版本)
包含：相机、左臂外骨骼、灵巧手、机械臂
动态读取 config/recording_config.yaml 配置文件
"""

import os
import sys
import yaml
import subprocess
import signal
import time
import threading
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# ============================================================================
# 颜色定义
# ============================================================================
class Colors:
    """终端颜色代码"""
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color

    @staticmethod
    def green(text: str) -> str:
        return f"{Colors.GREEN}{text}{Colors.NC}"

    @staticmethod
    def blue(text: str) -> str:
        return f"{Colors.BLUE}{text}{Colors.NC}"

    @staticmethod
    def yellow(text: str) -> str:
        return f"{Colors.YELLOW}{text}{Colors.NC}"

    @staticmethod
    def red(text: str) -> str:
        return f"{Colors.RED}{text}{Colors.NC}"


# ============================================================================
# 全局变量
# ============================================================================
countdown_thread: Optional[threading.Thread] = None
stop_countdown = threading.Event()
record_process: Optional[subprocess.Popen] = None
interrupted = False  # 标记是否被 Ctrl+C 中断


# ============================================================================
# 信号处理
# ============================================================================
def signal_handler(signum, frame):
    """
    处理 Ctrl+C 信号
    优雅地停止录制进程，确保 rosbag2 数据库不损坏
    设置中断标志，但不抛出异常，让主函数正常完成
    """
    global interrupted

    print()
    print(Colors.yellow("收到中断信号，正在停止录制..."))

    interrupted = True

    # 停止倒计时线程
    stop_countdown.set()
    if countdown_thread and countdown_thread.is_alive():
        countdown_thread.join(timeout=1)

    # 向录制进程发送 SIGINT 信号（不是 SIGKILL！）
    # 这样 ros2 bag record 可以正常关闭数据库
    if record_process and record_process.poll() is None:
        try:
            # 第一次尝试：发送 SIGINT
            record_process.send_signal(signal.SIGINT)
            print(Colors.yellow("等待录制进程正常退出（最多60秒）..."))
            record_process.wait(timeout=60)
            print(Colors.green("录制进程已正常退出"))
        except subprocess.TimeoutExpired:
            # 第二次尝试：发送 SIGTERM
            print(Colors.yellow("SIGINT 超时，尝试发送 SIGTERM..."))
            try:
                record_process.send_signal(signal.SIGTERM)
                record_process.wait(timeout=20)
                print(Colors.green("录制进程已退出"))
            except subprocess.TimeoutExpired:
                # 最后手段：强制终止
                print(Colors.red("录制进程未响应，强制终止"))
                print(Colors.red("警告: 数据库文件可能损坏！"))
                record_process.kill()
                record_process.wait()
        except Exception as e:
            print(Colors.red(f"停止录制进程时出错: {e}"))

    print(Colors.green("已停止录制"))


# ============================================================================
# 配置读取
# ============================================================================
def load_recording_config(config_path: str) -> Dict:
    """
    读取录制配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(Colors.red(f"错误: 配置文件不存在: {config_path}"))
        sys.exit(1)
    except yaml.YAMLError as e:
        print(Colors.red(f"错误: 配置文件格式错误: {e}"))
        sys.exit(1)


def load_filter_type_from_baseline_config(project_root: Path) -> str:
    """
    从 baseline_filters_config.yaml 读取滤波器类型

    Args:
        project_root: 项目根目录

    Returns:
        滤波器类型 (vist, oneeuro, kalman, none)
    """
    config_path = project_root / 'config' / 'baseline_filters_config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        # 从 /vist_filter_node/ros__parameters/filter_type 路径提取
        # 注意：YAML 中的键是 '/vist_filter_node'（带斜杠）
        filter_type = config.get('/vist_filter_node', {}).get('ros__parameters', {}).get('filter_type', 'vist')
        return filter_type
    except FileNotFoundError:
        print(Colors.yellow(f"⚠ 配置文件不存在: {config_path}，使用默认值 'vist'"))
        return 'vist'
    except yaml.YAMLError as e:
        print(Colors.yellow(f"⚠ 配置文件格式错误: {e}，使用默认值 'vist'"))
        return 'vist'


def extract_enabled_topics(config: Dict) -> List[str]:
    """
    从配置中提取所有 enabled: true 的话题（静默）

    Args:
        config: 配置字典

    Returns:
        话题列表
    """
    topics = []
    topics_config = config.get('topics', {})

    for _, topic_info in topics_config.items():
        if isinstance(topic_info, dict):
            if topic_info.get('enabled', False):
                topic = topic_info.get('topic')
                if topic:
                    topics.append(topic)

    return topics


# ============================================================================
# ROS2 节点检查
# ============================================================================
def check_ros2_nodes(required_nodes: List[str]) -> List[str]:
    """
    检查必要的 ROS2 节点是否在运行

    Args:
        required_nodes: 必需的节点列表

    Returns:
        缺失的节点列表
    """
    try:
        result = subprocess.run(
            ['ros2', 'node', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        running_nodes = result.stdout.strip().split('\n')

        missing_nodes = []
        for node in required_nodes:
            if node not in running_nodes:
                missing_nodes.append(node)

        return missing_nodes
    except subprocess.TimeoutExpired:
        print(Colors.red("错误: ros2 node list 超时"))
        return required_nodes
    except Exception as e:
        print(Colors.red(f"错误: 检查节点时出错: {e}"))
        return required_nodes


# ============================================================================
# 倒计时显示
# ============================================================================
def countdown_display(duration: int):
    """
    在终端显示倒计时

    Args:
        duration: 倒计时秒数
    """
    for i in range(duration, 0, -1):
        if stop_countdown.is_set():
            break
        print(f"\r剩余时间: {i} 秒   ", end='', flush=True)
        time.sleep(1)

    if not stop_countdown.is_set():
        print("\r录制完成！           ")


# ============================================================================
# 元数据生成
# ============================================================================
def generate_metadata(data_dir: str, experiment_name: str, duration: int,
                     topics: List[str], config: Dict, filter_type: str):
    """
    生成实验元数据文件（静默）

    Args:
        data_dir: 数据目录
        experiment_name: 实验名称
        duration: 录制时长
        topics: 录制的话题列表
        config: 配置字典
        filter_type: 滤波器类型（从 baseline_filters_config.yaml 读取）
    """
    metadata = {
        'experiment': {
            'name': experiment_name,
            'type': 'teleoperation_experiment',
            'duration': f'{duration}s',
            'timestamp': datetime.now().isoformat(),
            'task_label': config.get('experiment', {}).get('task_label', ''),
            'filter_type': filter_type
        },
        'components': [
            {'camera': 'RealSense D435i'},
            {'left_arm': 'Linkerta Exoskeleton'},
            {'dexterous_hand': 'Linker Hand L10 (Left)'},
            {'robot': 'Controlled Robot Arm'}
        ],
        'recorded_topics': topics,
        'config': {
            'recording_mode': config.get('recording_mode', {}),
            'frequency_analysis': config.get('frequency_analysis', {}),
            'quality_checks': config.get('quality_checks', {})
        }
    }

    metadata_path = os.path.join(data_dir, 'experiment_metadata.yaml')
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True)
    except Exception:
        pass  # 静默失败


# ============================================================================
# 意图因子数据提取和可视化
# ============================================================================
def extract_and_visualize_intent_factors(data_dir: str):
    """
    从rosbag中提取VIST意图因子数据并生成可视化

    Args:
        data_dir: 实验数据目录
    """
    try:
        from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
        from rclpy.serialization import deserialize_message
        from std_msgs.msg import Float64MultiArray
    except ImportError as e:
        print(Colors.yellow(f"⚠ 无法导入ROS2库，跳过意图因子提取: {e}"))
        return

    print()
    print(Colors.yellow("提取VIST意图因子数据..."))

    storage_options = StorageOptions(uri=str(data_dir), storage_id='sqlite3')
    converter_options = ConverterOptions(
        input_serialization_format='cdr',
        output_serialization_format='cdr'
    )

    try:
        reader = SequentialReader()
        reader.open(storage_options, converter_options)
    except Exception as e:
        print(Colors.yellow(f"⚠ 无法打开rosbag: {e}"))
        return

    alpha_list = []
    alpha_distance_list = []
    alpha_velocity_list = []
    alpha_alignment_list = []
    q_norm_list = []
    r_norm_list = []
    k_norm_list = []
    timestamps = []

    topic = '/vist_intent_factors'
    while reader.has_next():
        topic_name, data, timestamp = reader.read_next()
        if topic_name == topic:
            try:
                msg = deserialize_message(data, Float64MultiArray)
                if len(msg.data) >= 7:
                    alpha_list.append(msg.data[0])
                    alpha_distance_list.append(msg.data[1])
                    alpha_velocity_list.append(msg.data[2])
                    alpha_alignment_list.append(msg.data[3])
                    q_norm_list.append(msg.data[4])
                    r_norm_list.append(msg.data[5])
                    k_norm_list.append(msg.data[6])
                    timestamps.append(timestamp * 1e-9)
            except Exception:
                continue

    if not alpha_list:
        print(Colors.yellow("⚠ 未找到意图因子数据"))
        return

    print(Colors.green(f"✓ 提取到 {len(alpha_list)} 个意图因子样本"))

    # 归零时间戳
    t0 = timestamps[0]
    timestamps_relative = [t - t0 for t in timestamps]

    # 保存原始时间序列数据 - 每一行对应一个时间点的所有数据
    timeseries_data = []
    for i in range(len(timestamps)):
        timeseries_data.append({
            'time': timestamps_relative[i],
            'alpha': alpha_list[i],
            'alpha_velocity': alpha_velocity_list[i],
            'alpha_distance': alpha_distance_list[i],
            'alpha_alignment': alpha_alignment_list[i],
            'q_norm': q_norm_list[i],
            'r_norm': r_norm_list[i],
            'k_norm': k_norm_list[i]
        })

    timeseries_file = os.path.join(data_dir, 'intent_factors_timeseries.json')
    try:
        with open(timeseries_file, 'w') as f:
            json.dump(timeseries_data, f, indent=2)
        print(Colors.green(f"✓ 时间序列数据已保存: intent_factors_timeseries.json"))
    except Exception as e:
        print(Colors.yellow(f"⚠ 保存时间序列失败: {e}"))
        return

    # 生成可视化
    print(Colors.yellow("生成意图因子可视化..."))
    try:
        # 使用归零后的时间戳
        t = np.array(timestamps_relative)
        alpha = np.array(alpha_list)
        alpha_velocity = np.array(alpha_velocity_list)
        alpha_distance = np.array(alpha_distance_list)
        k_norm = np.array(k_norm_list)

        # 创建3个子图
        fig, axes = plt.subplots(3, 1, figsize=(15, 10))

        # α总意图因子
        ax = axes[0]
        ax.plot(t, alpha, 'b-', linewidth=1.5, label='α (total)')
        ax.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Precision threshold')
        ax.fill_between(t, 0.5, 1.0, alpha=0.1, color='red', label='Precision mode')
        ax.fill_between(t, 0.0, 0.5, alpha=0.1, color='green', label='Free mode')
        ax.set_ylabel('α')
        ax.set_title('VIST Intent Factor α')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_ylim([0, 1])

        # α分量对比
        ax = axes[1]
        ax.plot(t, alpha_velocity, 'g-', linewidth=1.5, label='α_velocity', alpha=0.7)
        ax.plot(t, alpha_distance, 'orange', linewidth=1.5, label='α_distance', alpha=0.7)
        ax.set_ylabel('α components')
        ax.set_title('Intent Factor Components')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_ylim([0, 1])

        # 卡尔曼增益
        ax = axes[2]
        ax.plot(t, k_norm, 'red', linewidth=1.5, label='K_norm')
        ax.set_ylabel('K norm')
        ax.set_title('Kalman Gain Norm')
        ax.set_xlabel('Time (s)')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        output_file = os.path.join(data_dir, 'intent_factors.png')
        plt.savefig(output_file, dpi=300)
        plt.close()

        print(Colors.green(f"✓ 可视化已保存: intent_factors.png"))
    except Exception as e:
        print(Colors.yellow(f"⚠ 生成可视化失败: {e}"))


# ============================================================================
# 数据分析联动
# ============================================================================
def prompt_analysis(data_dir: str) -> bool:
    """
    询问用户是否立即运行数据分析

    Args:
        data_dir: 数据目录

    Returns:
        是否运行分析
    """
    print()
    print(Colors.yellow("是否立即运行 analyze_all_metrics.py 进行数据分析？[y/N]: "), end='', flush=True)

    # 等待一小段时间，让标准输入流恢复正常
    time.sleep(0.5)

    try:
        # 使用 sys.stdin 直接读取，更可靠
        import sys
        response = sys.stdin.readline().strip().lower()
        return response in ['y', 'yes']
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def run_analysis(data_dir: str):
    """
    运行数据分析脚本

    Args:
        data_dir: 数据目录
    """
    analysis_script = 'scripts/analysis/analyze_all_metrics.py'

    if not os.path.exists(analysis_script):
        print(Colors.red(f"错误: 分析脚本不存在: {analysis_script}"))
        return

    print()
    print(Colors.blue("========================================"))
    print(Colors.blue("开始数据分析"))
    print(Colors.blue("========================================"))
    print()

    try:
        result = subprocess.run(
            ['python3', analysis_script, '--rosbag', data_dir],
            check=False
        )

        if result.returncode == 0:
            print()
            print(Colors.green("✓ 数据分析完成"))
        else:
            print()
            print(Colors.yellow(f"⚠ 数据分析退出码: {result.returncode}"))
    except Exception as e:
        print(Colors.red(f"错误: 运行分析脚本失败: {e}"))


# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    global countdown_thread, record_process, interrupted

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ========================================
    # 1. 解析命令行参数
    # ========================================
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    experiment_name = sys.argv[2] if len(sys.argv) > 2 else f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 数据保存到外接硬盘
    base_data_dir = "/media/ilex/Cyan_data/data/gello/01_gello_usb_data"
    data_dir = f"{base_data_dir}/{experiment_name}"

    print(Colors.blue("========================================"))
    print(Colors.blue("完整实验数据采集"))
    print(Colors.blue("========================================"))
    print(f"实验名称: {experiment_name}")
    print(f"采集时长: {duration}秒")
    print(f"数据目录: {data_dir}")
    print()

    # ========================================
    # 2. 读取配置文件
    # ========================================
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / 'config' / 'recording_config.yaml'

    print(Colors.yellow("读取配置文件..."))
    print(f"配置文件: {config_path}")
    config = load_recording_config(str(config_path))

    # 从 baseline_filters_config.yaml 读取滤波器类型
    filter_type = load_filter_type_from_baseline_config(project_root)
    print(f"滤波器类型: {filter_type}")

    print()
    print(Colors.yellow("提取启用的话题..."))
    topics = extract_enabled_topics(config)

    if not topics:
        print(Colors.red("错误: 没有启用的话题！"))
        print("请检查 config/recording_config.yaml 中的 topics 配置")
        sys.exit(1)

    print()
    print(Colors.green(f"✓ 共找到 {len(topics)} 个启用的话题"))
    print()

    # ========================================
    # 3. 创建数据目录的父目录
    # ========================================
    # 创建外接硬盘上的基础目录
    os.makedirs(base_data_dir, exist_ok=True)

    # ========================================
    # 4. 检查 ROS2 节点
    # ========================================
    print(Colors.yellow("检查系统状态..."))
    required_nodes = [
        '/camera_global/camera_global',  # D435i 全局相机节点
        '/camera_wrist/camera_wrist',    # D405 腕部相机节点
        '/linker_hand_advanced_l10',  # 灵巧手节点
        '/linkerta_node',  # 外骨骼节点
        '/vist_filter_node',  # VIST 滤波器节点
    ]

    missing_nodes = check_ros2_nodes(required_nodes)

    if missing_nodes:
        print(Colors.red("错误: 以下节点未运行:"))
        for node in missing_nodes:
            print(f"  - {node}")
        print()
        print("请启动完整的遥操作系统：")
        print()
        print("方法 1 - 使用集成启动（推荐）：")
        print("  1. 准备系统: ./scripts/prepare_system.sh")
        print("  2. 启动系统: ros2 launch bringup teleop_system.launch.py")
        print()
        print("方法 2 - 单独启动各模块：")
        print("  1. 准备系统: ./scripts/prepare_system.sh")
        print("  2. 相机: ros2 launch bringup camera.launch.py")
        print("  3. 外骨骼: ros2 launch bringup exoskeleton.launch.py")
        print("  4. 滤波器: ros2 launch bringup vist_filter.launch.py")
        print("  5. 灵巧手: ros2 launch bringup dexterous_hand.launch.py hand_type:=left")
        print("  6. 机械臂: ros2 launch bringup robot_driver.launch.py")
        print("  7. 桥接: ros2 launch bringup teleop_bridge.launch.py")
        sys.exit(1)

    print(Colors.green("✓ 所有节点已就绪"))
    print()

    # ========================================
    # 5. 准备开始采集
    # ========================================
    print(Colors.yellow("准备开始采集..."))
    print("3秒后开始，请准备好操作")
    time.sleep(3)

    print()
    print(Colors.green("========================================"))
    print(Colors.green(f"开始采集数据！录制 {duration} 秒"))
    print(Colors.green("按 Ctrl+C 可以提前停止"))
    print(Colors.green("========================================"))
    print()

    # ========================================
    # 6. 启动倒计时线程
    # ========================================
    countdown_thread = threading.Thread(target=countdown_display, args=(duration,))
    countdown_thread.daemon = True
    countdown_thread.start()

    # ========================================
    # 7. 启动 ROS bag 录制进程（统一录制所有数据）
    # ========================================
    # 所有数据（包括相机）统一保存在 rosbag 中，方便时间戳对齐
    # 直接保存在 data_dir，不使用子目录
    record_cmd = ['ros2', 'bag', 'record', '-o', data_dir] + topics
    record_exit_code = -1  # 默认失败

    try:
        # 不捕获输出，让它直接显示到终端（但会被倒计时覆盖）
        record_process = subprocess.Popen(
            record_cmd,
            stdout=subprocess.DEVNULL,  # 隐藏标准输出
            stderr=subprocess.DEVNULL   # 隐藏错误输出
        )

        # 等待一小段时间，让录制进程初始化
        time.sleep(2)

        # 检查进程是否还在运行
        if record_process.poll() is not None:
            print()
            print(Colors.red(f"❌ 录制启动失败！退出码: {record_process.returncode}"))
            record_exit_code = record_process.returncode
        else:
            # 等待录制完成或超时
            try:
                record_process.wait(timeout=duration)
                record_exit_code = record_process.returncode

            except subprocess.TimeoutExpired:
                # 超时后发送 SIGINT 信号
                print()
                try:
                    record_process.send_signal(signal.SIGINT)
                    record_process.wait(timeout=60)
                    record_exit_code = 0
                except subprocess.TimeoutExpired:
                    record_process.send_signal(signal.SIGTERM)
                    record_process.wait(timeout=20)
                    record_exit_code = 0
            except KeyboardInterrupt:
                if record_process.poll() is not None:
                    record_exit_code = 0
                else:
                    try:
                        record_process.wait(timeout=5)
                        record_exit_code = 0
                    except subprocess.TimeoutExpired:
                        record_exit_code = -1

        if interrupted and record_process.poll() is not None:
            record_exit_code = 0

    except KeyboardInterrupt:
        # 捕获 KeyboardInterrupt，但不退出，继续执行元数据生成
        print()
        print(Colors.yellow("检测到中断信号，继续处理..."))
        if record_process and record_process.poll() is not None:
            record_exit_code = 0
    except Exception as e:
        print()
        print(Colors.red(f"错误: 启动录制失败: {e}"))
        record_exit_code = -1

    # ========================================
    # 8. 停止倒计时
    # ========================================
    stop_countdown.set()
    if countdown_thread.is_alive():
        countdown_thread.join(timeout=1)

    # ========================================
    # 9. 检查录制结果
    # ========================================
    print()
    if record_exit_code == 0:
        print(Colors.green("✓ 数据采集完成！"))
    else:
        print(Colors.red(f"❌ 数据采集失败"))

    print(f"数据保存在: {data_dir}")
    print()

    # ========================================
    # 10. 生成元数据（静默）
    # ========================================
    generate_metadata(data_dir, experiment_name, duration, topics, config, filter_type)

    # ========================================
    # 11. 提取和可视化意图因子（仅当滤波器为vist时）
    # ========================================
    if record_exit_code == 0 and filter_type == 'vist' and '/vist_intent_factors' in topics:
        print(Colors.yellow(f"检测到VIST滤波器，正在提取意图因子..."))
        extract_and_visualize_intent_factors(data_dir)
    elif record_exit_code == 0 and filter_type != 'vist':
        print(Colors.blue(f"当前滤波器类型: {filter_type}，跳过意图因子分析"))

    # ========================================
    # 12. 询问是否运行分析（已注释，避免影响录制进程）
    # ========================================
    # if record_exit_code == 0:
    #     if prompt_analysis(data_dir):
    #         run_analysis(data_dir)

    print()
    print(Colors.blue("========================================"))
    print(Colors.blue("实验数据采集完成"))
    print(Colors.blue("========================================"))


if __name__ == '__main__':
    main()
