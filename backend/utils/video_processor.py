"""
视频处理模块
"""
import cv2
import numpy as np
import base64
from typing import Tuple, Optional


class VideoProcessor:
    """
    视频帧处理器 - 处理视频帧的编解码
    """
    
    @staticmethod
    def decode_frame(base64_str: str) -> Optional[np.ndarray]:
        """
        将 Base64 编码的图像解码为 OpenCV 帧
        
        Args:
            base64_str: Base64 编码的图像字符串
            
        Returns:
            np.ndarray: OpenCV 图像帧，解码失败返回 None
        """
        try:
            # 移除 data URL 前缀
            if ',' in base64_str:
                base64_str = base64_str.split(',')[1]
            
            # Base64 解码
            img_data = base64.b64decode(base64_str)
            
            # 转换为 numpy 数组
            nparr = np.frombuffer(img_data, np.uint8)
            
            # 解码为图像
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            return frame
        except Exception as e:
            print(f"Frame decode error: {e}")
            return None
    
    @staticmethod
    def encode_frame(frame: np.ndarray, quality: int = 80) -> Optional[str]:
        """
        将 OpenCV 帧编码为 Base64 字符串
        
        Args:
            frame: OpenCV 图像帧
            quality: JPEG 质量 (0-100)
            
        Returns:
            str: Base64 编码的图像字符串，编码失败返回 None
        """
        try:
            # 编码为 JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            # Base64 编码
            base64_str = base64.b64encode(buffer).decode('utf-8')
            
            # 添加 data URL 前缀
            return f"data:image/jpeg;base64,{base64_str}"
        except Exception as e:
            print(f"Frame encode error: {e}")
            return None
    
    @staticmethod
    def resize_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
        """
        调整帧大小
        
        Args:
            frame: 输入帧
            width: 目标宽度
            height: 目标高度
            
        Returns:
            np.ndarray: 调整后的帧
        """
        return cv2.resize(frame, (width, height))
    
    @staticmethod
    def draw_text(frame: np.ndarray, text: str, position: Tuple[int, int], 
                  color: Tuple[int, int, int] = (0, 255, 0), 
                  font_scale: float = 0.7, thickness: int = 2) -> np.ndarray:
        """
        在帧上绘制文本
        
        Args:
            frame: 输入帧
            text: 文本内容
            position: 文本位置 (x, y)
            color: 文本颜色 (B, G, R)
            font_scale: 字体缩放
            thickness: 线条粗细
            
        Returns:
            np.ndarray: 绘制了文本的帧
        """
        cv2.putText(frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 
                   font_scale, color, thickness, cv2.LINE_AA)
        return frame
    
    @staticmethod
    def draw_rectangle(frame: np.ndarray, top_left: Tuple[int, int], 
                      bottom_right: Tuple[int, int], 
                      color: Tuple[int, int, int] = (0, 255, 0), 
                      thickness: int = 2) -> np.ndarray:
        """
        在帧上绘制矩形
        
        Args:
            frame: 输入帧
            top_left: 左上角坐标
            bottom_right: 右下角坐标
            color: 矩形颜色 (B, G, R)
            thickness: 线条粗细
            
        Returns:
            np.ndarray: 绘制了矩形的帧
        """
        cv2.rectangle(frame, top_left, bottom_right, color, thickness)
        return frame
    
    @staticmethod
    def draw_circle(frame: np.ndarray, center: Tuple[int, int], radius: int,
                   color: Tuple[int, int, int] = (0, 255, 0), 
                   thickness: int = -1) -> np.ndarray:
        """
        在帧上绘制圆形
        
        Args:
            frame: 输入帧
            center: 圆心坐标
            radius: 半径
            color: 圆形颜色 (B, G, R)
            thickness: 线条粗细，-1 表示填充
            
        Returns:
            np.ndarray: 绘制了圆形的帧
        """
        cv2.circle(frame, center, radius, color, thickness)
        return frame
