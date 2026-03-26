import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque

class InterviewAntiCheating:
    def __init__(self):
        # 1. 初始化 MediaPipe
        self.mp_face_mesh = mp.solutions.face_mesh # type: ignore
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            refine_landmarks=True
        )
        self.mp_drawing = mp.solutions.drawing_utils # type: ignore
        
        # 数据平滑缓冲
        self.pitch_buffer = deque(maxlen=10)
        self.yaw_buffer = deque(maxlen=10)
        
        # --- 阈值设置 (根据实际情况微调) ---
        # 1. 角度阈值
        self.YAW_THRESHOLD = 25       # 左右转头 (度)
        self.PITCH_UP_THRESHOLD = 15  # 抬头 (度) -> 这里的数越小，判定抬头越灵敏
        self.PITCH_DOWN_THRESHOLD = -20 # 低头 (度)

        # 2. 位置偏移阈值 (像素占比)
        # 允许人脸中心偏离画面中心的比例 (0.2 表示允许偏离 20% 的宽高)
        self.OFFSET_THRESHOLD_X = 0.25 
        self.OFFSET_THRESHOLD_Y = 0.25 

        self.window_name = 'Interview Anti-Cheating System'

    def get_head_pose(self, image, landmarks):
        img_h, img_w, img_c = image.shape
        face_3d = []
        face_2d = []

        # 关键点：鼻尖(1), 下巴(152), 左眼角(33), 右眼角(266), 左嘴角(61), 右嘴角(291)
        key_points = [1, 152, 33, 266, 61, 291]

        for idx, lm in enumerate(landmarks.landmark):
            if idx in key_points:
                if idx == 1:
                    nose_2d = (lm.x * img_w, lm.y * img_h)
                    nose_3d = (lm.x * img_w, lm.y * img_h, lm.z * 3000)

                x, y = int(lm.x * img_w), int(lm.y * img_h)
                face_2d.append([x, y])
                face_3d.append([x, y, lm.z])

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        focal_length = 1 * img_w
        cam_matrix = np.array([[focal_length, 0, img_h / 2],
                               [0, focal_length, img_w / 2],
                               [0, 0, 1]])
        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
        rmat, jac = cv2.Rodrigues(rot_vec)
        angles, mtxR, mtxQ, Qx, Qy, Qz = cv2.RQDecomp3x3(rmat)

        x = angles[0] * 360 # Pitch
        y = angles[1] * 360 # Yaw
        z = angles[2] * 360 # Roll

        return x, y, z, nose_2d

    def check_position(self, nose_point, img_w, img_h):
        """
        检测人脸位置是否偏离中心
        """
        center_x, center_y = img_w // 2, img_h // 2
        nose_x, nose_y = nose_point[0], nose_point[1]

        # 计算偏移量 (绝对值)
        offset_x = abs(nose_x - center_x)
        offset_y = abs(nose_y - center_y)

        # 计算最大允许偏移像素
        max_off_x = img_w * self.OFFSET_THRESHOLD_X
        max_off_y = img_h * self.OFFSET_THRESHOLD_Y

        is_centered = True
        msg = ""

        if offset_x > max_off_x:
            is_centered = False
            msg = "Position: Too Far Side!"
        elif offset_y > max_off_y:
            is_centered = False
            msg = "Position: Too High/Low!"
            
        return is_centered, msg, (int(center_x - max_off_x), int(center_y - max_off_y), int(center_x + max_off_x), int(center_y + max_off_y))

    def run(self):
        cap = cv2.VideoCapture(0)
        cv2.namedWindow(self.window_name)

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("无法获取摄像头画面")
                continue

            # 镜像翻转，让用户看屏幕像照镜子，体验更好
            image = cv2.flip(image, 1)

            image.flags.writeable = False
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(image_rgb)

            image.flags.writeable = True
            image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

            img_h, img_w, _ = image.shape
            
            status_text = "Status: Normal"
            color = (0, 255, 0) # 绿色

            if not results.multi_face_landmarks:
                status_text = "WARNING: No Face!"
                color = (0, 0, 255)
                self.pitch_buffer.clear()
                self.yaw_buffer.clear()
            elif len(results.multi_face_landmarks) > 1:
                status_text = "WARNING: Multiple Faces!"
                color = (0, 0, 255)
            else:
                for face_landmarks in results.multi_face_landmarks:
                    pitch_raw, yaw_raw, roll, nose_point = self.get_head_pose(image, face_landmarks)
                    
                    # 平滑数据
                    self.pitch_buffer.append(pitch_raw)
                    self.yaw_buffer.append(yaw_raw)
                    pitch = sum(self.pitch_buffer) / len(self.pitch_buffer)
                    yaw = sum(self.yaw_buffer) / len(self.yaw_buffer)

                    # 1. 先检测位置偏移 (Position Check)
                    is_centered, pos_msg, box_coords = self.check_position(nose_point, img_w, img_h)
                    
                    # 画出“安全区”方框
                    cv2.rectangle(image, (box_coords[0], box_coords[1]), (box_coords[2], box_coords[3]), (255, 255, 0), 1)

                    if not is_centered:
                        status_text = f"WARNING: {pos_msg}"
                        color = (0, 0, 255)
                    else:
                        # 2. 如果位置正常，再检测头部姿态 (Pose Check)
                        if yaw < -self.YAW_THRESHOLD:
                            # 镜像后，yaw方向反转：原图负数是左，镜像后负数看起来是向右
                            # 为了逻辑通顺，镜像模式下：
                            # 脸朝画面右侧(真实左侧) -> 负数
                            status_text = "Looking Right (Side)" 
                            color = (0, 165, 255)
                        elif yaw > self.YAW_THRESHOLD:
                            status_text = "Looking Left (Side)"
                            color = (0, 165, 255)
                        elif pitch < self.PITCH_DOWN_THRESHOLD:
                            status_text = "Looking Down (Cheat?)"
                            color = (0, 0, 255)
                        elif pitch > self.PITCH_UP_THRESHOLD:
                            # 增加抬头检测
                            status_text = "Looking Up (Cheat?)" 
                            color = (0, 0, 255)

                    # 绘制方向线
                    nose_x, nose_y = int(nose_point[0]), int(nose_point[1])
                    # 镜像后，yaw 的可视化方向也要反转
                    p2 = (int(nose_x - yaw * 10), int(nose_y - pitch * 10))
                    cv2.line(image, (nose_x, nose_y), p2, (255, 0, 0), 3)
                    cv2.circle(image, (nose_x, nose_y), 5, color, -1)

                    # Debug 信息
                    cv2.putText(image, f"Pitch: {int(pitch)}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)
                    cv2.putText(image, f"Yaw: {int(yaw)}", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)

            cv2.putText(image, status_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.imshow(self.window_name, image)

            # 关闭逻辑
            key = cv2.waitKey(5) & 0xFF
            if key == 27:
                break
            try:
                if cv2.getWindowProperty(self.window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except Exception:
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    system = InterviewAntiCheating()
    system.run()