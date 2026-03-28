import cv2
import numpy as np
from collections import deque
from typing import Optional, Tuple, List

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .data_types import GazeDirection, EyeState, BlinkState, GazeData


class GazeTracker:
    def __init__(
        self,
        model_path: str = "frontend/public/face_landmarker.task",
        temporal_window_size: int = 5
    ):
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)

        self.LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
        self.RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
        self.LEFT_IRIS_INDICES = [468, 469, 470, 471, 472]
        self.RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]

        self.EAR_THRESHOLD = 0.21
        self.EAR_CLOSED_THRESHOLD = 0.15
        self.GAZE_OFFSET_THRESHOLD = 0.1

        self.temporal_window_size = temporal_window_size
        self.ear_buffer = deque(maxlen=temporal_window_size)
        self.gaze_buffer = deque(maxlen=temporal_window_size)

        self.blink_counter = 0
        self.blink_duration = 0
        self.is_blinking = False
        self.was_blinking = False

        self.frame_count = 0

    def detect(self, image: np.ndarray, timestamp: int) -> Optional[EyeState]:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = vision.Image(image_format=vision.ImageFormat.SRGB, data=rgb_image)
        result = self.detector.detect_for_video(mp_image, timestamp)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]

        left_ear = self._calculate_eye_aspect_ratio(landmarks, self.LEFT_EYE_INDICES)
        right_ear = self._calculate_eye_aspect_ratio(landmarks, self.RIGHT_EYE_INDICES)

        self.ear_buffer.append((left_ear, right_ear))
        smoothed_ear = self._get_smoothed_ear()

        blink_state = self._detect_blink_state(smoothed_ear)

        left_pupil_offset, left_gaze = self._calculate_pupil_position(
            landmarks, self.LEFT_EYE_INDICES, self.LEFT_IRIS_INDICES
        )
        right_pupil_offset, right_gaze = self._calculate_pupil_position(
            landmarks, self.RIGHT_EYE_INDICES, self.RIGHT_IRIS_INDICES
        )

        self.gaze_buffer.append((left_gaze, right_gaze))
        smoothed_left_gaze, smoothed_right_gaze = self._get_smoothed_gaze()

        left_iris_size = self._calculate_iris_size(landmarks, self.LEFT_IRIS_INDICES)
        right_iris_size = self._calculate_iris_size(landmarks, self.RIGHT_IRIS_INDICES)

        self.frame_count += 1

        return EyeState(
            left_ear=left_ear,
            right_ear=right_ear,
            blink_state=blink_state,
            left_gaze= smoothed_left_gaze,
            right_gaze= smoothed_right_gaze,
            left_pupil_offset=left_pupil_offset,
            right_pupil_offset=right_pupil_offset,
            left_iris_size=left_iris_size,
            right_iris_size=right_iris_size
        )

    def _calculate_eye_aspect_ratio(
        self,
        landmarks,
        eye_indices: List[int]
    ) -> float:
        coords = []
        for idx in eye_indices:
            lm = landmarks[idx]
            coords.append((lm.x, lm.y, lm.z))

        v1 = np.linalg.norm(np.array(coords[1]) - np.array(coords[5]))
        v2 = np.linalg.norm(np.array(coords[2]) - np.array(coords[4]))
        h = np.linalg.norm(np.array(coords[0]) - np.array(coords[3]))

        if h == 0:
            return 0.0
        return (v1 + v2) / (2.0 * h)

    def _calculate_pupil_position(
        self,
        landmarks,
        eye_indices: List[int],
        iris_indices: List[int]
    ) -> Tuple[Tuple[float, float], GazeDirection]:
        eye_left = landmarks[eye_indices[0]]
        eye_right = landmarks[eye_indices[3]]
        eye_center = np.array([
            (eye_left.x + eye_right.x) / 2,
            (eye_left.y + eye_right.y) / 2
        ])

        iris_points = []
        for idx in iris_indices:
            lm = landmarks[idx]
            iris_points.append((lm.x, lm.y))
        iris_center = np.mean(iris_points, axis=0)

        eye_width = np.linalg.norm(
            np.array([eye_right.x, eye_right.y]) - np.array([eye_left.x, eye_left.y])
        )

        if eye_width < 1e-6:
            return (0.0, 0.0), GazeDirection.CENTER

        offset = (iris_center - eye_center) / eye_width

        gaze = self._offset_to_gaze_direction(offset)

        return (float(offset[0]), float(offset[1])), gaze

    def _offset_to_gaze_direction(self, offset: np.ndarray) -> GazeDirection:
        x, y = offset[0], offset[1]

        if abs(x) < self.GAZE_OFFSET_THRESHOLD and abs(y) < self.GAZE_OFFSET_THRESHOLD:
            return GazeDirection.CENTER

        if x < -self.GAZE_OFFSET_THRESHOLD:
            if y < -self.GAZE_OFFSET_THRESHOLD:
                return GazeDirection.TOP_LEFT
            elif y > self.GAZE_OFFSET_THRESHOLD:
                return GazeDirection.BOTTOM_LEFT
            else:
                return GazeDirection.LEFT

        if x > self.GAZE_OFFSET_THRESHOLD:
            if y < -self.GAZE_OFFSET_THRESHOLD:
                return GazeDirection.TOP_RIGHT
            elif y > self.GAZE_OFFSET_THRESHOLD:
                return GazeDirection.BOTTOM_RIGHT
            else:
                return GazeDirection.RIGHT

        if y < -self.GAZE_OFFSET_THRESHOLD:
            return GazeDirection.UP
        if y > self.GAZE_OFFSET_THRESHOLD:
            return GazeDirection.DOWN

        return GazeDirection.CENTER

    def _calculate_iris_size(
        self,
        landmarks,
        iris_indices: List[int]
    ) -> float:
        iris_points = []
        for idx in iris_indices:
            lm = landmarks[idx]
            iris_points.append((lm.x, lm.y, lm.z))

        center = np.mean(iris_points, axis=0)
        distances = [
            np.linalg.norm(np.array(p) - center)
            for p in iris_points
        ]
        return float(np.mean(distances))

    def _detect_blink_state(self, avg_ear: float) -> BlinkState:
        if avg_ear >= self.EAR_THRESHOLD:
            if self.is_blinking:
                self.is_blinking = False
                self.blink_counter += 1
            return BlinkState.OPEN
        elif avg_ear <= self.EAR_CLOSED_THRESHOLD:
            if not self.is_blinking:
                self.is_blinking = True
                self.blink_duration = 1
            else:
                self.blink_duration += 1
            return BlinkState.CLOSED
        else:
            if self.is_blinking:
                return BlinkState.CLOSING
            else:
                return BlinkState.OPENING

    def _get_smoothed_ear(self) -> float:
        if not self.ear_buffer:
            return 0.0
        return np.mean([(l + r) / 2 for l, r in self.ear_buffer])

    def _get_smoothed_gaze(self) -> Tuple[GazeDirection, GazeDirection]:
        if not self.gaze_buffer:
            return GazeDirection.CENTER, GazeDirection.CENTER

        left_votes = [g[0] for g in self.gaze_buffer]
        right_votes = [g[1] for g in self.gaze_buffer]

        from collections import Counter
        left_gaze = Counter(left_votes).most_common(1)[0][0]
        right_gaze = Counter(right_votes).most_common(1)[0][0]

        return left_gaze, right_gaze

    def get_gaze_data(self, timestamp: int) -> Optional[GazeData]:
        if not self.gaze_buffer:
            return None

        latest = self.gaze_buffer[-1]
        current_gaze = latest[0]

        recent_ears = list(self.ear_buffer)
        avg_ear = np.mean([(l + r) / 2 for l, r in recent_ears]) if recent_ears else 0.0

        return GazeData(
            timestamp=timestamp,
            gaze_direction=current_gaze,
            pupil_positions=(
                (latest[0].value[0] if hasattr(latest[0], 'value') else 0,
                 latest[0].value[1] if hasattr(latest[0], 'value') else 0),
                (latest[1].value[0] if hasattr(latest[1], 'value') else 0,
                 latest[1].value[1] if hasattr(latest[1], 'value') else 0)
            ) if len(self.gaze_buffer) > 0 else ((0, 0), (0, 0)),
            eye_openness=avg_ear,
            blink_detected=self.blink_counter > 0
        )

    def reset(self):
        self.ear_buffer.clear()
        self.gaze_buffer.clear()
        self.blink_counter = 0
        self.blink_duration = 0
        self.is_blinking = False
        self.was_blinking = False
        self.frame_count = 0

    def get_statistics(self) -> dict:
        return {
            'total_frames': self.frame_count,
            'blink_count': self.blink_counter,
            'average_ear': np.mean([(l + r) / 2 for l, r in self.ear_buffer]) if self.ear_buffer else 0.0
        }