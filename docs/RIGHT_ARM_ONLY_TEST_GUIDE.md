# 右臂单独数据采集测试指南
# Right Arm Only Data Collection Test Guide

## 安全须知 ⚠️

**测试前必读**:
1. 确保急停按钮在手边，随时可以按下
2. 首次测试时保持低速运动
3. 观察机械臂运动是否异常
4. 如有任何异常立即按下急停
5. 确认工作空间内无障碍物和人员

## 测试目标

1. 验证右臂单独控制的完整数据流
2. 建立无滤波基线数据
3. 进行滤波器消融实验
4. 采集性能指标用于论文分析

## 实验设计

### 实验组

| 实验编号 | 滤波器类型 | 参数 | 目的 |
|---------|-----------|------|------|
| Exp0 | none | - | 基线（无滤波） |
| Exp1 | ema | alpha=0.3 | EMA标准参数 |
| Exp2 | ema | alpha=0.5 | EMA弱平滑 |
| Exp3 | one_euro | min_cutoff=1.0, beta=0.007 | One-Euro标准参数 |
| Exp4 | one_euro | min_cutoff=2.0, beta=0.01 | One-Euro高响应 |

### 评估指标

- 轨迹平滑度（Jerk）
- 跟踪误差（RMSE）
- 控制频率稳定性
- 电机负载
- 响应延迟

## 完整测试流程

### 准备阶段

#### 1. 检查硬件状态

```bash
# 检查机械臂连接
ping 192.168.1.18  # 右臂IP

# 检查外骨骼连接
ros2 topic list | grep linkerta
```

#### 2. 确认配置文件

检查 `external_sdk/arm_teleop/src/lbot_teleop/config/teleop_bridge_params.yaml`:

```yaml
teleop_bridge_node:
  ros__parameters:
    # 右臂配置
    master_right_topic: "/right_arm_joint_control"  # 将改为滤波后的话题

    # 左臂配置 - 不使用
    master_left_topic: "/left_arm_joint_control_disabled"  # 禁用左臂

    robot_type: "RS"
    first_move_speed: 0.2
    first_move_acce: 0.2
```

### 实验0: 基线测试（无滤波）

#### Terminal 1: 启动外骨骼数据源

```bash
cd /home/ilex/Dev/VIST

# 启动linkerta（外骨骼桥接）
# 只发布右臂数据
ros2 run linkerta linkerta_node --ros-args \
  -p publish_left:=false \
  -p publish_right:=true
```

#### Terminal 2: 启动无滤波节点（直通模式）

```bash
cd /home/ilex/Dev/VIST

# 无滤波 - 直接透传
python3 src/nodes/unified_filter_node.py --ros-args \
  -p filter_type:=none \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true \
  -p performance_topic:=/filter_performance
```

#### Terminal 3: 启动teleop_bridge

```bash
cd /home/ilex/Dev/VIST/external_sdk/arm_teleop

# 修改配置让teleop_bridge订阅滤波后的话题
# 临时修改: master_right_topic -> /filtered_right_joint_control

ros2 run lbot_teleop teleop_bridge_node --ros-args \
  --params-file src/lbot_teleop/config/teleop_bridge_params.yaml \
  -p master_right_topic:=/filtered_right_joint_control \
  -p master_left_topic:=/left_arm_disabled
```

#### Terminal 4: 数据采集

```bash
cd /home/ilex/Dev/VIST/data

# 创建实验目录
mkdir -p exp_right_arm_only_$(date +%Y%m%d)
cd exp_right_arm_only_$(date +%Y%m%d)

# 记录数据（30秒）
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /robot1/right_arm/joint_follow \
  /robot1/right_arm/joint_states \
  /filter_performance \
  -o exp0_no_filter \
  --duration 30
```

#### Terminal 5: 监控系统健康

```bash
cd /home/ilex/Dev/VIST

# 实时监控频率
python3 scripts/monitor_system_health.py
```

#### 测试步骤

1. 启动所有节点（Terminal 1-3）
2. 检查monitor显示的频率是否正常（80Hz）
3. 确认只有1个发布者在每个话题上
4. 开始数据采集（Terminal 4）
5. 缓慢移动右臂外骨骼，执行以下动作：
   - 前后移动（5秒）
   - 左右移动（5秒）
   - 上下移动（5秒）
   - 旋转运动（5秒）
   - 组合运动（10秒）
6. 停止数据采集
7. 停止所有节点（Ctrl+C）

### 实验1: EMA滤波（alpha=0.3）

#### Terminal 2: 启动EMA滤波节点

```bash
cd /home/ilex/Dev/VIST

# EMA滤波 alpha=0.3
python3 src/nodes/unified_filter_node.py --ros-args \
  -p filter_type:=ema \
  -p ema_alpha:=0.3 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true \
  -p performance_topic:=/filter_performance
```

#### Terminal 4: 数据采集

```bash
cd /home/ilex/Dev/VIST/data/exp_right_arm_only_$(date +%Y%m%d)

# 记录数据
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /robot1/right_arm/joint_follow \
  /robot1/right_arm/joint_states \
  /filter_performance \
  -o exp1_ema_alpha03 \
  --duration 30
```

重复相同的测试动作。

