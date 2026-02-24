# VIST 鲁棒数据采集系统设计

## 📋 设计目标

基于LinkerHand数据采集系统的优秀实践，为VIST系统设计一个鲁棒的数据采集架构，保留rosbag2的优势，同时补充关键功能。

### 核心原则

1. **保留rosbag2优势** - 标准ROS2工具链，易于调试和回放
2. **增强Episode管理** - 自动编号、元数据、质量评分
3. **严格时间同步** - 验证多传感器时间对齐
4. **训练数据就绪** - 提供rosbag到训练格式的转换
5. **自动化流程** - 减少手动操作，提高效率

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                  VIST 鲁棒数据采集系统                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐     │
│  │         Episode管理服务 (新增)                         │     │
│  │    scripts/episode_manager.py                         │     │
│  │    - 任务管理 (create_task, stop_task)                │     │
│  │    - Episode自动编号                                   │     │
│  │    - 元数据生成                                        │     │
│  │    - 质量评分                                          │     │
│  │    - rosbag录制协调                                    │     │
│  └──────────────┬────────────────────────────────────────┘     │
│                 │                                               │
│  ┌──────────────┴───────────────────────────────────┐          │
│  │                                                   │          │
│  ▼                     ▼                  ▼          ▼          │
│ ┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────┐   │
│ │ rosbag2    │  │ 相机管理     │  │ 时间同步  │  │质量监控 │   │
│ │ 录制       │  │ (已实现)     │  │ 验证器    │  │ 模块    │   │
│ │            │  │ RobustCamera │  │ (新增)    │  │ (新增)  │   │
│ │            │  │ Manager      │  │           │  │         │   │
│ └────────────┘  └─────────────┘  └──────────┘  └─────────┘   │
│       │                 │                │            │        │
│  ┌────┴─────────────────┴────────────────┴────────────┘        │
│  │                                                              │
│  ▼                                                              │
│ ┌──────────────────────────────────────────────────────┐       │
│ │           数据后处理模块 (新增)                       │       │
│ │  - 时间同步验证 (validate_time_sync.py)              │       │
│ │  - 元数据生成 (generate_episode_metadata.py)         │       │
│ │  - 质量评分 (quality_scorer.py)                      │       │
│ │  - 格式转换 (rosbag_to_hdf5.py)                      │       │
│ └──────────────────────────────────────────────────────┘       │
│                          │                                     │
│                          ▼                                     │
│ ┌──────────────────────────────────────────────────────┐       │
│ │              数据存储 (增强)                          │       │
│ │  task_name/session_timestamp/                        │       │
│ │  ├── episode_000000/                                 │       │
│ │  │   ├── rosbag/ (rosbag2数据)                      │       │
│ │  │   ├── metadata.json (Episode元数据)              │       │
│ │  │   ├── sync_validation_report.json (同步报告)     │       │
│ │  │   ├── quality_report.json (质量评分)             │       │
│ │  │   └── training_data/ (可选，转换后的训练数据)    │       │
│ │  ├── episode_000001/                                 │       │
│ │  └── session_manifest.json (会话清单)               │       │
│ └──────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 核心组件设计

### 1. Episode管理服务 (新增)

**文件**: `scripts/episode_manager.py`

**功能**:
- 统一管理数据采集会话
- 自动Episode编号
- 协调rosbag录制
- 生成元数据和质量报告

**接口设计**:

```python
class EpisodeManager:
    \"\"\"Episode管理器 - 统一数据采集接口\"\"\"

    def __init__(self, base_dir: str = "data/collection"):
        \"\"\"初始化管理器\"\"\"
        pass

    def create_task(self, task_name: str, config: Dict) -> str:
        \"\"\"
        创建新任务

        Args:
            task_name: 任务名称 (如 "pick_and_place")
            config: 任务配置 (相机、话题、参数等)

        Returns:
            session_id: 会话ID
        \"\"\"
        pass

    def start_episode(self, session_id: str, max_duration: int = 60) -> str:
        \"\"\"
        开始新Episode

        Args:
            session_id: 会话ID
            max_duration: 最大时长（秒）

        Returns:
            episode_id: Episode ID
        \"\"\"
        pass

    def stop_episode(self, episode_id: str, quality_score: str = None):
        \"\"\"
        停止Episode并生成报告

        Args:
            episode_id: Episode ID
            quality_score: 手动质量评分 (A/B/C/D/F)
        \"\"\"
        pass

    def validate_episode(self, episode_id: str) -> Dict:
        \"\"\"
        验证Episode数据质量

        Returns:
            验证报告 (时间同步、数据完整性等)
        \"\"\"
        pass

    def convert_to_training_format(self, episode_id: str, format: str = "hdf5"):
        \"\"\"
        转换Episode到训练格式

        Args:
            episode_id: Episode ID
            format: 目标格式 ("hdf5", "zarr", "numpy")
        \"\"\"
        pass
```

