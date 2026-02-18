#!/usr/bin/env python3
"""
测试 SE3_distance 函数的修复

验证在有旋转的情况下，新实现比旧实现更准确
"""

import numpy as np
import pinocchio as pin
from src.utils.lie_algebra import SE3_distance


def old_SE3_distance(M1: pin.SE3, M2: pin.SE3):
    """旧的（有问题的）实现"""
    M_rel = M1.actInv(M2)
    v = pin.log(M_rel)
    translation_dist = np.linalg.norm(v.linear)
    rotation_dist = np.linalg.norm(v.angular)
    return translation_dist, rotation_dist


print("🧪 测试 SE3_distance 修复\n")
print("=" * 80)

# 测试 1: 纯平移（无旋转）
print("\n测试 1: 纯平移（无旋转）")
M1 = pin.SE3.Identity()
M2 = pin.SE3(np.eye(3), np.array([1.0, 0.5, 0.2]))

t_dist_new, r_dist_new = SE3_distance(M1, M2)
t_dist_old, r_dist_old = old_SE3_distance(M1, M2)

expected_t_dist = np.linalg.norm([1.0, 0.5, 0.2])

print(f"  预期平移距离: {expected_t_dist:.6f} m")
print(f"  新实现: t={t_dist_new:.6f} m, r={r_dist_new:.6f} rad")
print(f"  旧实现: t={t_dist_old:.6f} m, r={r_dist_old:.6f} rad")
print(f"  差异: Δt={abs(t_dist_new - t_dist_old):.6e} m")

if abs(t_dist_new - expected_t_dist) < 1e-10:
    print("  ✅ 新实现正确")
else:
    print("  ❌ 新实现有误")

# 测试 2: 纯旋转（无平移）
print("\n测试 2: 纯旋转（无平移）")
R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/4)  # 绕 Z 轴旋转 45°
M1 = pin.SE3.Identity()
M2 = pin.SE3(R2, np.array([0, 0, 0]))

t_dist_new, r_dist_new = SE3_distance(M1, M2)
t_dist_old, r_dist_old = old_SE3_distance(M1, M2)

expected_r_dist = np.pi / 4

print(f"  预期旋转距离: {expected_r_dist:.6f} rad ({np.degrees(expected_r_dist):.2f}°)")
print(f"  新实现: t={t_dist_new:.6f} m, r={r_dist_new:.6f} rad")
print(f"  旧实现: t={t_dist_old:.6f} m, r={r_dist_old:.6f} rad")
print(f"  差异: Δr={abs(r_dist_new - r_dist_old):.6e} rad")

if abs(r_dist_new - expected_r_dist) < 1e-10:
    print("  ✅ 新实现正确")
else:
    print("  ❌ 新实现有误")

# 测试 3: 平移 + 旋转（关键测试）
print("\n测试 3: 平移 + 旋转（关键测试）")
R2 = pin.rpy.rpyToMatrix(0, 0, np.pi/2)  # 绕 Z 轴旋转 90°
M1 = pin.SE3.Identity()
M2 = pin.SE3(R2, np.array([1.0, 0, 0]))

t_dist_new, r_dist_new = SE3_distance(M1, M2)
t_dist_old, r_dist_old = old_SE3_distance(M1, M2)

expected_t_dist = 1.0
expected_r_dist = np.pi / 2

print(f"  预期: t={expected_t_dist:.6f} m, r={expected_r_dist:.6f} rad ({np.degrees(expected_r_dist):.2f}°)")
print(f"  新实现: t={t_dist_new:.6f} m, r={r_dist_new:.6f} rad")
print(f"  旧实现: t={t_dist_old:.6f} m, r={r_dist_old:.6f} rad")
print(f"  差异: Δt={abs(t_dist_new - t_dist_old):.6e} m, Δr={abs(r_dist_new - r_dist_old):.6e} rad")

if abs(t_dist_new - expected_t_dist) < 1e-10 and abs(r_dist_new - expected_r_dist) < 1e-10:
    print("  ✅ 新实现正确")
else:
    print("  ❌ 新实现有误")

# 测试 4: 大旋转 + 平移（最能体现差异的测试）
print("\n测试 4: 大旋转 + 平移（最能体现差异）")
R2 = pin.rpy.rpyToMatrix(np.pi/3, np.pi/4, np.pi/2)  # 复杂旋转
M1 = pin.SE3.Identity()
M2 = pin.SE3(R2, np.array([2.0, 1.5, 1.0]))

t_dist_new, r_dist_new = SE3_distance(M1, M2)
t_dist_old, r_dist_old = old_SE3_distance(M1, M2)

expected_t_dist = np.linalg.norm([2.0, 1.5, 1.0])

print(f"  预期平移距离: {expected_t_dist:.6f} m")
print(f"  新实现: t={t_dist_new:.6f} m, r={r_dist_new:.6f} rad ({np.degrees(r_dist_new):.2f}°)")
print(f"  旧实现: t={t_dist_old:.6f} m, r={r_dist_old:.6f} rad ({np.degrees(r_dist_old):.2f}°)")
print(f"  差异: Δt={abs(t_dist_new - t_dist_old):.6e} m ({abs(t_dist_new - t_dist_old)/expected_t_dist*100:.2f}%)")

if abs(t_dist_new - expected_t_dist) < 1e-10:
    print("  ✅ 新实现正确")
    if abs(t_dist_old - expected_t_dist) > 1e-6:
        print(f"  ⚠️  旧实现误差: {abs(t_dist_old - expected_t_dist):.6e} m ({abs(t_dist_old - expected_t_dist)/expected_t_dist*100:.2f}%)")
else:
    print("  ❌ 新实现有误")

print("\n" + "=" * 80)
print("✅ 测试完成")
print("\n总结:")
print("  - 新实现直接使用 M_rel.translation 计算平移距离（准确）")
print("  - 旧实现使用 pin.log(M_rel).linear（在有旋转时不准确）")
print("  - 在纯平移或小旋转时，两者差异很小")
print("  - 在大旋转时，旧实现会产生明显误差")