### 实验2: EMA滤波（alpha=0.5）

```bash
# Terminal 2
python3 src/nodes/unified_filter_node.py --ros-args \
  -p filter_type:=ema \
  -p ema_alpha:=0.5 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true

# Terminal 4
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /robot1/right_arm/joint_follow \
  /robot1/right_arm/joint_states \
  /filter_performance \
  -o exp2_ema_alpha05 \
  --duration 30
```

### 实验3: One-Euro滤波（标准参数）

```bash
# Terminal 2
python3 src/nodes/unified_filter_node.py --ros-args \
  -p filter_type:=one_euro \
  -p one_euro_min_cutoff:=1.0 \
  -p one_euro_beta:=0.007 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true

# Terminal 4
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /robot1/right_arm/joint_follow \
  /robot1/right_arm/joint_states \
  /filter_performance \
  -o exp3_oneeuro_standard \
  --duration 30
```

### 实验4: One-Euro滤波（高响应）

```bash
# Terminal 2
python3 src/nodes/unified_filter_node.py --ros-args \
  -p filter_type:=one_euro \
  -p one_euro_min_cutoff:=2.0 \
  -p one_euro_beta:=0.01 \
  -p input_topic:=/right_arm_joint_control \
  -p output_topic:=/filtered_right_joint_control \
  -p enable_performance_monitoring:=true

# Terminal 4
ros2 bag record \
  /right_arm_joint_control \
  /filtered_right_joint_control \
  /robot1/right_arm/joint_follow \
  /robot1/right_arm/joint_states \
  /filter_performance \
  -o exp4_oneeuro_highresp \
  --duration 30
```

## 数据分析

### 分析脚本

创建分析脚本 `scripts/analyze_filter_ablation.py`:

```python
#!/usr/bin/env python3
"""
滤波器消融实验数据分析
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState

def analyze_bag(bag_path):
    """分析rosbag数据"""
    # 读取数据
    # 计算指标:
    # 1. Jerk (加加速度)
    # 2. RMSE (跟踪误差)
    # 3. 频率稳定性
    # 4. 延迟
    pass

def compare_filters(exp_dirs):
    """对比不同滤波器的性能"""
    # 生成对比图表
    # 生成性能表格
    pass

if __name__ == "__main__":
    exp_dir = Path("data/exp_right_arm_only_20260225")

    experiments = [
        "exp0_no_filter",
        "exp1_ema_alpha03",
        "exp2_ema_alpha05",
        "exp3_oneeuro_standard",
        "exp4_oneeuro_highresp"
    ]

    for exp in experiments:
        print(f"\n分析 {exp}...")
        analyze_bag(exp_dir / exp)

    print("\n生成对比报告...")
    compare_filters([exp_dir / exp for exp in experiments])
```

### 运行分析

```bash
cd /home/ilex/Dev/VIST

# 分析所有实验数据
python3 scripts/analyze_filter_ablation.py

# 生成报告
# 输出: data/exp_right_arm_only_20260225/analysis_report.pdf
```

## 故障排查

### 问题1: 频率异常

```bash
# 检查发布者数量
ros2 topic info /filtered_right_joint_control

# 应该只有1个发布者！
# 如果有多个，说明有节点冲突
```

### 问题2: 机械臂不动

```bash
# 检查话题连接
ros2 topic echo /robot1/right_arm/joint_follow --once

# 检查teleop_bridge是否收到数据
ros2 topic hz /filtered_right_joint_control
```

### 问题3: 运动异常抖动

1. 立即按下急停
2. 检查是否有多个滤波节点在运行
3. 检查滤波器参数是否合理

## 实验记录表

| 实验 | 日期 | 时间 | 滤波器 | 参数 | 数据文件 | 备注 |
|-----|------|------|--------|------|---------|------|
| Exp0 | | | none | - | exp0_no_filter | 基线 |
| Exp1 | | | ema | α=0.3 | exp1_ema_alpha03 | |
| Exp2 | | | ema | α=0.5 | exp2_ema_alpha05 | |
| Exp3 | | | one_euro | 标准 | exp3_oneeuro_standard | |
| Exp4 | | | one_euro | 高响应 | exp4_oneeuro_highresp | |

## 预期结果

### 无滤波（Exp0）
- 优点: 响应快，无延迟
- 缺点: 噪声大，Jerk高

### EMA滤波（Exp1-2）
- 优点: 计算简单，平滑效果好
- 缺点: 固定延迟，快速运动响应慢

### One-Euro滤波（Exp3-4）
- 优点: 自适应，快速运动响应好
- 缺点: 计算稍复杂

## 安全检查清单

测试前:
- [ ] 急停按钮在手边
- [ ] 工作空间清空
- [ ] 机械臂状态正常
- [ ] 外骨骼校准完成
- [ ] 所有节点配置正确

测试中:
- [ ] 监控频率正常（80Hz）
- [ ] 只有1个发布者
- [ ] 运动平滑无异常
- [ ] 电机温度正常

测试后:
- [ ] 数据已保存
- [ ] 所有节点已停止
- [ ] 机械臂回到安全位置
- [ ] 记录实验日志

---

更新日期: 2026-02-25
作者: VIST Team