#!/usr/bin/env python3
"""
标定系统检查脚本
在开始标定前运行此脚本，检查系统是否正常
"""

import sys
import os
from pathlib import Path

def print_header(text):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_check(text, success=True):
    """打印检查结果"""
    symbol = "✓" if success else "✗"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{symbol}{reset} {text}")

def check_python_version():
    """检查 Python 版本"""
    print_header("检查 Python 环境")

    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print_check("Python 版本符合要求 (>= 3.8)")
        return True
    else:
        print_check("Python 版本过低，需要 >= 3.8", False)
        return False

def check_dependencies():
    """检查依赖库"""
    print_header("检查依赖库")

    all_ok = True

    # 检查 OpenCV
    try:
        import cv2
        version = cv2.__version__
        print_check(f"OpenCV: {version}")

        if tuple(map(int, version.split('.')[:2])) < (4, 7):
            print_check("  警告: OpenCV 版本 < 4.7，建议升级", False)
            all_ok = False
    except ImportError:
        print_check("OpenCV 未安装", False)
        all_ok = False

    # 检查 NumPy
    try:
        import numpy as np
        print_check(f"NumPy: {np.__version__}")
    except ImportError:
        print_check("NumPy 未安装", False)
        all_ok = False

    # 检查 RealSense SDK
    try:
        import pyrealsense2 as rs
        print_check("RealSense SDK: 已安装")
    except ImportError:
        print_check("RealSense SDK 未安装", False)
        all_ok = False

    # 检查 YAML
    try:
        import yaml
        print_check("PyYAML: 已安装")
    except ImportError:
        print_check("PyYAML 未安装", False)
        all_ok = False

    return all_ok

def check_calibration_files():
    """检查标定文件"""
    print_header("检查标定文件")

    all_ok = True

    required_files = [
        "config.py",
        "calibration_solver.py",
        "data_collection.py",
        "robot_interface.py",
        "hand_camera_config.yaml",
        "head_camera_config.yaml"
    ]

    for file in required_files:
        if Path(file).exists():
            print_check(f"{file}")
        else:
            print_check(f"{file} 不存在", False)
            all_ok = False

    return all_ok

def check_config_loading():
    """检查配置加载"""
    print_header("检查配置加载")

    all_ok = True

    try:
        from config import CalibrationConfig

        # 测试默认配置
        config = CalibrationConfig()
        print_check("默认配置加载成功")

        # 测试手内相机配置
        if Path("hand_camera_config.yaml").exists():
            config_hand = CalibrationConfig(config_file="hand_camera_config.yaml")
            print_check(f"手内相机配置: {config_hand.calibration_solver.calibration_type}")

            if config_hand.calibration_solver.calibration_type != "eye_in_hand":
                print_check("  警告: 标定类型应为 eye_in_hand", False)
                all_ok = False

        # 测试头部相机配置
        if Path("head_camera_config.yaml").exists():
            config_head = CalibrationConfig(config_file="head_camera_config.yaml")
            print_check(f"头部相机配置: {config_head.calibration_solver.calibration_type}")

            if config_head.calibration_solver.calibration_type != "eye_to_hand":
                print_check("  警告: 标定类型应为 eye_to_hand", False)
                all_ok = False

    except Exception as e:
        print_check(f"配置加载失败: {e}", False)
        all_ok = False

    return all_ok

def check_robot_sdk():
    """检查机器人 SDK"""
    print_header("检查机器人 SDK")

    sdk_paths = [
        "src/robot/sdk/linkerarm",
        "../src/robot/sdk/linkerarm",
        "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm"
    ]

    found = False
    for path in sdk_paths:
        sdk_path = Path(path)
        if sdk_path.exists():
            lbot_path = sdk_path / "lbot"
            if lbot_path.exists():
                print_check(f"找到 SDK: {path}")
                found = True
                break

    if not found:
        print_check("未找到机器人 SDK", False)
        print("  提示: 请确保 SDK 路径正确配置")
        return False

    return True

def check_camera_connection():
    """检查相机连接"""
    print_header("检查相机连接")

    try:
        import pyrealsense2 as rs

        ctx = rs.context()
        devices = ctx.query_devices()

        if len(devices) == 0:
            print_check("未检测到 RealSense 相机", False)
            print("  提示: 请确保相机已连接并通电")
            return False

        for i, dev in enumerate(devices):
            name = dev.get_info(rs.camera_info.name)
            serial = dev.get_info(rs.camera_info.serial_number)
            print_check(f"相机 {i+1}: {name} (序列号: {serial})")

        return True

    except ImportError:
        print_check("无法检查相机（RealSense SDK 未安装）", False)
        return False
    except Exception as e:
        print_check(f"相机检查失败: {e}", False)
        return False

def check_robot_connection():
    """检查机器人连接"""
    print_header("检查机器人连接")

    import subprocess

    robot_ip = "192.168.10.21"

    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "2", robot_ip],
            capture_output=True,
            timeout=3
        )

        if result.returncode == 0:
            print_check(f"机器人连接正常 ({robot_ip})")
            return True
        else:
            print_check(f"无法连接到机器人 ({robot_ip})", False)
            print("  提示: 请检查网络连接和机器人 IP 地址")
            return False

    except Exception as e:
        print_check(f"连接检查失败: {e}", False)
        return False

def main():
    """主函数"""
    print("\n" + "="*60)
    print("  VIST 标定系统检查")
    print("="*60)

    results = []

    # 运行所有检查
    results.append(("Python 环境", check_python_version()))
    results.append(("依赖库", check_dependencies()))
    results.append(("标定文件", check_calibration_files()))
    results.append(("配置加载", check_config_loading()))
    results.append(("机器人 SDK", check_robot_sdk()))
    results.append(("相机连接", check_camera_connection()))
    results.append(("机器人连接", check_robot_connection()))

    # 打印总结
    print_header("检查总结")

    all_passed = True
    for name, result in results:
        if result:
            print_check(f"{name}: 通过")
        else:
            print_check(f"{name}: 失败", False)
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有检查通过！系统已准备好进行标定。")
    else:
        print("✗ 部分检查失败，请解决上述问题后再开始标定。")
    print("="*60 + "\n")

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
