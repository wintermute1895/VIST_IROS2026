#!/usr/bin/env python3
"""
关节方向测试脚本（应用 joint_directions 变换）
测试 joint_directions 的效果

Author: VIST Project
Date: 2026-02-21
"""

import sys
import time
import numpy as np
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 添加 LBot SDK 路径
sdk_path = project_root / "src" / "robot" / "sdk" / "linkerarm"
if not sdk_path.exists():
    raise ImportError(f"无法找到 LBot SDK: {sdk_path}")
sys.path.insert(0, str(sdk_path))

# 导入配置和机器人接口
from config.config_loader import VISTConfig
from lbot.lbot_robot import LbotRobot, LbotArm


class JointDirectionTesterWithTransforms:
    """关节方向测试器（应用完整变换）"""

    def __init__(self, config_path=None):
        """初始化测试器"""
        if config_path is None:
            config_path = project_root / "config" / "system_config.yaml"

        print("=" * 70)
        print("关节方向测试脚本（完整变换版本）")
        print("=" * 70)
        print(f"\n加载配置文件: {config_path}")

        self.config = VISTConfig(str(config_path))

        # 获取配置参数
        self.robot_ip = self.config.hardware_robot_ip
        self.arm_side = self.config.hardware_arm_side
        self.joint_directions = self.config.robot_joint_directions
        self.joint_limits = self.config.robot_joint_limits

        print(f"机器人 IP: {self.robot_ip}")
        print(f"使用手臂: {self.arm_side}")
        print(f"关节方向配置: {self.joint_directions}")

        # 测试参数
        self.test_angle = np.deg2rad(30)  # 测试角度：30度
        self.test_speed = 0.05  # 测试速度：0.05 rad/s
        self.test_accel = 0.05  # 测试加速度：0.05 rad/s²

        # 机器人接口
        self.robot = None
        self.arm = LbotArm.LEFT_ARM if self.arm_side == "left" else LbotArm.RIGHT_ARM

        print(f"\n测试参数:")
        print(f"  测试角度: {np.rad2deg(self.test_angle):.1f}°")
        print(f"  测试速度: {self.test_speed} rad/s")
        print(f"  测试加速度: {self.test_accel} rad/s²")

    def apply_transforms(self, q_logical):
        """
        应用变换（只使用 joint_directions）

        Args:
            q_logical: 逻辑关节角度（IK输出）

        Returns:
            q_hardware: 硬件关节角度（发送给SDK）
        """
        q_transformed = q_logical.copy()

        # 应用 joint_directions
        for idx in range(len(q_transformed)):
            q_transformed[idx] *= self.joint_directions[idx]

        return q_transformed

    def connect(self):
        """连接到机器人"""
        print(f"\n正在连接到机器人 {self.robot_ip}...")
        self.robot = LbotRobot(self.robot_ip)

        if not self.robot.connect(timeout=10.0):
            print("❌ 连接失败")
            return False

        print("✅ 连接成功")

        # 使能机械臂
        print(f"正在使能 {self.arm_side} 机械臂...")
        if not self.robot.enable_arm(self.arm, True):
            print("❌ 使能失败")
            return False

        print("✅ 机械臂已使能")
        return True

    def disconnect(self):
        """断开连接"""
        if self.robot:
            print("\n正在断开连接...")
            self.robot.enable_arm(self.arm, False)
            self.robot.disconnect()

    def get_current_joints(self):
        """获取当前关节角度（硬件角度）"""
        joints = self.robot.get_joint_positions(self.arm)
        if joints is None:
            raise RuntimeError("无法获取关节位置")
        return np.array(joints)

    def move_to_joints_logical(self, q_logical, description=""):
        """
        移动到逻辑关节角度（应用完整变换）

        Args:
            q_logical: 逻辑关节角度（就像IK输出的角度）
        """
        if description:
            print(f"  {description}")

        # 应用完整变换链
        q_hardware = self.apply_transforms(q_logical)

        print(f"  逻辑角度: {np.rad2deg(q_logical)}")
        print(f"  硬件角度: {np.rad2deg(q_hardware)}")

        success = self.robot.move_to_joint_target(
            self.arm,
            q_hardware.tolist(),
            speed=self.test_speed,
            accel=self.test_accel,
            block=True
        )

        if not success:
            print("  ❌ 运动指令发送失败")
            return False

        time.sleep(2.0)
        return True

    def test_joint(self, joint_idx):
        """测试单个关节的方向"""
        print(f"\n{'=' * 70}")
        print(f"测试关节 {joint_idx}")
        print(f"{'=' * 70}")

        # 获取当前硬件角度
        print("获取当前关节位置...")
        q_hardware_current = self.get_current_joints()

        # 为了测试，我们假设当前位置就是"逻辑零位"
        # 在实际系统中，这个映射会更复杂
        q_logical_current = np.zeros(7)

        print(f"当前硬件角度: {np.rad2deg(q_hardware_current)}")

        # 检查关节限位
        joint_min, joint_max = self.joint_limits[joint_idx]

        print(f"\n关节 {joint_idx} 信息:")
        print(f"  限位范围: [{np.rad2deg(joint_min):.1f}°, {np.rad2deg(joint_max):.1f}°]")
        print(f"  joint_directions[{joint_idx}]: {self.joint_directions[joint_idx]}")

        # 计算逻辑目标位置（+30°）
        q_logical_target = q_logical_current.copy()
        q_logical_target[joint_idx] = self.test_angle

        print(f"\n开始测试:")
        print(f"  逻辑目标: 关节{joint_idx} = +30°")
        print(f"  预期效果: 关节{joint_idx} 应该按照配置的方向转动")

        # 移动到目标位置
        if not self.move_to_joints_logical(q_logical_target, "正在移动到测试位置..."):
            return False

        # 等待用户确认
        print("\n" + "=" * 70)
        print("请观察机械臂的运动方向")
        print("=" * 70)

        response = input("\n关节运动方向是否正确？(y/n/s=跳过): ").strip().lower()

        if response == 's':
            print("⏭️  跳过此关节")
            self.move_to_joints_logical(q_logical_current, "返回原位...")
            return None

        is_correct = (response == 'y')

        if is_correct:
            print("✅ 方向正确")
        else:
            print("❌ 方向错误")
            print("   需要修改 joint_directions 或 joint_sign_flip")

        # 返回原位
        print("\n返回原位...")
        if not self.move_to_joints_logical(q_logical_current, "正在返回..."):
            return False

        return is_correct

    def run_test(self):
        """运行完整测试"""
        print("\n" + "=" * 70)
        print("开始关节方向测试（完整变换）")
        print("=" * 70)

        if not self.connect():
            return

        try:
            results = {}

            for joint_idx in range(7):
                result = self.test_joint(joint_idx)
                results[joint_idx] = result

                if result is False:
                    response = input("\n测试失败，是否继续？(y/n): ").strip().lower()
                    if response != 'y':
                        break

            # 打印测试总结
            print("\n" + "=" * 70)
            print("测试总结")
            print("=" * 70)

            for joint_idx, result in results.items():
                if result is None:
                    status = "⏭️  跳过"
                elif result:
                    status = "✅ 正确"
                else:
                    status = "❌ 错误"

                print(f"关节 {joint_idx}: {status}")

            errors = [idx for idx, result in results.items() if result is False]
            if errors:
                print(f"\n⚠️ 发现 {len(errors)} 个关节方向错误: {errors}")
                print("\n需要调整配置文件:")
                print("  文件: config/system_config.yaml")
                print("  位置: robot.joint_directions")
                print("  将错误关节的方向系数取反（1 → -1 或 -1 → 1）")
            else:
                print("\n✅ 所有测试通过！")

        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断测试")
            self.robot.emergency_stop(self.arm, True)

        except Exception as e:
            print(f"\n❌ 测试过程中出错: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.disconnect()


def main():
    """主函数"""
    print("\n⚠️  安全提示:")
    print("1. 确保机械臂周围没有障碍物")
    print("2. 准备好紧急停止按钮")
    print("3. 测试过程中请保持注意力集中")
    print("4. 如有异常，立即按 Ctrl+C 中断")

    response = input("\n是否继续？(y/n): ").strip().lower()
    if response != 'y':
        print("测试取消")
        return

    tester = JointDirectionTesterWithTransforms()
    tester.run_test()


if __name__ == "__main__":
    main()
