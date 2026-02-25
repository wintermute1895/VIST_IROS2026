# VIST系统安全架构重设计 - SDK外层防护方案

**约束条件**: `lbot_driver.cpp` 是厂商SDK，不可修改
**解决方案**: 在ROS2话题层添加安全网关节点

---

## 架构设计

### 原始架构（不安全）
```
外骨骼/视觉 → /xxx_joint_control
                    ↓
              teleop_bridge
                    ↓
         /robot1/right_arm/joint_follow
                    ↓
              lbot_driver (SDK，不可改)
                    ↓
                 固件 (50Hz)
```

### 新架构（安全）
```
外骨骼/视觉 → /xxx_joint_control
                    ↓
              teleop_bridge
                    ↓
         /robot1/right_arm/joint_follow_unsafe  ← 重命名
                    ↓
         🛡️ SAFETY GATEWAY NODE 🛡️  ← 新增！
                    ↓
         /robot1/right_arm/joint_follow  ← 安全的
                    ↓
              lbot_driver (SDK)
                    ↓
                 固件 (50Hz)
```

---

## 核心组件：Safety Gateway Node

### 功能清单

1. ✅ **差分限幅器** (Delta Limiter) - 防止阶跃输入
2. ✅ **NaN/Inf检测** - 防止传感器故障
3. ✅ **心跳检测** - 防止上游卡死
4. ✅ **频率监控** - 防止发送频率异常
5. ✅ **进程互斥** - 防止多实例冲突
6. ✅ **紧急停止** - 一键停机
7. ✅ **黑匣子记录** - 事后分析

---

## 实现代码

### safety_gateway_node.py

