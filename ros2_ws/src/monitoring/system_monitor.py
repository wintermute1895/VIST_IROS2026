#!/usr/bin/env python3
"""
VIST系统状态管理器
用于Web后端获取真实的系统状态
"""

import socket
import psutil
import time
from typing import Dict, Optional
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config


class VISTSystemMonitor:
    """VIST系统监控器"""

    def __init__(self):
        self.config = get_config()
        self.robot_ip = self.config.hardware_robot_ip
        self.udp_port = self.config.udp_port
        self._robot_connection_cache = None
        self._robot_connection_cache_time = 0
        self._cache_timeout = 2.0  # 缓存2秒

    def is_vision_running(self) -> bool:
        """
        检测视觉节点是否运行
        通过检查进程名来判断
        """
        try:
            # 检查是否有vision_node进程在运行
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('vision_node' in str(arg) for arg in cmdline):
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False

        except Exception as e:
            print(f"检测vision节点失败: {e}")
            return False

    def is_robot_connected(self) -> bool:
        """
        检测机器人是否连接
        通过ping机器人IP地址来判断
        """
        # 使用缓存避免频繁检测
        current_time = time.time()
        if (self._robot_connection_cache is not None and
            current_time - self._robot_connection_cache_time < self._cache_timeout):
            return self._robot_connection_cache

        try:
            # 尝试连接机器人的控制端口（通常是8080或类似端口）
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)

            # LBot API通常使用8080端口
            result = sock.connect_ex((self.robot_ip, 8080))
            sock.close()

            connected = (result == 0)

            # 更新缓存
            self._robot_connection_cache = connected
            self._robot_connection_cache_time = current_time

            return connected

        except Exception as e:
            print(f"检测机器人连接失败: {e}")
            self._robot_connection_cache = False
            self._robot_connection_cache_time = current_time
            return False

    def get_cpu_usage(self) -> float:
        """获取CPU使用率（百分比）"""
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            print(f"获取CPU使用率失败: {e}")
            return 0.0

    def get_memory_usage(self) -> float:
        """获取内存使用率（百分比）"""
        try:
            return psutil.virtual_memory().percent
        except Exception as e:
            print(f"获取内存使用率失败: {e}")
            return 0.0

    def is_recording(self) -> bool:
        """
        检测是否正在录制数据
        通过检查data/experiments目录中是否有正在写入的文件
        """
        try:
            # 使用硬编码的路径，因为配置中没有data_dir属性
            data_dir = project_root / "data" / "experiments"
            if not data_dir.exists():
                return False

            # 检查最近1分钟内修改的文件
            current_time = time.time()
            for file_path in data_dir.rglob('*.csv'):
                if current_time - file_path.stat().st_mtime < 60:
                    return True

            return False

        except Exception as e:
            print(f"检测录制状态失败: {e}")
            return False

    def get_system_status(self) -> Dict:
        """
        获取完整的系统状态

        Returns:
            包含所有系统状态的字典
        """
        return {
            'timestamp': time.time(),
            'vision_running': self.is_vision_running(),
            'robot_connected': self.is_robot_connected(),
            'recording': self.is_recording(),
            'cpu_usage': self.get_cpu_usage(),
            'memory_usage': self.get_memory_usage()
        }

    def get_performance_metrics(self) -> Dict:
        """
        获取性能指标
        TODO: 从实际的控制节点获取这些指标
        """
        return {
            'timestamp': time.time(),
            'tracking_error': 0.0,  # TODO: 从控制节点获取
            'jerk': 0.0,
            'velocity': 0.0,
            'acceleration': 0.0,
            'packet_loss': 0.0
        }

    def get_network_stats(self) -> Dict:
        """获取网络统计信息"""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'errin': net_io.errin,
                'errout': net_io.errout,
                'dropin': net_io.dropin,
                'dropout': net_io.dropout
            }
        except Exception as e:
            print(f"获取网络统计失败: {e}")
            return {}


# 全局实例
_monitor = None

def get_monitor() -> VISTSystemMonitor:
    """获取全局系统监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = VISTSystemMonitor()
    return _monitor


if __name__ == '__main__':
    # 测试代码
    monitor = get_monitor()
    print("=" * 50)
    print("VIST系统状态监控")
    print("=" * 50)

    status = monitor.get_system_status()
    print(f"\n视觉节点运行: {status['vision_running']}")
    print(f"机器人连接: {status['robot_connected']}")
    print(f"正在录制: {status['recording']}")
    print(f"CPU使用率: {status['cpu_usage']:.1f}%")
    print(f"内存使用率: {status['memory_usage']:.1f}%")

    print("\n网络统计:")
    net_stats = monitor.get_network_stats()
    for key, value in net_stats.items():
        print(f"  {key}: {value}")
