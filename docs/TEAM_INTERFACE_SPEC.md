# VIST团队接口规范

**版本**: v1.0
**日期**: 2026-02-11
**状态**: 🔒 **接口冻结** - 未经双方同意不得修改

---

## 分工概览

| 人员 | 职责 | 核心任务 |
|-----|------|---------|
| **人员A** | 核心算法 + 理论验证 | 状态估计、数学建模、离线仿真 |
| **人员B** | 系统集成 + 实验验证 | 视觉感知、机器人控制、真机实验 |

---

## 核心接口定义

### 1. VISTKalmanFilter（A提供，B使用）

**文件位置**: `src/core/vist_kalman_filter.py`

```python
class VISTKalmanFilter:
    """
    VIST自适应卡尔曼滤波器

    职责：
    - 融合人手观测和视觉引导观测
    - 动态调整观测噪声协方差
    - 维护置信度状态变量
    """

    def __init__(self, config: dict):
        """
        初始化滤波器

        参数:
            config: 配置字典，包含：
                - dt: 采样时间（默认0.002s，500Hz）
                - R_human: 人手观测噪声（默认0.005）
                - R_virtual_base: 虚拟引导基础噪声（默认0.01）
                - Q_base: 过程噪声基础值（默认0.001）
                - lambda_decay: 置信度衰减率（默认5.0）
                - lambda_recover: 置信度恢复率（默认0.5）
        """
        pass

    def update(self,
               z_human: np.ndarray,      # shape: (3,) [x, y, z]
               z_virtual: np.ndarray,    # shape: (3,) [x, y, z]
               alpha: float              # range: [0, 1]
              ) -> tuple[np.ndarray, float, dict]:
        """
        更新滤波器状态

        参数:
            z_human: 人手位置观测 [x, y, z] (单位: 米)
            z_virtual: 视觉引导位置观测 [x, y, z] (单位: 米)
            alpha: 意图因子 (0=远离目标, 1=靠近目标)

        返回:
            x_filtered: 滤波后状态 [x, y, z, vx, vy, vz] (单位: 米, 米/秒)
            confidence: 当前置信度 c(t) ∈ [0, 1]
            debug_info: 调试信息字典 {
                'R_virtual': float,  # 当前虚拟观测噪声
                'K_virtual': float,  # 虚拟观测卡尔曼增益
                'K_human': float,    # 人手观测卡尔曼增益
                'delta_norm': float  # 人机冲突强度
            }
        """
        pass

    def reset(self, initial_state: np.ndarray):
        """
        重置滤波器状态

        参数:
            initial_state: 初始状态 [x, y, z, vx, vy, vz]
        """
        pass
```

### 2. 视觉感知接口（B提供，A使用）

**文件位置**: `src/perception/camera.py`

```python
def get_wrist_pose() -> np.ndarray:
    """
    获取人手腕部位置（世界坐标系）

    返回:
        pose: [x, y, z, qx, qy, qz, qw] (单位: 米)
              前3个是位置，后4个是四元数姿态

    异常:
        VisionLostError: 视觉丢失时抛出

    注意:
        - 坐标系: 机器人基座坐标系
        - 更新频率: 30Hz
        - 延迟: ~33ms
    """
    pass

def get_visual_target() -> np.ndarray:
    """
    获取视觉引导目标位置（如USB插口）

    返回:
        target: [x, y, z] (单位: 米)

    异常:
        TargetNotFoundError: 目标未检测到时抛出

    注意:
        - 坐标系: 机器人基座坐标系
        - 标定误差: 3-8mm
    """
    pass
```

### 3. 机器人控制接口（B提供，A使用）

**文件位置**: `src/control/robot_interface.py`

```python
def send_target_pose(pose: np.ndarray,
                     velocity_scale: float = 1.0) -> bool:
    """
    发送目标位姿给机器人

    参数:
        pose: [x, y, z, qx, qy, qz, qw] (单位: 米)
        velocity_scale: 速度缩放因子 [0.1, 1.0]

    返回:
        success: 是否成功发送

    注意:
        - 控制频率: 500Hz
        - 执行器延迟: ~20ms
    """
    pass

def emergency_stop() -> None:
    """
    紧急停止机器人

    注意:
        - 响应时间: <10ms
        - 会清空运动队列
    """
    pass

def is_in_safe_workspace(pose: np.ndarray) -> bool:
    """
    检查位姿是否在安全工作空间内

    参数:
        pose: [x, y, z, qx, qy, qz, qw]

    返回:
        safe: 是否安全
    """
    pass
```

### 4. 意图检测接口（B实现，简化版本）

**文件位置**: `src/core/intent_detector.py`

