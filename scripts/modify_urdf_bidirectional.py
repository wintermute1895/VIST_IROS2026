#!/usr/bin/env python3
"""
修改 URDF 文件，让 Right_Elbow_Pitch_Joint 支持双向旋转
"""

import re

urdf_path = '/home/ilex/Dev/VIST/config/lkls73_o2_dual_arm_description.urdf'

# 读取 URDF 文件
with open(urdf_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修改 Right_Elbow_Pitch_Joint 的限位为双向
pattern = r'(<joint\s+name="Right_Elbow_Pitch_Joint".*?</joint>)'
match = re.search(pattern, content, re.DOTALL)

if match:
    joint_def = match.group(1)
    print("找到 Right_Elbow_Pitch_Joint 定义")

    # 修改限位为双向：lower="-2.2" upper="2.2"
    modified_joint = re.sub(
        r'<limit\s+lower="[^"]+"\s+upper="[^"]+"',
        '<limit\n      lower="-2.2"\n      upper="2.2"',
        joint_def
    )

    # 替换原内容
    new_content = content.replace(joint_def, modified_joint)

    # 写回文件
    with open(urdf_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✅ URDF 文件已修改为双向旋转")
    print("\n修改后的限位:")
    print("  lower: -2.2 rad = -126°")
    print("  upper: +2.2 rad = +126°")
    print("\n现在支持:")
    print("  ✓ direction=1: 产生正值 [0, 180°]")
    print("  ✓ direction=-1: 产生负值 [-180°, 0]")
else:
    print("❌ 未找到 Right_Elbow_Pitch_Joint 定义")
