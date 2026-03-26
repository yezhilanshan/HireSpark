import cv2
import mediapipe as mp
import numpy as np
import time
from math import hypot

class LivenessDetector:
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # 定义眼睛和嘴巴的关键点索引
        self.LEFT_EYE = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE = [33, 160, 158, 133, 153, 144]
        self.MOUTH = [78, 81, 13, 311, 308, 402, 14, 178] # 内嘴唇点

        # 阈值设置 (需要根据实际光线微调)
        self.BLINK_THRESHOLD = 0.50  # 眼睛长宽比小于此值认为闭眼
        self.MOUTH_THRESHOLD = 0.40  # 嘴巴长宽比大于此值认为张嘴

        # 状态记录
        self.blink_count = 0
        self.mouth_open_count = 0
        self.is_blinked = False
        self.is_mouth_opened = False
        
        # 活体检测结果
        self.is_real_person = False

    def get_aspect_ratio(self, landmarks, indices, width, height):
        """计算纵横比 (EAR 或 MAR)"""
        # 获取关键点坐标
        coords = []
        for i in indices:
            lm = landmarks[i]
            coords.append((int(lm.x * width), int(lm.y * height)))

        # 计算垂直距离 (通常取两组垂直点的平均值)
        # 对于眼睛：(p2-p6) + (p3-p5)
        # 对于嘴巴：类似逻辑，取上下唇距离
        
        # 这里使用简化的欧氏距离计算
        # 垂直距离 A
        v1 = hypot(coords[1][0] - coords[5][0], coords[1][1] - coords[5][1])
        # 垂直距离 B
        v2 = hypot(coords[2][0] - coords[4][0], coords[2][1] - coords[4][1])
        
        # 水平距离
        h = hypot(coords[0][0] - coords[3][0], coords[0][1] - coords[3][1])

        if h == 0: return 0
        ratio = (v1 + v2) / (2.0 * h)
        return ratio

    def run(self):
        cap = cv2.VideoCapture(0)
        
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("无法读取摄像头")
                break

            # 镜像翻转，体验更好
            image = cv2.flip(image, 1)
            h, w, c = image.shape
            
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(image_rgb)

            status_text = "Please perform actions..."
            color = (0, 255, 255) # 黄色

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    lm = face_landmarks.landmark
                    
                    # 1. 计算左眼 EAR
                    left_ear = self.get_aspect_ratio(lm, self.LEFT_EYE, w, h)
                    # 2. 计算右眼 EAR
                    right_ear = self.get_aspect_ratio(lm, self.RIGHT_EYE, w, h)
                    # 取平均值
                    avg_ear = (left_ear + right_ear) / 2.0

                    # 3. 计算嘴巴 MAR
                    # 嘴巴关键点逻辑稍有不同，这里取简化的上下唇距离/嘴角距离
                    # 使用内嘴唇索引重新计算
                    mouth_top = lm[13]
                    mouth_bottom = lm[14]
                    mouth_left = lm[78]
                    mouth_right = lm[308]
                    
                    mouth_h = hypot(mouth_top.x*w - mouth_bottom.x*w, mouth_top.y*h - mouth_bottom.y*h)
                    mouth_w = hypot(mouth_left.x*w - mouth_right.x*w, mouth_left.y*h - mouth_right.y*h)
                    
                    if mouth_w == 0: mar = 0
                    else: mar = mouth_h / mouth_w

                    # --- 逻辑判定区 ---
                    
                    # 判定眨眼
                    # 注意：mediapipe 的 EAR 算法在闭眼时数值变小 (通常 < 0.2 或 0.25，但我放宽到0.3以便容易触发)
                    # 之前的 0.5 可能太大，这里调整更精确的阈值
                    if avg_ear < 0.25: 
                        self.is_blinked = True
                    
                    # 判定张嘴
                    if mar > 0.5: # 嘴巴张开高度超过宽度的 50%
                        self.is_mouth_opened = True

                    # UI 显示当前数值 (调试用)
                    cv2.putText(image, f"Eye Ratio: {avg_ear:.2f}", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
                    cv2.putText(image, f"Mouth Ratio: {mar:.2f}", (20, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

                    # 判定活体成功：既检测到了眨眼，也检测到了张嘴（不需要同时）
                    if self.is_blinked and self.is_mouth_opened:
                        self.is_real_person = True
                        status_text = "REAL PERSON VERIFIED!"
                        color = (0, 255, 0) # 绿色
                    else:
                        # 显示当前还需要做什么
                        req = []
                        if not self.is_blinked: req.append("Blink Eyes")
                        if not self.is_mouth_opened: req.append("Open Mouth")
                        status_text = "Action Required: " + " & ".join(req)
                        color = (0, 0, 255) # 红色

            # 绘制 UI
            cv2.rectangle(image, (0, 0), (w, 60), (50, 50, 50), -1)
            cv2.putText(image, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            cv2.imshow('Liveness Detection (No Files Needed)', image)

            if cv2.waitKey(5) & 0xFF == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detector = LivenessDetector()
    detector.run()