**使用示例**:

```python
# 创建任务
manager = EpisodeManager()
session_id = manager.create_task(
    task_name="vision_control_test",
    config={
        "cameras": ["overhead", "wrist"],
        "topics": [
            "/camera/color/image_raw",
            "/robot1/right_arm/joint_states",
            "/vision_right_joint_control"
        ],
        "control_frequency": 25,
        "camera_fps": 30
    }
)

# 录制多个Episodes
for i in range(10):
    print(f"录制Episode {i+1}/10")

    # 开始录制
    episode_id = manager.start_episode(session_id, max_duration=30)

    # 等待用户操作
    input("按Enter停止录制...")

    # 停止并验证
    manager.stop_episode(episode_id)
    report = manager.validate_episode(episode_id)

    print(f"质量评级: {report['quality_grade']}")
    print(f"同步质量: {report['sync_quality']}")

    # 如果质量好，转换为训练格式
    if report['quality_grade'] in ['A', 'B']:
        manager.convert_to_training_format(episode_id, format="hdf5")
```

---

### 2. 时间同步验证器 (已实现)

**文件**: `scripts/validate_time_sync.py`

**功能**:
- 验证rosbag中多传感器时间同步质量
- 计算时间差统计
- 生成同步质量报告

**关键指标**:
- 优秀: <10ms
- 良好: <33ms (一帧)
- 可接受: <100ms
- 较差: <200ms

**使用**:
```bash
# 验证单个rosbag
python scripts/validate_time_sync.py data/recordings/rec_20260224_122434/rosbag

# 指定参考话题
python scripts/validate_time_sync.py data/recordings/rec_20260224_122434/rosbag \
    /camera/color/image_raw \
    /robot1/right_arm/joint_states
```

---

### 3. Episode元数据生成器 (已实现)

**文件**: `scripts/generate_episode_metadata.py`

**功能**:
- 为rosbag生成标准化元数据
- 提取录制信息（时长、消息数、话题）
- 支持批量处理

**元数据格式**:
```json
{
  "episode_id": "episode_000000",
  "format": "rosbag2",
  "timestamp": "2026-02-24T15:30:22.123456",
  "task_name": "vision_control_test",
  "duration_sec": 30.5,
  "total_messages": 1523,
  "topics": {
    "/camera/color/image_raw": {
      "type": "sensor_msgs/msg/Image",
      "count": 915,
      "frequency": 30.0
    },
    "/robot1/right_arm/joint_states": {
      "type": "sensor_msgs/msg/JointState",
      "count": 608,
      "frequency": 25.0
    }
  },
  "quality_score": "A"
}
```

**使用**:
```bash
# 单个rosbag
python scripts/generate_episode_metadata.py \
    data/recordings/rec_20260224_122434/rosbag \
    --task vision_control_test

# 批量处理
python scripts/generate_episode_metadata.py \
    data/recordings \
    --batch \
    --task vision_control_test
```

---

### 4. 数据质量评分器 (待实现)

**文件**: `scripts/quality_scorer.py`

**功能**:
- 综合评估Episode数据质量
- 计算多维度质量指标
- 生成A/B/C/D/F评级

**评分维度**:

| 维度 | 权重 | 指标 |
|------|------|------|
| 时间同步 | 40% | 中位数时间差、同步成功率 |
| 数据完整性 | 30% | 消息丢失率、话题覆盖率 |
| 频率稳定性 | 20% | 频率标准差、抖动 |
| 异常检测 | 10% | 异常值数量、数据跳变 |