```python
#!/usr/bin/env python3
"""
安全网关节点 - SDK外层防护
在不修改厂商SDK的前提下，提供多层安全防护

架构:
  上游 → /robot1/right_arm/joint_follow_unsafe
           ↓
      Safety Gateway (本节点)
           ↓
      /robot1/right_arm/joint_follow → lbot_driver (SDK)

Author: VIST Safety Team
Date: 2026-02-25
"""

import rclpy
from rclpy.node import Node
from lbot_arm_interfaces.msg import FollowJoint
import numpy as np
import time
import json
from pathlib import Path
import fcntl
import os


class SafetyGatewayNode(Node):
    """安全网关节点 - 在SDK外层提供安全防护"""

    def __init__(self):
        super().__init__('safety_gateway_node')

        # ========== 1. 进程互斥检查 ==========
        self.lockfile_path = '/tmp/vist_safety_gateway.lock'
        self.lockfile = None
        if not self._acquire_lock():
            self.get_logger().error('❌ 另一个Safety Gateway正在运行！')
            self.get_logger().error(f'   如果确认无进程，删除: {self.lockfile_path}')
            raise RuntimeError('进程互斥检查失败')

        self.get_logger().info('✅ 进程互斥检查通过')

        # ========== 2. 参数配置 ==========
        self.declare_parameter('arm_side', 'right')
        self.declare_parameter('max_joint_delta', 0.1)  # rad, 50Hz下安全阈值
        self.declare_parameter('heartbeat_timeout', 0.5)  # 秒
        self.declare_parameter('min_publish_hz', 20.0)  # 最低发送频率
        self.declare_parameter('enable_blackbox', True)

        self.arm_side = self.get_parameter('arm_side').value
        self.max_joint_delta = self.get_parameter('max_joint_delta').value
        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self.min_publish_hz = self.get_parameter('min_publish_hz').value
        self.enable_blackbox = self.get_parameter('enable_blackbox').value

        # ========== 3. 状态变量 ==========
        self.last_joints = None
        self.last_cmd_time = None
        self.emergency_stop = False
        self.violation_count = {
            'nan': 0,
            'delta': 0,
            'heartbeat': 0,
            'frequency': 0
        }

        # ========== 4. 黑匣子记录 ==========
        if self.enable_blackbox:
            self._init_blackbox()

        # ========== 5. 创建订阅器和发布器 ==========
        # 订阅不安全的话题
        unsafe_topic = f'/robot1/{self.arm_side}_arm/joint_follow_unsafe'
        self.unsafe_sub = self.create_subscription(
            FollowJoint,
            unsafe_topic,
            self.safety_callback,
            10
        )

        # 发布到安全的话题（SDK订阅）
        safe_topic = f'/robot1/{self.arm_side}_arm/joint_follow'
        self.safe_pub = self.create_publisher(
            FollowJoint,
            safe_topic,
            10
        )

        # 紧急停止服务
        from std_srvs.srv import Trigger
        self.emergency_stop_srv = self.create_service(
            Trigger,
            'emergency_stop',
            self.emergency_stop_callback
        )

        # ========== 6. 心跳检查定时器 ==========
        self.heartbeat_timer = self.create_timer(0.1, self.heartbeat_check)

        self.get_logger().info('=' * 80)
        self.get_logger().info('🛡️  Safety Gateway Node 已启动')
        self.get_logger().info('=' * 80)
        self.get_logger().info(f'订阅: {unsafe_topic}')
        self.get_logger().info(f'发布: {safe_topic}')
        self.get_logger().info(f'最大关节增量: {self.max_joint_delta} rad')
        self.get_logger().info(f'心跳超时: {self.heartbeat_timeout} s')
        self.get_logger().info(f'最低频率: {self.min_publish_hz} Hz')
        self.get_logger().info('=' * 80)

    def _acquire_lock(self):
        """获取进程锁（原子操作）"""
        try:
            self.lockfile = open(self.lockfile_path, 'w')
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lockfile.write(str(os.getpid()))
            self.lockfile.flush()
            return True
        except IOError:
            return False

    def _init_blackbox(self):
        """初始化黑匣子记录"""
        log_dir = Path.home() / 'vist_blackbox'
        log_dir.mkdir(exist_ok=True)

        timestamp = time.strftime('%Y%m%d_%H%M%S')
        self.blackbox_file = log_dir / f'safety_gateway_{timestamp}.jsonl'
        self.get_logger().info(f'📦 黑匣子记录: {self.blackbox_file}')

    def _log_blackbox(self, event_type, data):
        """记录到黑匣子"""
        if not self.enable_blackbox:
            return

        entry = {
            'timestamp': time.time(),
            'event': event_type,
            'data': data
        }

        with open(self.blackbox_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def safety_callback(self, msg):
        """安全检查回调 - 核心逻辑"""

        current_time = time.time()

        # ========== 检查1: 紧急停止 ==========
        if self.emergency_stop:
            self.get_logger().error('🚨 紧急停止激活，拒绝命令')
            return

        # ========== 检查2: 消息有效性 ==========
        if not msg or not msg.joints or len(msg.joints) != 7:
            self.get_logger().error('❌ 无效消息')
            self._log_blackbox('invalid_msg', {'msg': str(msg)})
            return

        joints = np.array(msg.joints)

        # ========== 检查3: NaN/Inf检测 ==========
        if np.any(np.isnan(joints)) or np.any(np.isinf(joints)):
            self.violation_count['nan'] += 1
            self.get_logger().error(f'❌ 检测到NaN/Inf: {joints}')
            self.get_logger().error(f'   累计违规: {self.violation_count["nan"]}次')
            self._log_blackbox('nan_detected', {'joints': joints.tolist()})

            # 连续3次NaN触发紧急停止
            if self.violation_count['nan'] >= 3:
                self.get_logger().error('🚨 连续NaN检测，触发紧急停止')
                self.emergency_stop = True

            return

        # ========== 检查4: 超时检测 ==========
        if self.last_cmd_time is not None:
            elapsed = current_time - self.last_cmd_time

            # 超时检测
            if elapsed > self.heartbeat_timeout:
                self.get_logger().warn(f'⚠️  命令超时: {elapsed:.3f}s')
                self._log_blackbox('timeout', {'elapsed': elapsed})

                # 重置基线（防止超时后大跳变）
                self.last_joints = joints
                self.last_cmd_time = current_time
                return  # 第一帧不执行

            # 频率检测
            actual_hz = 1.0 / elapsed if elapsed > 0 else 0
            if actual_hz < self.min_publish_hz:
                self.violation_count['frequency'] += 1
                self.get_logger().warn(f'⚠️  发送频率过低: {actual_hz:.1f} Hz')

                if self.violation_count['frequency'] >= 10:
                    self.get_logger().error('🚨 频率持续异常，触发紧急停止')
                    self.emergency_stop = True
                    return
            else:
                self.violation_count['frequency'] = 0  # 恢复后重置

        # ========== 检查5: 差分限幅（最关键！）==========
        if self.last_joints is not None:
            delta = joints - self.last_joints
            max_delta = np.max(np.abs(delta))

            if max_delta > self.max_joint_delta:
                self.violation_count['delta'] += 1
                violated_joints = np.where(np.abs(delta) > self.max_joint_delta)[0]

                self.get_logger().error('❌ 关节增量超限！')
                self.get_logger().error(f'   违规关节: {violated_joints}')
                self.get_logger().error(f'   最大增量: {max_delta:.3f} rad (限制: {self.max_joint_delta})')
                self.get_logger().error(f'   delta: {delta[violated_joints]}')

                self._log_blackbox('delta_violation', {
                    'joints': joints.tolist(),
                    'last_joints': self.last_joints.tolist(),
                    'delta': delta.tolist(),
                    'max_delta': float(max_delta),
                    'violated_joints': violated_joints.tolist()
                })

                # 限幅到安全范围
                for i in violated_joints:
                    sign = np.sign(delta[i])
                    joints[i] = self.last_joints[i] + sign * self.max_joint_delta

                self.get_logger().warn(f'   已限幅到: {joints[violated_joints]}')

                # 连续10次限幅触发紧急停止
                if self.violation_count['delta'] >= 10:
                    self.get_logger().error('🚨 连续大跳变，触发紧急停止')
                    self.emergency_stop = True
                    return
            else:
                self.violation_count['delta'] = 0  # 恢复后重置

        # ========== 检查通过，发布安全命令 ==========
        safe_msg = FollowJoint()
        safe_msg.joints = joints.tolist()
        safe_msg.follow = msg.follow

        self.safe_pub.publish(safe_msg)

        # 更新状态
        self.last_joints = joints
        self.last_cmd_time = current_time

        # 记录正常命令（采样记录，避免文件过大）
        if self.enable_blackbox and np.random.random() < 0.01:  # 1%采样率
            self._log_blackbox('normal_cmd', {
                'joints': joints.tolist(),
                'follow': msg.follow
            })

    def heartbeat_check(self):
        """心跳检查定时器"""
        if self.last_cmd_time is None:
            return

        elapsed = time.time() - self.last_cmd_time

        if elapsed > self.heartbeat_timeout:
            self.violation_count['heartbeat'] += 1

            if self.violation_count['heartbeat'] % 10 == 1:  # 每10次打印一次
                self.get_logger().warn(f'⚠️  心跳超时: {elapsed:.3f}s (已{self.violation_count["heartbeat"]}次)')

            # 连续超时30次（3秒）触发紧急停止
            if self.violation_count['heartbeat'] >= 30:
                self.get_logger().error('🚨 心跳长时间超时，触发紧急停止')
                self.emergency_stop = True
        else:
            self.violation_count['heartbeat'] = 0

    def emergency_stop_callback(self, request, response):
        """紧急停止服务"""
        self.emergency_stop = True
        self.get_logger().error('🚨 收到紧急停止请求')
        self._log_blackbox('emergency_stop', {'source': 'service_call'})

        response.success = True
        response.message = 'Emergency stop activated'
        return response

    def destroy_node(self):
        """节点销毁时释放锁"""
        if self.lockfile:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.lockfile.close()
            try:
                os.remove(self.lockfile_path)
            except:
                pass

        self.get_logger().info('🛡️  Safety Gateway Node 已停止')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    try:
        node = SafetyGatewayNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        print('\n⚠️  收到中断信号')
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

---

## 部署方案

### 1. 修改 teleop_bridge 的发布话题

```python
# 在 teleop_bridge_node 中修改
# 原来发布到: /robot1/right_arm/joint_follow
# 现在发布到: /robot1/right_arm/joint_follow_unsafe