```python
def compute_alpha(z_human: np.ndarray,
                  z_virtual: np.ndarray,
                  v_human: np.ndarray,
                  config: dict) -> float:
    """
    计算意图因子α

    参数:
        z_human: 人手位置 [x, y, z]
        z_virtual: 虚拟目标位置 [x, y, z]
        v_human: 人手速度 [vx, vy, vz]
        config: 配置字典 {
            'distance_threshold': 0.15,  # 距离阈值
            'sigmoid_k': 15,             # Sigmoid斜率
            'velocity_beta': 2.0         # 速度衰减系数
        }

    返回:
        alpha: 意图因子 ∈ [0, 1]

    公式（简化版）:
        distance = ||z_human - z_virtual||
        alpha_dist = 1 / (1 + exp(-k * (threshold - distance)))
        alpha_vel = 1 / (1 + beta * ||v_human||)
        alpha = 0.5 * alpha_dist + 0.5 * alpha_vel
    """
    pass
```

---

## 数据流图

```
┌─────────────────┐
│  视觉系统 (B)   │
│  - MediaPipe    │
│  - 手眼标定     │
└────────┬────────┘
         │ get_wrist_pose()
         │ get_visual_target()
         ▼
┌─────────────────┐
│  意图检测 (B)   │
│  compute_alpha()│
└────────┬────────┘
         │ alpha
         ▼
┌─────────────────┐      ┌─────────────────┐
│  人手观测 (B)   │      │  视觉引导 (B)   │
│  z_human        │      │  z_virtual      │
└────────┬────────┘      └────────┬────────┘
         │                        │
         └────────┬───────────────┘
                  ▼
         ┌─────────────────┐
         │  卡尔曼滤波 (A) │
         │  VISTKalmanFilter│
         └────────┬────────┘
                  │ x_filtered, confidence
                  ▼
         ┌─────────────────┐
         │  机器人控制 (B) │
         │  send_target_pose│
         └─────────────────┘
```

---

## 配置文件格式

**文件位置**: `config/system_config.yaml`

```yaml
vist_kalman:
  dt: 0.002  # 采样时间 (500Hz)

  noise:
    R_human: 0.005      # 人手观测噪声
    R_virtual_base: 0.01  # 虚拟引导基础噪声
    Q_base: 0.001       # 过程噪声基础值

  confidence:
    lambda_decay: 5.0    # 置信度衰减率
    lambda_recover: 0.5  # 置信度恢复率
    delta_threshold: 0.005  # 冲突检测阈值 (5mm)
    lambda_escape: 200   # 挣脱增益系数

intent_detection:
  distance_threshold: 0.15  # 距离阈值 (m)
  sigmoid_k: 15            # Sigmoid斜率
  velocity_beta: 2.0       # 速度衰减系数

robot:
  control_frequency: 500  # 控制频率 (Hz)
  velocity_scale: 0.8     # 默认速度缩放

vision:
  update_frequency: 30    # 视觉更新频率 (Hz)
  calibration_error: 0.005  # 标定误差 (m)
```

---

## 开发流程

### 阶段1：接口实现（今晚，并行）

**A的任务**：
1. 实现`VISTKalmanFilter`类
2. 写单元测试（用假数据）
3. 确保接口签名完全符合规范

**B的任务**：
1. 实现`get_wrist_pose()`
2. 实现`get_visual_target()`
3. 实现`compute_alpha()`（简化版）
4. 写单元测试

### 阶段2：集成测试（明天上午）

**联调点**：
1. B调用A的`VISTKalmanFilter`
2. 用真实视觉数据测试
3. 检查数据流是否正常

### 阶段3：并行开发（明天下午-后天）

**A的任务**：
- 离线仿真（不依赖B）
- 数学理论完善
- 论文图表生成

**B的任务**：
- 真机实验
- 数据采集
- 视频录制

---

## 接口变更流程

⚠️ **重要**: 接口签名已冻结，但内部实现可以自由修改

### 冻结的部分（不能改）：
- `VISTKalmanFilter.update()`的**函数签名**（参数和返回值）
- `get_wrist_pose()`的返回格式
- `send_target_pose()`的参数格式

### 可以自由修改的部分：
- `VISTKalmanFilter`的**内部实现**（A可以随意修改数学建模）
- `get_wrist_pose()`的**内部实现**（B可以优化视觉算法）
- 配置文件的参数（只要不破坏接口）

### 如果必须修改接口签名：
1. 提出变更请求（说明原因）
2. 双方讨论并同意
3. 更新本文档
4. 通知对方更新代码

---

## 常见问题

### Q1: 如果视觉丢失怎么办？
**A**: B的`get_wrist_pose()`会抛出`VisionLostError`，A的主循环需要捕获并处理（例如：使用上一帧数据）

### Q2: 如果机器人超出安全范围怎么办？
**A**: B在`send_target_pose()`内部会检查`is_in_safe_workspace()`，如果不安全会拒绝执行并返回`False`

### Q3: 配置文件谁负责维护？
**A**: A负责`vist_kalman`和`intent_detection`部分，B负责`robot`和`vision`部分

---

**最后更新**: 2026-02-11
**维护者**: 人员A + 人员B