**评级标准**:
- A (90-100分): 优秀，直接用于训练
- B (80-89分): 良好，可用于训练
- C (70-79分): 可接受，需要审查
- D (60-69分): 较差，建议重新录制
- F (<60分): 失败，不可用

---

### 5. rosbag到训练格式转换器 (待实现)

**文件**: `scripts/rosbag_to_hdf5.py`

**功能**:
- 将rosbag转换为训练友好的格式
- 支持HDF5、Zarr、NumPy等格式
- 自动对齐时间戳
- 提取图像、关节数据、动作

**转换流程**:

```
rosbag2 数据
  ↓
1. 读取所有话题
  ↓
2. 提取时间戳，找到对齐的帧
  ↓
3. 解码图像数据
  ↓
4. 提取关节位置、速度、力矩
  ↓
5. 构建observation和action
  ↓
6. 写入HDF5文件
  ↓
训练数据 (HDF5)
```

**HDF5格式**:
```python
episode_000000.hdf5
├── /observations
│   ├── qpos              # (N, qpos_dim) float32
│   ├── qvel              # (N, qvel_dim) float32
│   ├── images
│   │   ├── overhead      # (N, H, W, 3) uint8
│   │   └── wrist         # (N, H, W, 3) uint8
│   └── timestamp         # (N,) float64
├── /actions              # (N, action_dim) float32
└── /metadata
    ├── task_name         # str
    ├── episode_id        # str
    ├── duration_sec      # float
    └── quality_score     # str
```

**使用**:
```bash
# 转换单个Episode
python scripts/rosbag_to_hdf5.py \
    data/collection/task_name/session_xxx/episode_000000/rosbag \
    --output data/training/episode_000000.hdf5 \
    --camera-topics /camera/color/image_raw \
    --joint-topic /robot1/right_arm/joint_states \
    --action-topic /vision_right_joint_control

# 批量转换
python scripts/rosbag_to_hdf5.py \
    data/collection/task_name/session_xxx \
    --batch \
    --output data/training
```

---

## 📂 数据存储结构

### 目录层级

```
data/
├── collection/                          # 原始采集数据
│   └── task_name/                       # 任务名称
│       ├── session_20260224_153024/     # 采集会话
│       │   ├── episode_000000/          # Episode目录
│       │   │   ├── rosbag/              # rosbag2数据
│       │   │   │   ├── *.db3
│       │   │   │   └── metadata.yaml
│       │   │   ├── metadata.json        # Episode元数据
│       │   │   ├── sync_validation_report.json  # 同步验证报告
│       │   │   ├── quality_report.json  # 质量评分报告
│       │   │   └── README.md            # 人类可读的报告
│       │   ├── episode_000001/
│       │   ├── ...
│       │   └── session_manifest.json    # 会话清单
│       └── all_episodes/                # 符号链接目录（训练用）
│           ├── episode_000000 -> ../session_xxx/episode_000000
│           └── episode_000001 -> ../session_xxx/episode_000001
│
└── training/                            # 训练数据
    └── task_name/
        ├── episode_000000.hdf5
        ├── episode_000001.hdf5
        └── dataset_manifest.json
```

### session_manifest.json

```json
{
  "session_id": "session_20260224_153024",
  "task_name": "vision_control_test",
  "created_at": "2026-02-24T15:30:24.123456",
  "config": {
    "cameras": ["overhead", "wrist"],
    "topics": [...],
    "control_frequency": 25,
    "camera_fps": 30
  },
  "episodes": [
    {
      "episode_id": "episode_000000",
      "duration_sec": 30.5,
      "quality_score": "A",
      "sync_quality": "excellent",
      "created_at": "2026-02-24T15:31:00.000000"
    },
    {
      "episode_id": "episode_000001",
      "duration_sec": 28.3,
      "quality_score": "B",
      "sync_quality": "good",
      "created_at": "2026-02-24T15:32:15.000000"
    }
  ],
  "statistics": {
    "total_episodes": 10,
    "total_duration_sec": 305.2,
    "quality_distribution": {
      "A": 6,
      "B": 3,
      "C": 1,
      "D": 0,
      "F": 0
    }
  }
}
```

---

## 🔄 完整工作流程

### 1. 任务创建阶段

```bash
# 创建新任务
python scripts/episode_manager.py create-task \
    --name vision_control_test \
    --config config/vision_control_config.yaml
```