self.right_pub = self.create_publisher(
    FollowJoint,
    '/robot1/right_arm/joint_follow_unsafe',  # ← 改这里
    10
)
```

### 2. 启动流程（新增一个终端）

**终端1**: lbot_driver (SDK)
```bash
ros2 run lbot_driver lbot_driver --ros-args -r __ns:=/robot1 -p arm_ip:=192.168.10.21
```

**终端2**: Safety Gateway（新增！）
```bash
ros2 run vist_nodes safety_gateway_node --ros-args \
    -p arm_side:=right \
    -p max_joint_delta:=0.1 \
    -p heartbeat_timeout:=0.5 \
    -p min_publish_hz:=20.0
```

**终端3**: linkerta
```bash
ros2 run linkerta linkerta_node
```

**终端4**: teleop_bridge
```bash
ros2 run lbot_teleop teleop_bridge_node
```

---

## 测试验证

### 测试1: NaN注入
```bash
# 发送NaN命令
ros2 topic pub --once /robot1/right_arm/joint_follow_unsafe lbot_arm_interfaces/msg/FollowJoint \
    "{joints: [nan, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], follow: true}"

# 预期: Safety Gateway拒绝，机器人不动
```

### 测试2: 大跳变
```bash
# 发送大跳变命令
ros2 topic pub --once /robot1/right_arm/joint_follow_unsafe lbot_arm_interfaces/msg/FollowJoint \
    "{joints: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], follow: true}"

# 预期: Safety Gateway限幅到0.1 rad
```

### 测试3: 多实例检测
```bash
# 终端A
ros2 run vist_nodes safety_gateway_node

# 终端B（同时启动）
ros2 run vist_nodes safety_gateway_node

# 预期: 终端B启动失败，提示锁文件被占用
```

### 测试4: 紧急停止
```bash
# 触发紧急停止
ros2 service call /emergency_stop std_srvs/srv/Trigger

# 预期: 所有命令被拒绝
```

---

## 优势

1. ✅ **不修改SDK** - 完全在外层实现
2. ✅ **透明插入** - 只需修改话题名称
3. ✅ **独立进程** - 崩溃不影响SDK
4. ✅ **易于调试** - 可以单独启停
5. ✅ **黑匣子记录** - 事后分析
6. ✅ **进程互斥** - flock原子锁

---

## 下一步

1. 创建 `safety_gateway_node.py` 文件
2. 修改 `teleop_bridge_node` 的发布话题
3. 更新启动文档
4. 进行压力测试

需要我立即创建这些文件吗？