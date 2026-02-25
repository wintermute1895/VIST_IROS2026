# 机械臂使能操作指南
# Robot Arm Enable/Disable Guide

## 重要说明 ⚠️

**代码中没有自动使能功能，这是安全设计！**

所有的使能和急停操作都需要手动执行，确保操作者完全掌控机械臂状态。

## 使能服务

机械臂提供以下ROS2服务：

### 1. 使能服务 (SetEnable)
```bash
# 服务名称
/left_arm/set_enable
/right_arm/set_enable

# 服务类型
lbot_arm_interfaces/srv/SetEnable

# 请求参数
bool enable  # true=使能, false=失能

# 响应
bool success
```

### 2. 急停服务 (SetEmergency)
```bash
# 服务名称
/left_arm/set_emergency_stop
/right_arm/set_emergency_stop

# 服务类型
lbot_arm_interfaces/srv/SetEmergency

# 请求参数
bool emergency  # true=急停, false=解除急停

# 响应
bool success
```

## 操作流程

### 启动前检查

1. **确认机械臂状态**
```bash
# 检查服务是否可用
ros2 service list | grep set_enable
ros2 service list | grep emergency
```

2. **确认当前状态**
```bash
# 查看机械臂状态话题
ros2 topic echo /robot1/right_arm/joint_states --once
```

### 使能机械臂（右臂）

#### 方法1: 使用ros2命令行

```bash
# 1. 解除急停（如果处于急停状态）
ros2 service call /right_arm/set_emergency_stop \
  lbot_arm_interfaces/srv/SetEmergency \
  "{emergency: false}"

# 等待2秒

# 2. 使能机械臂
ros2 service call /right_arm/set_enable \
  lbot_arm_interfaces/srv/SetEnable \
  "{enable: true}"

# 确认使能成功
# 观察机械臂是否有轻微的伺服声音
```

#### 方法2: 使用Python脚本

创建 `scripts/enable_right_arm.py`:

```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.srv import SetEnable, SetEmergency
import sys

class ArmEnableClient(Node):
    def __init__(self):
        super().__init__('arm_enable_client')

        # 创建服务客户端
        self.enable_client = self.create_client(
            SetEnable,
            '/right_arm/set_enable'
        )
        self.emergency_client = self.create_client(
            SetEmergency,
            '/right_arm/set_emergency_stop'
        )

    def release_emergency(self):
        """解除急停"""
        self.get_logger().info('解除急停...')

        if not self.emergency_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('急停服务不可用')
            return False

        request = SetEmergency.Request()
        request.emergency = False

        future = self.emergency_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() and future.result().success:
            self.get_logger().info('✓ 急停已解除')
            return True
        else:
            self.get_logger().error('✗ 解除急停失败')
            return False

    def enable_arm(self):
        """使能机械臂"""
        self.get_logger().info('使能机械臂...')

        if not self.enable_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('使能服务不可用')
            return False

        request = SetEnable.Request()
        request.enable = True

        future = self.enable_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() and future.result().success:
            self.get_logger().info('✓ 机械臂已使能')
            return True
        else:
            self.get_logger().error('✗ 使能失败')
            return False

    def disable_arm(self):
        """失能机械臂"""
        self.get_logger().info('失能机械臂...')

        if not self.enable_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error('使能服务不可用')
            return False

        request = SetEnable.Request()
        request.enable = False

        future = self.enable_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if future.result() and future.result().success:
            self.get_logger().info('✓ 机械臂已失能')
            return True
        else:
            self.get_logger().error('✗ 失能失败')
            return False

def main():
    rclpy.init()

    if len(sys.argv) < 2:
        print("用法: python3 enable_right_arm.py <enable|disable>")
        print("  enable  - 解除急停并使能机械臂")
        print("  disable - 失能机械臂")
        sys.exit(1)

    action = sys.argv[1]
    client = ArmEnableClient()

    try:
        if action == 'enable':
            print("\n⚠️  准备使能机械臂")
            print("⚠️  确保工作空间安全")
            input("按Enter键继续...")

            # 解除急停
            if not client.release_emergency():
                sys.exit(1)

            # 等待2秒
            import time
            time.sleep(2)

            # 使能
            if not client.enable_arm():
                sys.exit(1)

            print("\n✓ 机械臂已使能，可以开始控制")

        elif action == 'disable':
            if not client.disable_arm():
                sys.exit(1)
            print("\n✓ 机械臂已失能")

        else:
            print(f"未知操作: {action}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n操作已取消")
    finally:
        client.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
```

