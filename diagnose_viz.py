#!/usr/bin/env python3
"""
诊断脚本：检查目标坐标系可视化问题
"""
import sys
import time

print("🔍 目标坐标系可视化诊断")
print("=" * 60)
print()

# 检查1：是否有 arm_node 在运行
print("检查1：查找运行中的 arm_node 进程...")
import subprocess
result = subprocess.run(['pgrep', '-f', 'arm_node'], capture_output=True, text=True)
if result.stdout.strip():
    print(f"✅ 找到 arm_node 进程: PID {result.stdout.strip()}")
else:
    print("❌ 未找到 arm_node 进程")
    print("   请先运行: ./run_arm_node.sh")
    sys.exit(1)

print()

# 检查2：是否有测试脚本在发送数据
print("检查2：查找运行中的 test_motion_mapper 进程...")
result = subprocess.run(['pgrep', '-f', 'test_motion_mapper'], capture_output=True, text=True)
if result.stdout.strip():
    print(f"✅ 找到 test_motion_mapper 进程: PID {result.stdout.strip()}")
else:
    print("⚠️ 未找到 test_motion_mapper 进程")
    print("   建议运行: ./run_test_mapper.sh")
    print("   （如果不运行测试脚本，目标坐标系不会更新）")

print()

# 检查3：UDP 端口是否在监听
print("检查3：检查 UDP 端口 6001 是否在监听...")
result = subprocess.run(['netstat', '-uln'], capture_output=True, text=True)
if '6001' in result.stdout:
    print("✅ UDP 端口 6001 正在监听")
else:
    print("⚠️ UDP 端口 6001 未在监听")

print()

# 检查4：MeshCat 服务器是否在运行
print("检查4：检查 MeshCat 服务器...")
result = subprocess.run(['netstat', '-tln'], capture_output=True, text=True)
if '7000' in result.stdout or '7001' in result.stdout:
    print("✅ MeshCat 服务器正在运行")
    print("   请在浏览器中打开: http://127.0.0.1:7000/static/")
else:
    print("⚠️ MeshCat 服务器未运行")

print()
print("=" * 60)
print("📋 诊断完成")
print()
print("💡 提示：")
print("1. 确保两个终端都在运行：")
print("   - 终端1: ./run_arm_node.sh")
print("   - 终端2: ./run_test_mapper.sh")
print()
print("2. 在 MeshCat 中查找目标坐标系：")
print("   - 打开浏览器: http://127.0.0.1:7000/static/")
print("   - 在左侧面板中展开 'target_frame' 节点")
print("   - 应该能看到 x_axis (红), y_axis (绿), z_axis (蓝)")
print()
print("3. 如果看不到坐标系：")
print("   - 尝试缩放视图（鼠标滚轮）")
print("   - 尝试旋转视图（鼠标拖动）")
print("   - 坐标系初始位置在 [0.3, 0.0, 0.3]")
print("   - 坐标轴长度为 15cm，半径为 8mm")
