import cv2
import numpy as np
from typing import Optional, Dict, Any
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .eyes_track import GazeTracker, EyeState, GazeDirection
from .micro_expression import (
    ExpressionAnalyzer, ExpressionResult,
    EmotionType, MicroExpressionDetection
)


class FaceAnalyzer:
    def __init__(
        self,
        model_path: str = "frontend/public/face_landmarker.task"
    ):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)

        self.gaze_tracker = GazeTracker(model_path=model_path)
        self.expression_analyzer = ExpressionAnalyzer(model_path=model_path)

        self.frame_count = 0
        self.results_buffer: Dict[int, Dict[str, Any]] = {}

    def analyze(
        self,
        image: np.ndarray,
        timestamp: int = 0
    ) -> Optional[Dict[str, Any]]:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = vision.Image(image_format=vision.ImageFormat.SRGB, data=rgb_image)
        result = self.detector.detect_for_video(mp_image, timestamp)

        if not result.face_landmarks:
            return None

        eye_state = self.gaze_tracker.detect(image, timestamp)
        expression_result = self.expression_analyzer.analyze(image, timestamp)

        head_pose = self._estimate_head_pose(result.face_landmarks[0], image.shape)

        combined_result = {
            'timestamp': timestamp,
            'frame_count': self.frame_count,
            'face_detected': True,
            'eye_state': eye_state,
            'expression': expression_result,
            'head_pose': head_pose,
            'landmarks': result.face_landmarks[0],
            'blendshapes': result.face_blendshapes[0] if result.face_blendshapes else None,
            'transformation_matrix': (
                result.facial_transformation_matrixes[0].data if
                result.facial_transformation_matrixes else None
            )
        }

        self.results_buffer[timestamp] = combined_result
        self.frame_count += 1

        return combined_result

    def _estimate_head_pose(
        self,
        landmarks,
        image_shape
    ) -> Optional[Dict[str, float]]:
        if len(landmarks) < 468:
            return None

        h, w, _ = image_shape

        nose_tip = landmarks[1]
        chin = landmarks[152]
        left_eye = landmarks[33]
        right_eye = landmarks[263]
        left_ear = landmarks[234]
        right_ear = landmarks[454]

        nose_2d = np.array([nose_tip.x * w, nose_tip.y * h])
        nose_3d = np.array([nose_tip.x * w, nose_tip.y * h, nose_tip.z * 3000])

        eye_left_2d = np.array([left_eye.x * w, left_eye.y * h])
        eye_right_2d = np.array([right_eye.x * w, right_eye.y * h])

        eye_center = (eye_left_2d + eye_right_2d) / 2

        cam_matrix = np.array([
            [w, 0, w / 2],
            [0, h, h / 2],
            [0, 0, 1]
        ], dtype=np.float64)

        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        face_3d = []
        face_2d = []
        face_points = [
            (33, 0), (263, 0), (1, 0), (61, 0), (291, 0),
            (199, 0), (152, 0)
        ]

        for idx, _ in face_points:
            lm = landmarks[idx]
            face_2d.append([lm.x * w, lm.y * h])
            face_3d.append([lm.x * w, lm.y * h, lm.z * 3000])

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        try:
            success, rot_vec, trans_vec = cv2.solvePnP(
                face_3d, face_2d, cam_matrix, dist_matrix
            )

            if success:
                rmat, _ = cv2.Rodrigues(rot_vec)
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

                return {
                    'pitch': float(angles[0] * 180 / np.pi),
                    'yaw': float(angles[1] * 180 / np.pi),
                    'roll': float(angles[2] * 180 / np.pi)
                }
        except:
            pass

        return None

    def get_summary(self) -> Dict[str, Any]:
        gaze_stats = self.gaze_tracker.get_statistics()
        expr_stats = self.expression_analyzer.get_statistics()

        micro_expr_detected = self.expression_analyzer.detect_micro_expression_sequence()

        return {
            'total_frames': self.frame_count,
            'gaze_statistics': gaze_stats,
            'expression_statistics': expr_stats,
            'micro_expression_detected': (
                micro_expr_detected.detected if micro_expr_detected else False
            ),
            'micro_expression_info': micro_expr_detected
        }

    def reset(self):
        self.gaze_tracker.reset()
        self.expression_analyzer.reset()
        self.frame_count = 0
        self.results_buffer.clear()

    def draw_debug_visualization(
        self,
        image: np.ndarray,
        result: Dict[str, Any]
    ) -> np.ndarray:
        if not result or 'landmarks' not in result:
            return image

        h, w, _ = image.shape
        landmarks = result['landmarks']

        for idx in range(len(landmarks)):
            lm = landmarks[idx]
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(image, (x, y), 1, (0, 255, 0), -1)

        eye_state = result.get('eye_state')
        if eye_state:
            left_gaze_text = f"Left: {eye_state.left_gaze.value}"
            right_gaze_text = f"Right: {eye_state.right_gaze.value}"

            cv2.putText(
                image, f"Left Gaze: {eye_state.left_gaze.value}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            cv2.putText(
                image, f"Right Gaze: {eye_state.right_gaze.value}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            cv2.putText(
                image, f"EAR: L={eye_state.left_ear:.2f} R={eye_state.right_ear:.2f}",
                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )

        expression = result.get('expression')
        if expression:
            emotion_text = f"Emotion: {expression.primary_emotion.value} ({expression.confidence:.2f})"
            cv2.putText(
                image, emotion_text,
                (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2
            )

            if expression.is_micro_expression:
                cv2.putText(
                    image, f"MicroExpr: {expression.micro_expression_type.value if expression.micro_expression_type else 'N/A'}",
                    (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

        head_pose = result.get('head_pose')
        if head_pose:
            pose_text = f"Head Pose: P={head_pose['pitch']:.1f} Y={head_pose['yaw']:.1f} R={head_pose['roll']:.1f}"
            cv2.putText(
                image, pose_text,
                (10, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
            )

        return image