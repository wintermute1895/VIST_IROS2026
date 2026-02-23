# 外骨骼+手套集成分支 - 工作计划

## 分支信息
- **分支名称**: `feature/exo-hand-integration`
- **基于**: `feature/vision-perception` (e3d3c9d)
- **创建时间**: 2026-02-23
- **目标**: 集成外骨骼臂和数据手套的完整遥操作系统

## 当前状态

### ✅ 已完成
1. **外骨骼臂控制**
   - 基线遥操作（无滤波）- `exo_baseline_1_raw.py`
   - 低通滤波版本 - `exo_ours_filtered.py`
   - ROS2桥接 - `exo_ros2_bridge.py`
   - 滤波中间件 - `filter_middleware_node.py`

2. **手套数据采集**
   - 手套节点已运行，发布到 `/cb_left_hand_control_cmd`
   - 手套桥接节点 - `glove_to_robot_bridge.py`（已创建但可能不需要）

3. **手部SDK配置**
   - 原生SDK已配置 (`~/Downloads/linkerhand-ros2-sdk-main/`)
   - 配置文件已修改（L10左手，CAN通信）
   - 启动脚本已创建 - `start_hand_sdk.sh`

4. **SDK集成**
   - arm_teleop SDK（lbot外骨骼驱动）
   - linkerhand-ros-teleop SDK（手套驱动）

### 🔲 待完成

#### 1. VIST完整接入外骨骼控制流
**目标**: 将完整的VIST算法（意图因子α + 自适应卡尔曼滤波）应用到外骨骼控制

**实现方案**:
```python
# 新文件: scripts/exo_vist_full.py

数据流:
外骨骼编码器 → 关节角度 + 速度
                ↓
        简化意图检测器 → α因子（基于速度）
                ↓
        VISTKalmanFilter → 自适应滤波
                ↓
            机械臂控制
```

**关键点**:
- 使用 `VISTKalmanFilter` 替代简单的 `LowPassFilter`
- 实现简化的意图检测（仅基于速度，不需要视觉）
- 保持与现有代码的兼容性

#### 2. 手套+手部SDK完整测试
**目标**: 验证手套数据能正确驱动L10灵巧手

**测试步骤**:
1. 连接L10手的CAN线到电脑
2. 启动手套节点（已有）
3. 启动手部SDK: `./scripts/start_hand_sdk.sh`
4. 验证数据流: 手套 → `/cb_left_hand_control_cmd` → 手部SDK → CAN → L10手

**注意事项**:
- 手套和手部SDK使用相同的话题，无需桥接
- 确认CAN接口正常（can0）
- 检查关节映射是否正确

#### 3. 统一启动系统
**目标**: 创建一键启动脚本，同时启动臂和手的遥操作

**文件**: `scripts/start_full_teleop.sh`

```bash
#!/bin/bash
# 启动完整的外骨骼+手套遥操作系统

# 1. 启动CAN接口（手部）
echo "启动CAN接口..."
./scripts/setup_can.sh

# 2. 启动手套节点
echo "启动手套节点..."
# 在新终端启动

# 3. 启动手部SDK
echo "启动手部SDK..."
# 在新终端启动

# 4. 启动外骨骼臂遥操作（带VIST）
echo "启动外骨骼臂遥操作..."
python3 scripts/exo_vist_full.py
```

#### 4. 数据记录和分析
**目标**: 完善数据记录，用于论文实验

**需要记录的数据**:
- 原始外骨骼关节角度
- VIST滤波后的关节角度
- 机械臂实际关节角度
- 意图因子α的变化
- 手套关节数据
- 灵巧手实际关节数据

**分析工具**:
- `analyze_exo_data.py` - 已有，需要扩展
- 添加频域分析（PSD）
- 添加轨迹一致性分析（DTW）
- 添加平滑度分析（SPARC）

## 下一步行动计划

### 优先级1: VIST完整接入（本周）
1. 创建 `scripts/exo_vist_full.py`
2. 实现简化的意图检测器
3. 集成 `VISTKalmanFilter`
4. 测试和调试

### 优先级2: 手部系统测试（本周）
1. 连接硬件
2. 测试手套→手部SDK数据流
3. 验证关节映射
4. 调整参数

### 优先级3: 数据采集（下周）
1. 完善数据记录
2. 设计实验任务
3. 采集对比数据（Baseline vs VIST）
4. 分析数据质量

### 优先级4: 论文实验（下周）
1. USB插入任务
2. 积木堆叠任务
3. 精密装配任务
4. 数据分析和可视化

## 技术债务

### 需要清理
1. SDK的build目录不应该提交到git（添加到.gitignore）
2. 日志文件不应该提交（已有中文文件名的PDF）
3. 重复的代码需要重构

### 需要优化
1. 配置文件管理（统一配置格式）
2. 错误处理和日志记录
3. 代码文档和注释

## 参考资料

### 相关文件
- VIST核心: `src/core/vist_kalman_filter.py`
- 意图检测: `src/core/intent_detector.py`
- 控制器: `src/control/vist_controller.py`
- 代码结构: `docs/CODE_STRUCTURE.md`

### 配置文件
- 手部SDK: `~/Downloads/linkerhand-ros2-sdk-main/linker_hand_ros2_sdk/launch/linker_hand.launch.py`
- 手套配置: `src/robot/sdk/linkerhand-ros-teleop-main/.../base_config.yml`
- 外骨骼配置: `src/robot/sdk/arm_teleop/src/lbot_teleop/config/teleop_config.yaml`

## 联系和协作

如果遇到问题，检查：
1. 硬件连接（CAN、USB、网络）
2. ROS2环境（source setup.bash）
3. Python环境（conda环境）
4. 权限问题（sudo、chmod）

---

**最后更新**: 2026-02-23
**维护者**: ilex
