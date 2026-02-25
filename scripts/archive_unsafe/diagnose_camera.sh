#!/bin/bash
# RealSense相机诊断和修复脚本

echo "========================================="
echo "RealSense D435i 相机诊断"
echo "========================================="
echo ""

# 1. 检查USB设备
echo "1️⃣ 检查USB设备..."
if lsusb | grep -i "8087:0033\|8087:0b3a\|8087:0ad3" > /dev/null; then
    echo "✅ 检测到Intel RealSense USB设备"
    lsusb | grep -i "8087"
else
    echo "❌ 未检测到RealSense USB设备"
    echo "   请检查："
    echo "   - 相机是否插入USB 3.0接口（蓝色接口）"
    echo "   - USB线缆是否正常"
fi
echo ""

# 2. 检查video设备
echo "2️⃣ 检查video设备..."
if ls /dev/video* > /dev/null 2>&1; then
    echo "✅ 检测到video设备:"
    ls -l /dev/video* | head -5
else
    echo "❌ 未检测到video设备"
fi
echo ""

# 3. 检查用户权限
echo "3️⃣ 检查用户权限..."
if groups | grep -q video; then
    echo "✅ 用户在video组"
else
    echo "❌ 用户不在video组"
    echo "   运行: sudo usermod -aG video $USER"
    echo "   然后重新登录"
fi
echo ""

# 4. 检查udev规则
echo "4️⃣ 检查udev规则..."
if [ -f /etc/udev/rules.d/99-realsense-libusb.rules ]; then
    echo "✅ RealSense udev规则已安装"
else
    echo "❌ RealSense udev规则未安装"
    echo "   正在安装..."

    # 下载并安装udev规则
    sudo wget -q https://raw.githubusercontent.com/IntelRealSense/librealsense/master/config/99-realsense-libusb.rules \
        -O /etc/udev/rules.d/99-realsense-libusb.rules

    if [ $? -eq 0 ]; then
        echo "✅ udev规则已下载"
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo "✅ udev规则已重新加载"
        echo "   请重新插拔相机"
    else
        echo "❌ 下载udev规则失败"
        echo "   手动创建规则文件..."

        sudo tee /etc/udev/rules.d/99-realsense-libusb.rules > /dev/null << 'EOF'
# Intel RealSense D400 series
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b07", MODE:="0666", GROUP:="video"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b3a", MODE:="0666", GROUP:="video"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad3", MODE:="0666", GROUP:="video"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0ad4", MODE:="0666", GROUP:="video"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b3d", MODE:="0666", GROUP:="video"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="8086", ATTRS{idProduct}=="0b07", MODE:="0666", GROUP:="video"
EOF
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        echo "✅ udev规则已创建并重新加载"
    fi
fi
echo ""

# 5. 测试pyrealsense2
echo "5️⃣ 测试pyrealsense2..."
python3 << 'PYEOF'
try:
    import pyrealsense2 as rs
    ctx = rs.context()
    devices = ctx.query_devices()

    if len(devices) == 0:
        print("❌ pyrealsense2未检测到设备")
        print("   可能需要:")
        print("   1. 重新插拔相机")
        print("   2. 重启电脑")
        print("   3. 检查USB 3.0连接")
    else:
        print(f"✅ 检测到 {len(devices)} 个RealSense设备:")
        for dev in devices:
            print(f"   - {dev.get_info(rs.camera_info.name)}")
            print(f"     序列号: {dev.get_info(rs.camera_info.serial_number)}")
            print(f"     固件: {dev.get_info(rs.camera_info.firmware_version)}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
PYEOF
echo ""

echo "========================================="
echo "诊断完成"
echo "========================================="
echo ""
echo "💡 建议操作:"
echo "1. 如果安装了udev规则，请重新插拔相机"
echo "2. 确保相机插在USB 3.0接口（蓝色）"
echo "3. 运行: rs-enumerate-devices 查看相机"
echo "4. 刷新Web界面查看相机列表"
