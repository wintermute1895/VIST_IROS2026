# VIST 开发会话总结

## 会话日期
2026-02-06

## 完成的工作

### 1. 坐标系统调试和修复

#### 问题诊断
- **Z 坐标符号错误**: 向前伸手时 Z 坐标减小（应该增大）
- **坐标映射错误**: 视觉 Z 坐标被映射到机器人 Y 坐标（应该映射到 X）

#### 修复内容

**文件**: `src/nodes/vision_node_depth.py`
- **Line 163**: 修复深度符号
  ```python
  # 修改前: z_mp = real_depth
  # 修改后: z_mp = -real_depth
  ```
- **原因**: RealSense 相对深度为负时表示靠近相机，需要取反才能让 Z 增大

**文件**: `src/core/motion_mapper.py`
- **Line 56**: 修复旋转矩阵（同向放置）
  ```python
  # 修改前: [0, 0, -1]  # 面对面放置
  # 修改后: [0, 0,  1]  # 同向放置
  ```
- **原因**: 用户和机器人是同向放置，不是面对面

#### 验证结果
- ✅ 向前伸手 → Z 坐标增大
- ✅ 向前伸手 → 机器人 X 坐标增大（向前移动）
- ✅ 坐标映射正确

### 2. 架构重构 - Phase 1: 配置化

#### 目标
- 参数集中管理
- 职责清晰划分
- 提高可维护性

#### 创建的文件

1. **`config/system_config.yaml`**
   - 统一的系统配置文件
   - 包含：机器人参数、坐标转换、控制参数、网络参数、视觉参数、安全参数
   - 清晰的注释和分类

2. **`src/config/config_loader.py`**
   - 配置加载器类 `VISTConfig`
   - 单例模式，全局访问
   - 自动类型转换（numpy array）
   - 已测试通过 ✓

3. **`src/config/__init__.py`**
   - 模块初始化文件
   - 导出 `VISTConfig` 和 `get_config`

4. **`docs/ARCHITECTURE_REFACTOR.md`**
   - 完整的架构重构方案
   - 数据流图
   - 坐标系定义
   - 实施步骤

5. **`docs/REFACTOR_PHASE1_COMPLETE.md`**
   - Phase 1 完成报告
   - 详细的 Phase 2-4 实施指南
   - 代码示例

6. **`docs/REFACTOR_STATUS.md`**
   - 当前重构状态
   - 实施建议
   - 快速开始指南

#### 使用方法

```python
from src.config import get_config

config = get_config()

# 访问参数
shoulder_pos = config.robot_shoulder_position  # numpy array
rotation_matrix = config.rotation_matrix       # 3x3 numpy array
ik_gain = config.ik_gain                       # float
```

#### 配置文件结构

```yaml
robot:                  # 机器人参数
coordinate_transform:   # 坐标转换矩阵
control:                # 控制参数
network:                # UDP 通信
vision:                 # 相机参数
safety:                 # 安全参数
```

### 3. 架构设计

#### 数据流
```
MediaPipe 原始数据
    ↓
[视觉节点] vision_node_depth.py
    - 动态归零（肩部为原点）
    - 深度融合（RealSense + MediaPipe）
    - 输出：肩膀坐标系（X=上, Y=右, Z=前）
    ↓
UDP 传输
    ↓
[映射节点] motion_mapper.py
    - 坐标系转换（Shoulder Frame → Robot Base Frame）
    - 位置映射（人体臂长 → 机器人臂长）
    - 姿态计算（三向量法）
    - 输出：机器人基座坐标系（X=前, Y=左, Z=上）
    ↓
[控制节点] vist_teleoperation.py
    - 微分 IK 求解
    - 安全监控
    - 电机控制
    - 输出：关节角度指令
```

#### 坐标系定义

**肩膀坐标系（Shoulder Frame）** - 视觉节点输出
- X: 向上（垂直）
- Y: 向右（水平）
- Z: 向前（靠近相机）
- 原点：肩部（动态归零）

**机器人基座坐标系（Robot Base Frame）** - 映射节点输出
- X: 向前
- Y: 向左
- Z: 向上
- 原点：body_base_link

**转换矩阵（同向放置）**
```python
R = [
    [0,  0,  1],  # X_robot = Z_shoulder (前 = 前)
    [0, -1,  0],  # Y_robot = -Y_shoulder (左 = -右)
    [1,  0,  0]   # Z_robot = X_shoulder (上 = 上)
]
```

## 待完成的工作

### Phase 2: 视觉节点简化
- 移除坐标转换逻辑
- 只保留动态归零和深度融合
- 使用配置文件加载参数

### Phase 3: 映射节点职责明确
- 统一使用配置文件的转换矩阵
- 移除废弃代码（R_cam_to_base）
- 更新注释

### Phase 4: 控制节点配置化
- 使用配置文件加载所有参数
- 移除硬编码

## 技术要点

### 1. 深度融合
- 使用 RealSense 深度替换 MediaPipe 的 Z 坐标
- 计算相对深度：`wrist_depth - shoulder_depth`
- 取反以匹配坐标系定义：`z_mp = -real_depth`

### 2. 坐标转换
- 视觉节点：输出肩膀坐标系（不做旋转转换）
- 映射节点：负责坐标系转换（Shoulder → Robot Base）
- 单一职责原则

### 3. 配置管理
- 单例模式：全局唯一配置实例
- 自动类型转换：YAML → numpy array
- 向后兼容：保留旧的参数接口

## 测试验证

### 配置加载器测试
```bash
$ python3 src/config/config_loader.py
✅ 配置加载成功
```

### 坐标转换验证
- ✅ 向前伸手 → Z 坐标增大
- ✅ 向前伸手 → 机器人向前移动（X 增大）
- ✅ 向右移动 → 机器人向左移动（Y 增大）

## 文件清单

### 新增文件
- `config/system_config.yaml`
- `src/config/config_loader.py`
- `src/config/__init__.py`
- `docs/ARCHITECTURE_REFACTOR.md`
- `docs/REFACTOR_PHASE1_COMPLETE.md`
- `docs/REFACTOR_STATUS.md`

### 修改文件
- `src/nodes/vision_node_depth.py` (Line 163: 深度符号修复)
- `src/core/motion_mapper.py` (Line 56: 旋转矩阵修复)

## 下一步建议

1. **测试当前系统**
   - 运行 `scripts/test_coordinate_display.py`
   - 验证坐标显示是否正确
   - 测试完整的遥操作流程

2. **继续重构**（可选）
   - 实施 Phase 2-4
   - 逐步迁移到配置文件
   - 清理冗余代码

3. **性能优化**（可选）
   - 调整控制参数（IK 增益、速度限制）
   - 优化滤波算法
   - 提高响应速度

## 参考文档

- [架构重构方案](docs/ARCHITECTURE_REFACTOR.md)
- [Phase 1 完成报告](docs/REFACTOR_PHASE1_COMPLETE.md)
- [重构状态](docs/REFACTOR_STATUS.md)
- [配置文件](config/system_config.yaml)

## 备注

- 所有修改都保持向后兼容
- 配置文件已测试通过
- 坐标转换问题已修复
- 架构重构 Phase 1 已完成
