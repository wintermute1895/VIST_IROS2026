# VIST 架构重构方案

## 当前问题

### 1. 职责不清晰
- `vision_node_depth.py` 中的 `mediapipe_to_robot_coords()` 已经在做坐标转换
- `motion_mapper.py` 中又有 `R_vision_to_robot` 矩阵做二次转换
- 导致双重转换，容易出错且难以调试

### 2. 参数硬编码
- 肩部位置、臂长等参数分散在多个文件中
- 坐标转换矩阵在两个地方定义（`coordinate_transform.py` 和 `motion_mapper.py`）
- 缺乏统一的配置管理

### 3. 冗余代码
- `coordinate_transform.py` 和 `motion_mapper.py` 中有重复的转换逻辑
- 多个测试脚本功能重叠

## 重构目标

### 核心原则：单一职责
1. **视觉节点**：只负责数据采集和预处理
2. **映射节点**：只负责坐标转换和运动映射
3. **控制节点**：只负责 IK 求解和电机控制

## 新架构设计

### 数据流
```
MediaPipe 原始数据
    ↓
[视觉节点] vision_node_depth.py
    - 动态归零（肩部为原点）
    - 深度融合（RealSense + MediaPipe）
    - 输出：肩膀坐标系（Shoulder Frame）
    ↓
UDP 传输（原始数据）
    ↓
[映射节点] motion_mapper.py
    - 坐标系转换（Shoulder Frame → Robot Base Frame）
    - 位置映射（人体臂长 → 机器人臂长）
    - 姿态计算（三向量法）
    - 输出：机器人基座坐标系（body_base_link）
    ↓
[控制节点] vist_teleoperation.py
    - 微分 IK 求解
    - 安全监控
    - 电机控制
    - 输出：关节角度指令
```

### 坐标系定义

#### 1. MediaPipe 坐标系（原始）
- X: 视频中向左（镜像后对应物理右）
- Y: 向下
- Z: 向外（背离相机）

#### 2. 肩膀坐标系（Shoulder Frame）- 视觉节点输出
- X: 向上（垂直）
- Y: 向右（水平）
- Z: 向前（靠近相机）
- 原点：肩部（动态归零）

#### 3. 机器人基座坐标系（Robot Base Frame）- 映射节点输出
- X: 向前
- Y: 向左
- Z: 向上
- 原点：body_base_link

### 转换矩阵（同向放置）
```python
# Shoulder Frame → Robot Base Frame
R = [
    [0,  0,  1],  # X_robot = Z_shoulder (前 = 前)
    [0, -1,  0],  # Y_robot = -Y_shoulder (左 = -右)
    [1,  0,  0]   # Z_robot = X_shoulder (上 = 上)
]
```

## 重构步骤

### Phase 1: 配置化（优先）
1. 创建 `config/system_config.yaml`
   - 机器人参数（肩部位置、臂长）
   - 坐标转换矩阵
   - 控制参数（增益、速度限制）
   - 网络参数（UDP 端口）

2. 创建 `src/config/config_loader.py`
   - 统一的配置加载器
   - 参数验证

### Phase 2: 视觉节点简化
1. 修改 `vision_node_depth.py`
   - 移除 `mediapipe_to_robot_coords()` 中的坐标转换
   - 只保留动态归零和深度融合
   - 输出格式：肩膀坐标系（X=上, Y=右, Z=前）

### Phase 3: 映射节点职责明确
1. 修改 `motion_mapper.py`
   - 统一使用一个转换矩阵（从配置文件读取）
   - 移除 `R_cam_to_base`（已废弃）
   - 添加清晰的注释说明输入输出

### Phase 4: 清理冗余
1. 删除或合并重复的测试脚本
2. 移除 `coordinate_transform.py`（功能合并到 `motion_mapper.py`）
3. 统一调试输出格式

## 配置文件示例

```yaml
# config/system_config.yaml

robot:
  shoulder_position: [0.0, -0.096, 1.217]  # [x, y, z] in meters
  arm_lengths:
    upper: 0.2908  # meters
    forearm: 0.2366  # meters

coordinate_transform:
  # Shoulder Frame → Robot Base Frame (同向放置)
  rotation_matrix: [
    [0,  0,  1],
    [0, -1,  0],
    [1,  0,  0]
  ]
  description: "User and robot face same direction"

control:
  ik_gain: 0.9
  max_joint_velocity: 0.8  # rad/s
  max_joint_acceleration: 2.0  # rad/s^2
  frequency: 50  # Hz

network:
  udp_ip: "127.0.0.1"
  udp_port: 6001

vision:
  scale: 1.0
  width: 640
  height: 480
  fps: 30
```

## 实施优先级

1. **高优先级**：配置化（Phase 1）
   - 立即见效，减少硬编码
   - 便于调试和参数调整

2. **中优先级**：职责明确（Phase 2-3）
   - 修复架构问题
   - 提高可维护性

3. **低优先级**：清理冗余（Phase 4）
   - 代码整洁
   - 不影响功能

## 验证计划

每个 Phase 完成后：
1. 运行 `test_coordinate_display.py` 验证视觉输出
2. 运行 `vist_teleoperation.py` 验证完整流程
3. 检查坐标转换是否正确（向前伸手 → X 增大）
