# LinkerHand 重定向问题解决方案

## 问题描述

原始错误：
```
ValueError: Optimizer has 14 joints but non_target_qpos [] is given
```

**根本原因**：dex-retargeting 优化器需要固定关节（fixed joints）的位置信息，但调用时没有提供。

## 解决方案

### 1. 配置文件（hand_retargeting_config.yaml）

保持 **10个主动关节** 的配置（不需要添加被动关节）：

```yaml
target_joint_names:
  - "thumb_cmc_pitch"    # [Active] 拇指根部俯仰
  - "thumb_cmc_yaw"      # [Active] 拇指根部偏航
  - "thumb_cmc_roll"     # [Active] 拇指根部滚转
  - "index_mcp_pitch"    # [Active] 食指MCP弯曲
  - "index_mcp_roll"     # [Active] 食指MCP侧摆
  - "middle_mcp_pitch"   # [Active] 中指MCP弯曲
  - "ring_mcp_pitch"     # [Active] 无名指MCP弯曲
  - "ring_mcp_roll"      # [Active] 无名指MCP侧摆
  - "pinky_mcp_pitch"    # [Active] 小指MCP弯曲
  - "pinky_mcp_roll"     # [Active] 小指MCP侧摆
```

### 2. LinkerHandRetargeter 类

创建了新的 `LinkerHandRetargeter` 类（`src/core/linker_hand_retargeter.py`），实现以下功能：

#### 核心特性：

1. **自动处理 Mimic 关节**
   - dex-retargeting 自动从 URDF 检测 mimic 关节（PIP/DIP）
   - 不需要手动注入 MimicJointKinematicAdaptor

2. **提供固定关节位置**
   - 优化器需要14个固定关节（arm joints）的位置
   - 初始化时创建 `self.fixed_qpos = np.zeros(14)`
   - 调用 retarget 时传入：`retarget(vectors, fixed_qpos=self.fixed_qpos)`

3. **索引映射**
   - 优化器输出的关节顺序与 SDK 要求的顺序不同
   - 建立索引映射：`[0, 1, 3, 5, 6, 8, 4, 7, 9, 2]`
   - 自动重排序输出以匹配 SDK 顺序

#### 工作流程：

```
MediaPipe 关键点 (21, 3)
    ↓
坐标系对齐 + 指尖向量提取
    ↓
Dex-Retargeting 优化（提供 fixed_qpos）
    ↓
优化器输出 (10,) - 优化器顺序
    ↓
索引映射重排序
    ↓
SDK 顺序的关节角度 (10,)
```

### 3. 关键代码片段

```python
# 初始化时准备固定关节位置
self.fixed_qpos = np.zeros(len(self.retargeting.optimizer.fixed_joint_names))

# 处理时传入固定关节位置
qpos = self.retargeting.retarget(vectors, fixed_qpos=self.fixed_qpos)

# 使用索引映射重排序
active_qpos = qpos[self.active_joint_indices]
```

## 技术细节

### 优化器的关节结构

- **Robot 总关节数**：34个（包括 arm + hand）
- **Target 关节数**：10个（手部主动关节）
- **Fixed 关节数**：14个（arm 关节）
- **Mimic 关节数**：10个（手部被动关节，自动处理）

### 为什么需要 fixed_qpos？

dex-retargeting 的优化器需要计算从 hand_base_link 到指尖的完整运动学链。这个链条包括：
1. Arm 关节（固定，不优化）
2. Hand 主动关节（优化目标）
3. Hand mimic 关节（由 mimic 规则自动计算）

优化器在计算 FK 时需要知道所有关节的位置，因此必须提供 fixed_qpos。

## 测试结果

✅ 初始化成功
✅ 处理关键点成功
✅ 输出形状正确：(10,)
✅ 无 NaN 或 Inf 值
✅ 索引映射正确

## 使用方法

```python
from src.core.linker_hand_retargeter import LinkerHandRetargeter

# 初始化
retargeter = LinkerHandRetargeter(
    config_path="config/hand_retargeting_config.yaml",
    project_root="/path/to/VIST"
)

# 处理 MediaPipe 关键点
keypoints = np.array(...)  # shape: (21, 3)
joint_angles = retargeter.process(keypoints)  # shape: (10,)

# joint_angles 已按 SDK 顺序排列，可直接发送给 LinkerHand
```

## 文件清单

1. **配置文件**：`config/hand_retargeting_config.yaml`
   - 保持10个主动关节配置

2. **核心类**：`src/core/linker_hand_retargeter.py`
   - 新的 LinkerHandRetargeter 类
   - 处理固定关节位置和索引映射

3. **驱动更新**：`src/robot/hand_driver.py`
   - 更新导入：使用 LinkerHandRetargeter
   - 更新初始化和处理逻辑

4. **测试脚本**：`scripts/test_retargeter.py`
   - 验证 LinkerHandRetargeter 功能

## 总结

问题的关键在于理解 dex-retargeting 的内部机制：
- ❌ 不需要在 target_joint_names 中添加 mimic 关节
- ✅ 需要提供 fixed_qpos 给优化器
- ✅ Mimic 关节由 URDF 自动处理
- ✅ 需要索引映射来匹配 SDK 顺序

这个解决方案保持了代码的简洁性，同时正确处理了所有关节类型。