### 2. 数据采集阶段

```bash
# 启动Episode录制
python scripts/episode_manager.py start-episode \
    --session session_20260224_153024 \
    --duration 30

# 或使用交互式模式
python scripts/episode_manager.py interactive \
    --session session_20260224_153024
```

### 3. 数据验证阶段

```bash
# 自动验证（Episode停止时自动执行）
# 或手动验证
python scripts/episode_manager.py validate \
    --episode episode_000000
```

### 4. 数据转换阶段

```bash
# 转换高质量Episode到训练格式
python scripts/episode_manager.py convert \
    --session session_20260224_153024 \
    --quality-threshold B \
    --format hdf5
```

### 5. 数据管理阶段

```bash
# 查看会话统计
python scripts/episode_manager.py stats \
    --session session_20260224_153024

# 删除低质量Episode
python scripts/episode_manager.py cleanup \
    --session session_20260224_153024 \
    --quality-threshold C

# 导出训练数据清单
python scripts/episode_manager.py export-manifest \
    --task vision_control_test \
    --output data/training/task_name/dataset_manifest.json
```

---

## 🎯 实施计划

### Phase 1: 核心功能 (2-3天)

**优先级P0**:

1. ✅ 时间同步验证器 (`validate_time_sync.py`) - 已完成
2. ✅ Episode元数据生成器 (`generate_episode_metadata.py`) - 已完成
3. ⏳ Episode管理器核心 (`episode_manager.py`) - 待实现
   - 任务创建
   - Episode录制控制
   - 元数据管理

**预计时间**: 1天

### Phase 2: 质量保证 (1-2天)

**优先级P1**:

4. ⏳ 数据质量评分器 (`quality_scorer.py`) - 待实现
5. ⏳ 增强时间同步验证 - 待实现
   - 添加更多统计指标
   - 可视化时间差分布

**预计时间**: 1天

### Phase 3: 训练数据转换 (2-3天)

**优先级P1**:

6. ⏳ rosbag到HDF5转换器 (`rosbag_to_hdf5.py`) - 待实现
7. ⏳ 支持多种训练格式 (Zarr, NumPy) - 待实现
8. ⏳ 批量转换工具 - 待实现

**预计时间**: 2天

### Phase 4: 集成与测试 (1-2天)

**优先级P2**:

9. ⏳ 端到端测试 - 待实现
10. ⏳ 文档完善 - 待实现
11. ⏳ 示例和教程 - 待实现

**预计时间**: 1天

---

## 📊 与LinkerHand系统对比

| 功能 | LinkerHand | VIST (当前) | VIST (设计后) |
|------|-----------|------------|--------------|
| Episode管理 | ✅ 自动编号 | ❌ 手动 | ✅ 自动编号 |
| 时间同步验证 | ✅ 200ms容差 | ❌ 未验证 | ✅ 10ms精度 |
| 数据格式 | HDF5+视频 | rosbag2 | rosbag2+HDF5 |
| 质量评分 | ✅ A/B/C/D | ❌ 无 | ✅ A/B/C/D/F |
| 相机管理 | ⚠️ 基础 | ✅ 鲁棒 | ✅ 鲁棒 |
| 训练数据转换 | ✅ 直接可用 | ❌ 需手动 | ✅ 自动转换 |
| 调试友好性 | ⚠️ 中等 | ✅ 优秀 | ✅ 优秀 |

---

## 🎓 总结

### 设计优势

1. **保留rosbag2优势** - 标准工具链，易于调试
2. **补充关键功能** - Episode管理、时间同步、质量评分
3. **渐进式改进** - 不需要重写现有系统
4. **灵活性** - 支持多种训练数据格式
5. **自动化** - 减少手动操作，提高效率

### 关键改进点

1. **Episode管理** - 从手动管理到自动化
2. **时间同步** - 从未验证到严格验证
3. **数据质量** - 从无评分到多维度评分
4. **训练就绪** - 从需手动转换到自动转换

### 下一步行动

1. 实现Episode管理器核心功能
2. 测试时间同步验证器
3. 实现数据质量评分器
4. 实现rosbag到HDF5转换器
5. 端到端测试和文档完善

---

**需要我开始实现Episode管理器吗？**