#!/usr/bin/env python3
"""
修改 URDF 文件，翻转 Right_Elbow_Pitch_Joint 关节轴方向
"""

import re

urdf_path = '/home/ilex/Dev/VIST/config/lkls73_o2_dual_arm_description.urdf'

# 读取 URDF 文件
with open(urdf_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修改 Right_Elbow_Pitch_Joint 的轴方向和限位
# 查找 Right_Elbow_Pitch_Joint 定义
pattern = r'(<joint\s+name="Right_Elbow_Pitch_Joint".*?</joint>)'
match = re.search(pattern, content, re.DOTALL)

if match:
    joint_def = match.group(1)
    print("找到 Right_Elbow_Pitch_Joint 定义:")
    print(joint_def[:200] + "...")

    # 修改轴方向：0 1 0 → 0 -1 0
    modified_joint = re.sub(
        r'<axis\s+xyz="0 1 0"\s*/>',
        '<axis\n      xyz="0 -1 0" />',
        joint_def
    )

    # 修改限位：lower="0" upper="2.2" → lower="-2.2" upper="0"
    modified_joint = re.sub(
        r'<limit\s+lower="0"\s+upper="2\.2"',
        '<limit\n      lower="-2.2"\n      upper="0"',
        modified_joint
    )

    # 替换原内容
    new_content = content.replace(joint_def, modified_joint)

    # 写回文件
    with open(urdf_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("\n✅ URDF 文件已修改")
    print("\n修改后的关节定义:")
    print(modified_joint[:300])
else:
    print("❌ 未找到 Right_Elbow_Pitch_Joint 定义")
