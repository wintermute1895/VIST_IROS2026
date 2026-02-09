"""
ChArUco 标定板生成器
用于生成可打印的 ChArUco 标定板图像
"""

import cv2
import numpy as np
from pathlib import Path

from config import CalibrationConfig


def generate_charuco_board(config: CalibrationConfig, output_path: str = "charuco_board.png",
                           dpi: int = 300, paper_size: str = "A4"):
    """
    生成 ChArUco 标定板图像

    Args:
        config: 标定配置对象
        output_path: 输出文件路径
        dpi: 打印分辨率（DPI）
        paper_size: 纸张尺寸（"A4" 或 "A3"）
    """
    print("\n" + "="*60)
    print("ChArUco 标定板生成器")
    print("="*60)

    # 获取标定板对象
    board = config.get_charuco_board()

    # 计算图像尺寸（像素）
    if paper_size == "A4":
        # A4: 210mm x 297mm
        width_mm, height_mm = 210, 297
    elif paper_size == "A3":
        # A3: 297mm x 420mm
        width_mm, height_mm = 297, 420
    else:
        raise ValueError(f"不支持的纸张尺寸: {paper_size}")

    # 转换为像素（1 英寸 = 25.4mm）
    width_px = int(width_mm / 25.4 * dpi)
    height_px = int(height_mm / 25.4 * dpi)

    print(f"\n标定板参数:")
    print(f"  - 字典类型: {config.aruco_dict_type}")
    print(f"  - 尺寸: {config.charuco_board_cols} x {config.charuco_board_rows}")
    print(f"  - 方格边长: {config.square_size * 1000:.1f} mm")
    print(f"  - 二维码边长: {config.marker_size * 1000:.1f} mm")
    print(f"\n图像参数:")
    print(f"  - 纸张尺寸: {paper_size} ({width_mm}mm x {height_mm}mm)")
    print(f"  - 分辨率: {dpi} DPI")
    print(f"  - 图像尺寸: {width_px} x {height_px} 像素")

    # 生成标定板图像
    print(f"\n正在生成标定板图像...")
    img = board.generateImage((width_px, height_px), marginSize=50, borderBits=1)

    # 保存图像
    output_path = Path(output_path)
    cv2.imwrite(str(output_path), img)
    print(f"✓ 标定板图像已保存到: {output_path}")

    # 显示预览
    print(f"\n正在显示预览（按任意键关闭）...")
    preview = cv2.resize(img, (800, int(800 * height_px / width_px)))
    cv2.imshow("ChArUco Board Preview", preview)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # 打印说明
    print(f"\n" + "="*60)
    print("打印说明:")
    print("="*60)
    print(f"1. 使用高质量打印机打印 {output_path}")
    print(f"2. 打印设置:")
    print(f"   - 纸张: {paper_size}")
    print(f"   - 质量: 最高质量")
    print(f"   - 缩放: 100%（不要缩放！）")
    print(f"3. 将打印好的标定板粘贴到平整的硬质板上")
    print(f"4. 使用卡尺精确测量以下参数:")
    print(f"   - 方格边长（应为 {config.square_size * 1000:.1f} mm）")
    print(f"   - 二维码边长（应为 {config.marker_size * 1000:.1f} mm）")
    print(f"5. 在 config.py 中填写实际测量值")
    print("="*60 + "\n")


def main():
    """
    主函数
    """
    # 加载配置
    config = CalibrationConfig()

    # 生成标定板
    generate_charuco_board(
        config,
        output_path="charuco_board_A4.png",
        dpi=300,
        paper_size="A4"
    )

    # 可选：生成 A3 尺寸
    # generate_charuco_board(
    #     config,
    #     output_path="charuco_board_A3.png",
    #     dpi=300,
    #     paper_size="A3"
    # )


if __name__ == "__main__":
    main()