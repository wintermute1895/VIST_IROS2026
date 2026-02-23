# 滤波器代码整理方案

## 当前问题

滤波器代码分散在两个地方，职责不清：

### 1. src/core/ 目录
- `one_euro_filter.py` (6990字节)
  - `OneEuroFilter` - 基础One Euro滤波器
  - `VectorOneEuroFilter` - 向量版本（用于位置滤波）
  - `QuaternionOneEuroFilter` - 四元数版本（用于姿态滤波）
  - **使用者**: `src/core/motion_mapper.py`

- `vist_kalman_filter.py` (66429字节)
  - `VISTKalmanFilter` - VIST核心算法的卡尔曼滤波器
  - **使用者**: `src/control/vist_controller.py`

### 2. src/control/filters/ 目录
- `base_filter.py` - 滤波器抽象基类
- `filter_factory.py` - 滤波器工厂
- `low_pass_filter.py` - 低通滤波器
- `one_euro_filter.py` (6747字节) - One Euro滤波器（重构版本）
  - `OneEuroFilter(BaseFilter)` - 继承自BaseFilter
  - **使用者**: 无（未被使用）

## 问题分析

### 重复代码
- `one_euro_filter.py` 在两个地方都有，但版本不同：
  - `src/core/` 版本：原始实现，有3个类（基础、向量、四元数）
  - `src/control/filters/` 版本：重构版本，只有1个类，继承BaseFilter
  - **问题**: 重构未完成，新版本未被使用

### 职责混乱
- **src/core/** 应该包含：核心算法（VIST、IK、意图检测等）
- **src/control/** 应该包含：控制器和通用滤波器
- **当前问题**:
  - `vist_kalman_filter.py` 在 `src/core/` 是合理的（VIST核心算法）
  - `one_euro_filter.py` 在 `src/core/` 不太合理（应该是通用工具）

## 推荐方案

### 方案A: 合并到 src/control/filters/（推荐）

将所有滤波器统一到 `src/control/filters/`，保持清晰的职责划分：

```
src/
├── core/                           # 核心算法（不包含通用滤波器）
│   ├── vist_kalman_filter.py      # VIST核心算法（保留）
│   ├── intent_detector.py
│   ├── ik_solver.py
│   └── ...
│
├── control/
│   ├── filters/                    # 所有滤波器
│   │   ├── base_filter.py         # 抽象基类
│   │   ├── filter_factory.py      # 工厂模式
│   │   ├── low_pass_filter.py     # 低通滤波器
│   │   ├── one_euro_filter.py     # One Euro滤波器（合并版本）
│   │   └── __init__.py
│   ├── vist_controller.py
│   └── ...
│
└── ...
```

**实施步骤**:
1. 合并两个 `one_euro_filter.py`：
   - 保留 `src/core/` 版本的3个类（OneEuroFilter, VectorOneEuroFilter, QuaternionOneEuroFilter）
   - 让它们继承 `BaseFilter`
   - 移动到 `src/control/filters/one_euro_filter.py`

2. 更新导入路径：
   - `src/core/motion_mapper.py`:
     ```python
     # 从
     from src.core.one_euro_filter import VectorOneEuroFilter, QuaternionOneEuroFilter
     # 改为
     from src.control.filters.one_euro_filter import VectorOneEuroFilter, QuaternionOneEuroFilter
     ```

3. 删除 `src/core/one_euro_filter.py`

### 方案B: 保持现状，删除重复（最小改动）

保持 `src/core/one_euro_filter.py`，删除 `src/control/filters/one_euro_filter.py`：

```
src/
├── core/
│   ├── one_euro_filter.py         # 保留（motion_mapper使用）
│   ├── vist_kalman_filter.py      # 保留（VIST核心）
│   └── ...
│
├── control/
│   ├── filters/
│   │   ├── base_filter.py
│   │   ├── filter_factory.py
│   │   ├── low_pass_filter.py
│   │   └── one_euro_filter.py     # 删除（未使用）
│   └── ...
```

**实施步骤**:
1. 删除 `src/control/filters/one_euro_filter.py`
2. 在 `src/core/one_euro_filter.py` 添加注释说明为什么在core目录

### 方案C: 创建 src/utils/filters/（最规范）

创建独立的工具模块存放通用滤波器：

```
src/
├── core/                           # 核心算法
│   ├── vist_kalman_filter.py      # VIST核心（保留在core）
│   ├── intent_detector.py
│   └── ...
│
├── control/                        # 控制器
│   ├── vist_controller.py
│   └── ...
│
├── utils/                          # 工具函数
│   ├── filters/                    # 通用滤波器
│   │   ├── base_filter.py
│   │   ├── filter_factory.py
│   │   ├── low_pass_filter.py
│   │   ├── one_euro_filter.py
│   │   └── __init__.py
│   ├── lie_algebra.py
│   └── ...
```

## 推荐行动

### 立即执行（方案B - 最小改动）

1. 删除未使用的重复文件：
   ```bash
   rm src/control/filters/one_euro_filter.py
   ```

2. 在 `src/core/one_euro_filter.py` 添加说明：
   ```python
   """
   One Euro Filter Implementation

   Note: This file is in src/core/ because it provides specialized versions
   (VectorOneEuroFilter, QuaternionOneEuroFilter) used by motion_mapper.py.

   For general-purpose filtering, see src/control/filters/.
   """
   ```

3. 更新 `src/control/filters/__init__.py`：
   ```python
   from .base_filter import BaseFilter
   from .low_pass_filter import LowPassFilter
   from .filter_factory import FilterFactory

   # Note: OneEuroFilter specialized versions are in src/core/one_euro_filter.py
   # because they are tightly coupled with motion mapping

   __all__ = ['BaseFilter', 'LowPassFilter', 'FilterFactory']
   ```

### 后续优化（方案A）

如果有时间，可以重构为方案A，将所有滤波器统一管理。

## 滤波器职责说明

### VIST Kalman Filter (src/core/)
- **职责**: VIST算法的核心组件
- **特点**:
  - 意图驱动的自适应卡尔曼滤波
  - 与VIST算法紧密耦合
  - 不是通用滤波器
- **位置**: 应该在 `src/core/`（核心算法）

### One Euro Filter (src/core/)
- **职责**: 运动跟踪的自适应滤波
- **特点**:
  - 有专门的向量和四元数版本
  - 被motion_mapper使用
  - 相对通用，但有特殊版本
- **位置**:
  - 当前在 `src/core/`（因为历史原因）
  - 理想应该在 `src/control/filters/` 或 `src/utils/filters/`

### Low Pass Filter (src/control/filters/)
- **职责**: 通用低通滤波
- **特点**:
  - 简单的指数平滑
  - 完全通用
- **位置**: `src/control/filters/`（正确）

## 总结

**当前状态**:
- ❌ 有重复代码（two one_euro_filter.py）
- ❌ 职责不够清晰
- ⚠️ 重构未完成

**推荐行动**:
1. 立即删除 `src/control/filters/one_euro_filter.py`（未使用）
2. 保留 `src/core/one_euro_filter.py`（被motion_mapper使用）
3. 添加注释说明原因
4. 后续考虑统一到 `src/control/filters/` 或 `src/utils/filters/`

---

**准备好清理重复代码了吗？**
