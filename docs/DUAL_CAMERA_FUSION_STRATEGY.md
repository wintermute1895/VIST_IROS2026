# 双相机融合策略

## 架构设计原则

### 1. 互补而非冲突

两个相机的作用是**互补**的，而不是竞争的：

```
阶段划分：
┌─────────────────────────────────────────────────────────┐
│  远距离接近阶段（α < 0.3）                                │
│  - 主要使用：头顶相机（全局视野）                          │
│  - 辅助使用：手内相机（如果目标在视野内）                   │
│  - 融合权重：头顶70% + 手内30%                            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  中距离对准阶段（0.3 < α < 0.8）                          │
│  - 主要使用：手内相机（精度更高）                          │
│  - 辅助使用：头顶相机（提供全局参考）                       │
│  - 融合权重：手内60% + 头顶40%                            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  近距离插入阶段（α > 0.8）                                │
│  - 主要使用：手内相机（唯一可靠来源）                       │
│  - 辅助使用：无（头顶相机可能被遮挡）                       │
│  - 融合权重：手内100%                                     │
└─────────────────────────────────────────────────────────┘
```

### 2. 动态权重调整

融合权重不是固定的，而是根据多个因素动态调整：

```python
def compute_fusion_weights(alpha, distance, visibility):
    """
    根据意图因子、距离和可见性动态计算融合权重

    Args:
        alpha: 意图因子 [0, 1]
        distance: 目标距离（米）
        visibility: 可见性评分 [0, 1]

    Returns:
        (weight_hand, weight_head): 手内和头顶相机的权重
    """
    # 基础权重（根据意图因子）
    if alpha < 0.3:
        # 远距离：头顶相机主导
        base_weight_hand = 0.3
        base_weight_head = 0.7
    elif alpha < 0.8:
        # 中距离：手内相机主导
        base_weight_hand = 0.6
        base_weight_head = 0.4
    else:
        # 近距离：手内相机完全主导
        base_weight_hand = 1.0
        base_weight_head = 0.0

    # 根据可见性调整
    # 如果手内相机看不到目标，降低其权重
    weight_hand = base_weight_hand * visibility['hand']
    weight_head = base_weight_head * visibility['head']

    # 归一化
    total = weight_hand + weight_head
    if total > 0:
        weight_hand /= total
        weight_head /= total

    return weight_hand, weight_head
```

### 3. 冲突检测与处理

当两个相机的观测差异过大时，需要冲突检测：

```python
def detect_observation_conflict(obs_hand, obs_head, threshold=0.05):
    """
    检测双相机观测是否冲突

    Args:
        obs_hand: 手内相机观测（基座坐标系）
        obs_head: 头顶相机观测（基座坐标系）
        threshold: 冲突阈值（米）

    Returns:
        (is_conflict, distance): 是否冲突和观测距离
    """
    distance = np.linalg.norm(obs_hand - obs_head)
    is_conflict = distance > threshold

    if is_conflict:
        print(f"⚠️ 双相机观测冲突: 距离={distance:.3f}m > 阈值={threshold}m")
        print(f"   手内相机: {obs_hand}")
        print(f"   头顶相机: {obs_head}")
        print(f"   可能原因: 标定误差、目标检测错误、遮挡")

    return is_conflict, distance
```

## 实际使用场景

### 场景1：正常融合（无冲突）

```python
# 两个相机都检测到目标，观测一致
target_hand = np.array([0.30, 0.20, 0.15])  # 手内相机观测
target_head = np.array([0.31, 0.19, 0.16])  # 头顶相机观测（略有差异）

# 融合观测
fused = coord_mgr.fuse_dual_camera_observations(
    point_hand_cam=target_hand,
    point_head_cam=target_head,
    T_base_to_end=robot_pose,
    confidence_hand=0.9,
    confidence_head=0.7
)

# 结果: fused ≈ [0.304, 0.197, 0.154]（加权平均）
```

### 场景2：手内相机遮挡（降级到头顶相机）

```python
# 手内相机被遮挡，只有头顶相机有效
target_hand = None  # 手内相机检测失败
target_head = np.array([0.31, 0.19, 0.16])

# 融合观测（自动降级）
fused = coord_mgr.fuse_dual_camera_observations(
    point_hand_cam=target_hand,  # None
    point_head_cam=target_head,
    T_base_to_end=robot_pose,
    confidence_hand=0.0,  # 无效
    confidence_head=0.7
)

# 结果: fused = target_head（只使用头顶相机）
```

