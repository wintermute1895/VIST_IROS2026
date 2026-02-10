# 头部相机标定使用指南

## 📋 快速开始

本指南说明如何为头部相机（Intel RealSense D435i）进行 Eye-to-Hand 标定。

---

## 🔧 准备工作

### 1. 硬件准备

**关键区别**：
- ❌ **不要**把标定板固定在桌面上
- ✅ **必须**把标定板安装在机械臂末端

**安装方法**：
```
方式 1: 使用夹持器夹住标定板（推荐）
方式 2: 3D 打印固定支架安装在末端法兰
方式 3: 使用胶带临时固定（不推荐）
```

### 2. 配置文件

配置文件已准备好：`head_camera_config.yaml`

**关键配置**：
```yaml
calibration_solver:
  calibration_type: "eye_to_hand"  # ⚠️ 关键：眼到手标定

camera:
  camera_type: "realsense_d435i"   # D435i 相机

storage:
  data_dir: "calibration_data_head_camera"  # 独立的数据目录
```

---

## 📝 标定步骤

### 步骤 1: 数据采集

```bash
cd /home/ilex/Dev/VIST/calibration
python3 data_collection.py --config head_camera_config.yaml
```

**采集要点**：
1. 头部相机固定不动
2. 标定板安装在机械臂末端
3. 移动机械臂（带着标定板）到不同位置
4. 确保标定板始终在相机视野内
5. 采集 15-20 组不同位姿的数据

**推荐采集策略**：
```
1. 中心区域（5 组）
   - 标定板在相机正前方
   - 距离 50-80cm
   - 不同高度

2. 左侧区域（5 组）
   - 标定板向左移动
   - 保持在视野内

3. 右侧区域（5 组）
   - 标定板向右移动
   - 保持在视野内

4. 不同姿态（5 组）
   - 改变标定板倾斜角度
   - 增加旋转多样性
```

**操作说明**：
- 按 `s` 键：保存当前样本
- 按 `q` 键：退出采集

### 步骤 2: 标定计算

```bash
cd /home/ilex/Dev/VIST/calibration
python3 calibration_solver.py --config head_camera_config.yaml
```

**输出结果**：
- `T_base_to_cam`：相机相对于机器人基座的变换矩阵
- 保存在 `calibration_data_head_camera/eye_to_hand_result.json`

### 步骤 3: 结果验证

```bash
cd /home/ilex/Dev/VIST/calibration
python3 calibration_error_analysis.py --config head_camera_config.yaml
```

**质量标准**：
- 优秀: < 1.0 像素
- 良好: < 2.0 像素
- 可接受: < 5.0 像素

---

## 🎯 标定结果使用

### 坐标转换示例

```python
import json
import numpy as np

# 加载头部相机标定结果
with open('calibration_data_head_camera/eye_to_hand_result.json', 'r') as f:
    calib_result = json.load(f)

T_base_to_cam = np.array(calib_result['T_base_to_cam'])

def camera_to_base(point_cam):
    """将相机坐标系中的点转换到机器人基座坐标系"""
    point_homo = np.append(point_cam, 1.0)  # 齐次坐标
    point_base = T_base_to_cam @ point_homo
    return point_base[:3]

# 示例：检测到目标在相机坐标系中的位置
target_pos_cam = np.array([0.1, 0.2, 0.5])  # [x, y, z] in camera frame

# 转换到机器人基座坐标系
target_pos_base = camera_to_base(target_pos_cam)

print(f"目标在基座坐标系中的位置: {target_pos_base}")
```

---

## 🔄 与手内相机的对比

| 特性 | 手内相机 (D405) | 头部相机 (D435i) |
|------|----------------|-----------------|
| **标定类型** | Eye-in-Hand | Eye-to-Hand |
| **相机位置** | 机械臂末端 | 固定在头部 |
| **标定板位置** | 固定不动 | 安装在末端 |
| **配置文件** | `calibration_config_template.yaml` | `head_camera_config.yaml` |
| **数据目录** | `calibration_data` | `calibration_data_head_camera` |
| **结果矩阵** | `T_end_to_cam` | `T_base_to_cam` |
| **用途** | 近距离精密操作 | 全局视野观察 |

---

## ⚠️ 常见问题

### Q1: 数据采集时检测不到标定板？

**可能原因**：
- 标定板不在相机视野内
- 标定板距离太远
- 光照条件差

**解决方法**：
1. 调整机器人位姿，确保标定板在视野内
2. 调整距离到 50-80cm
3. 改善光照条件

### Q2: 标定误差很大？

**可能原因**：
- 标定板尺寸测量不准确
- 位姿多样性不足
- 标定板安装不稳定

**解决方法**：
1. 重新精确测量标定板尺寸
2. 增加位姿多样性
3. 确保标定板牢固安装在末端

### Q3: 两个相机可以同时使用吗？

**答案**：可以！完成两个相机的标定后：
- 手内相机（D405）：用于近距离精密操作
- 头部相机（D435i）：用于全局视野和远距离观察

两个相机的标定结果独立保存，可以在系统中同时使用。

---

## 📊 标定质量检查清单

在使用标定结果前，请确认：

- [ ] 标定板已牢固安装在机械臂末端
- [ ] 采集了至少 15 组数据
- [ ] 位姿具有足够多样性
- [ ] 所有样本都成功检测到标定板
- [ ] 平均重投影误差 < 2.0 像素
- [ ] 标定结果已保存到 `calibration_data_head_camera/`
- [ ] 已进行误差分析验证

---

## 🎯 总结

**关键步骤**：
1. 标定板安装在机械臂末端（不是固定在桌面）
2. 使用 `head_camera_config.yaml` 配置文件
3. 运行数据采集、标定计算、结果验证
4. 得到 `T_base_to_cam` 变换矩阵

**与手内相机的区别**：
- 硬件安装方式不同
- 标定类型不同（eye_to_hand vs eye_in_hand）
- 输出结果不同（T_base_to_cam vs T_end_to_cam）

**最后更新**: 2026-02-10
