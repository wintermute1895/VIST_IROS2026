#!/usr/bin/env python3
"""
快速测试RealSense RGB相机
"""
import cv2

print("测试 RealSense D435i RGB相机...")

# video8 是RGB彩色相机
cap = cv2.VideoCapture(8)

if not cap.isOpened():
    print("❌ 无法打开RealSense RGB相机 (/dev/video8)")
    exit(1)

print("✅ RealSense RGB相机已打开")
print("按 'q' 退出")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    cv2.imshow("RealSense RGB Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("✅ 测试完成")