### 场景3：观测冲突（选择高置信度）

```python
# 两个相机观测差异过大
target_hand = np.array([0.30, 0.20, 0.15])
target_head = np.array([0.40, 0.25, 0.20])  # 差异10cm！

# 检测冲突
distance = np.linalg.norm(target_hand - target_head)
if distance > 0.05:  # 5cm阈值
    print(f"⚠️ 观测冲突: {distance:.3f}m")

    # 策略1: 选择高置信度的观测
    if confidence_hand > confidence_head:
        fused = target_hand
    else:
        fused = target_head

    # 策略2: 根据意图因子选择
    if alpha > 0.5:
        fused = target_hand  # 近距离优先手内相机
    else:
        fused = target_head  # 远距离优先头顶相机
```

## 完整的融合流程

```python
class EnhancedCoordinateTransformManager(CoordinateTransformManager):
    """增强版坐标变换管理器（带智能融合）"""

    def smart_fuse_observations(
        self,
        obs_hand_cam,
        obs_head_cam,
        T_base_to_end,
        alpha,
        distance_to_target
    ):
        """
        智能融合双相机观测

        考虑因素：
        1. 意图因子α（远近距离）
        2. 目标距离
        3. 观测置信度
        4. 冲突检测
        """
        # 1. 转换到基座坐标系
        if obs_hand_cam is not None:
            obs_hand_base = self.hand_camera_to_base(obs_hand_cam, T_base_to_end)
        else:
            obs_hand_base = None

        if obs_head_cam is not None:
            obs_head_base = self.head_camera_to_base(obs_head_cam)
        else:
            obs_head_base = None

        # 2. 单相机降级
        if obs_hand_base is None:
            return obs_head_base
        if obs_head_base is None:
            return obs_hand_base

        # 3. 冲突检测
        conflict_distance = np.linalg.norm(obs_hand_base - obs_head_base)
        if conflict_distance > 0.05:  # 5cm阈值
            print(f"⚠️ 观测冲突: {conflict_distance:.3f}m")
            # 近距离优先手内，远距离优先头顶
            return obs_hand_base if alpha > 0.5 else obs_head_base

        # 4. 动态权重融合
        if alpha < 0.3:
            # 远距离：头顶70% + 手内30%
            weight_hand, weight_head = 0.3, 0.7
        elif alpha < 0.8:
            # 中距离：手内60% + 头顶40%
            weight_hand, weight_head = 0.6, 0.4
        else:
            # 近距离：手内100%
            weight_hand, weight_head = 1.0, 0.0

        # 5. 加权融合
        fused = weight_hand * obs_hand_base + weight_head * obs_head_base

        print(f"   📷 双相机融合: 手内{weight_hand:.1%} + 头顶{weight_head:.1%}")
        print(f"      手内观测: {obs_hand_base}")
        print(f"      头顶观测: {obs_head_base}")
        print(f"      融合结果: {fused}")

        return fused
```

## 关键设计决策

### 1. 为什么不会冲突？

**答案**：因为两个相机观测的是**同一个物理目标**，经过正确的坐标变换后，应该指向基座坐标系中的**同一个位置**。

如果观测差异过大（>5cm），说明：
- 标定误差
- 目标检测错误
- 相机遮挡
- 目标移动

此时需要冲突检测和降级处理。

### 2. 为什么需要融合？

**答案**：提高鲁棒性和精度

- **鲁棒性**：一个相机失效时，另一个可以接管
- **精度**：两个观测的加权平均可以降低噪声
- **互补**：远距离用头顶，近距离用手内

### 3. 融合权重如何确定？

**答案**：根据意图因子α动态调整

```
α → 0 (远距离): 头顶相机主导（全局视野好）
α → 0.5 (中距离): 两者平衡
α → 1 (近距离): 手内相机主导（精度高）
```

## 总结

1. **变换链清晰**：每个相机有独立的变换链，最终都转换到基座坐标系
2. **融合智能**：根据α、距离、可见性动态调整权重
3. **冲突处理**：检测观测差异，选择高置信度或根据场景降级
4. **互补设计**：两个相机各司其职，不会真正"冲突"

这个设计保证了系统的鲁棒性和精度！