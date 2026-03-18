#!/bin/bash
# 创建符号链接，让URDF能找到mesh文件

echo "=========================================="
echo "创建mesh文件符号链接"
echo "=========================================="
echo ""

URDF_DIR="/home/ilex/Dev/VIST/config/urdf"
MESH_DIR="/home/ilex/Dev/VIST/config/meshes"

# 在URDF目录下创建meshes符号链接
cd "$URDF_DIR"

if [ -L "meshes" ]; then
    echo "✓ 符号链接已存在"
elif [ -d "meshes" ]; then
    echo "⚠ meshes目录已存在（不是符号链接）"
    echo "  跳过创建"
else
    echo "创建符号链接: meshes -> $MESH_DIR"
    ln -s "$MESH_DIR" meshes
    echo "✓ 创建成功"
fi

echo ""
echo "验证:"
ls -la "$URDF_DIR/meshes" | head -5

echo ""
echo "=========================================="
echo "完成"
echo "=========================================="
echo ""
echo "现在URDF文件可以通过相对路径找到mesh文件了"
echo ""
echo "在Foxglove中:"
echo "  1. 3D面板 → URDF设置"
echo "  2. Source: File"
echo "  3. Upload: /home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description.urdf"
echo ""