使用方法:
```bash
# 使能机械臂
python3 scripts/enable_right_arm.py enable

# 失能机械臂
python3 scripts/enable_right_arm.py disable
```

### 失能机械臂（右臂）

```bash
# 失能机械臂
ros2 service call /right_arm/set_enable \
  lbot_arm_interfaces/srv/SetEnable \
  "{enable: false}"

# 或触发急停
ros2 service call /right_arm/set_emergency_stop \
  lbot_arm_interfaces/srv/SetEmergency \
  "{emergency: true}"
```

## 完整测试流程（含使能步骤）

### Terminal 1: 启动外骨骼
```bash
ros2 run linkerta linkerta_node --ros-args \
  -p publish_left:=false -p publish_right:=true
```

### Terminal 2: 启动滤波节点
```bash
cd /home/ilex/Dev/VIST
./scripts/start_right_arm_filter.sh none
```

### Terminal 3: 启动teleop_bridge
```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop
ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file src/lbot_teleop/config/teleop_bridge_params.yaml \
  -p master_right_topic:=/filtered_right_joint_control
```

### Terminal 4: 使能机械臂 ⚠️
```bash
cd /home/ilex/Dev/VIST

# 使能右臂
python3 scripts/enable_right_arm.py enable

# 或使用命令行
ros2 service call /right_arm/set_emergency_stop \
  lbot_arm_interfaces/srv/SetEmergency "{emergency: false}"

sleep 2

ros2 service call /right_arm/set_enable \
  lbot_arm_interfaces/srv/SetEnable "{enable: true}"
```

### Terminal 5: 数据采集
```bash
cd /home/ilex/Dev/VIST
./scripts/collect_right_arm_data.sh exp0_no_filter 30
```

## 安全注意事项

### 使能前
- [ ] 确认工作空间清空
- [ ] 确认机械臂位置安全
- [ ] 确认急停按钮可用
- [ ] 确认所有节点正常运行

### 使能后
- [ ] 观察机械臂是否有异常
- [ ] 缓慢移动外骨骼测试响应
- [ ] 随时准备按下急停

### 紧急情况
1. **立即按下物理急停按钮**
2. 或执行软急停:
```bash
ros2 service call /right_arm/set_emergency_stop \
  lbot_arm_interfaces/srv/SetEmergency "{emergency: true}"
```

## 状态检查

### 检查机械臂是否使能
```bash
# 查看机械臂状态
ros2 topic echo /robot1/right_arm/joint_states

# 如果使能成功，应该能看到实时的关节状态更新
```

### 检查控制流是否正常
```bash
# 检查话题频率
ros2 topic hz /filtered_right_joint_control
ros2 topic hz /robot1/right_arm/joint_follow

# 应该都在 70-90 Hz
```

## 常见问题

### Q1: 使能服务调用失败
```bash
# 检查lbot_driver是否运行
ros2 node list | grep lbot_driver

# 检查服务是否存在
ros2 service list | grep set_enable
```

### Q2: 使能后机械臂不动
- 检查teleop_bridge是否收到数据
- 检查外骨骼是否正常发布数据
- 检查滤波节点是否正常工作

### Q3: 如何确认机械臂已使能
- 使能后会听到轻微的伺服电机声音
- 关节状态话题会有实时更新
- 移动外骨骼时机械臂会响应

---

**重要**: 所有使能操作都是手动的，代码不会自动使能机械臂。这是安全设计的核心原则。

更新日期: 2026-02-25