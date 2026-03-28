import cv2
import numpy as np
from collections import deque, Counter
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .emotion_types import (
    EmotionType, AUCode, ExpressionResult,
    ActionUnitIntensity, TemporalExpressionFeature,
    MicroExpressionDetection
)


class ExpressionAnalyzer:
    def __init__(
        self,
        model_path: str = "frontend/public/face_landmarker.task",
        temporal_window: int = 15,
        micro_expression_threshold: float = 0.3,
        micro_expression_duration_max: int = 10
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

        self.MOUTH_INDICES = [61, 291, 78, 308, 13, 14, 178, 402]
        self.EYEBROW_LEFT = [336, 296, 334, 293, 300]
        self.EYEBROW_RIGHT = [107, 66, 70, 63, 105]
        self.NOSE = [1, 2, 98, 168, 195, 197]
        self.FOREHEAD = [10, 151]
        self.CHEEK_LEFT = [234]
        self.CHEEK_RIGHT = [454]

        self.MAR_THRESHOLD = 0.5
        self.SMILE_THRESHOLD = 0.3
        self.AU_INTENSITY_THRESHOLD = 0.2

        self.temporal_window = temporal_window
        self.micro_expression_threshold = micro_expression_threshold
        self.micro_expression_duration_max = micro_expression_duration_max

        self.expression_history: deque = deque(maxlen=temporal_window)
        self.au_history: deque = deque(maxlen=temporal_window)
        self.emotion_history: deque = deque(maxlen=temporal_window)

        self.micro_expression_candidates: deque = deque(maxlen=50)
        self.frame_count = 0

        self._blendshape_to_au_map = {
            'browDownLeft': AUCode.AU4,
            'browDownRight': AUCode.AU4,
            'browInnerUp': AUCode.AU1,
            'eyeLookUpLeft': AUCode.AU5,
            'eyeLookUpRight': AUCode.AU5,
            'eyeLookDownLeft': AUCode.AU5,
            'eyeLookDownRight': AUCode.AU5,
            'cheekPuff': AUCode.AU6,
            'cheekSquintLeft': AUCode.AU6,
            'cheekSquintRight': AUCode.AU6,
            'eyeSquintLeft': AUCode.AU6,
            'eyeSquintRight': AUCode.AU6,
            'noseSneerLeft': AUCode.AU9,
            'noseSneerRight': AUCode.AU9,
            'mouthDimpleLeft': AUCode.AU12,
            'mouthDimpleRight': AUCode.AU12,
            'mouthFrownLeft': AUCode.AU15,
            'mouthFrownRight': AUCode.AU15,
            'mouthLeft': AUCode.AU12,
            'mouthRight': AUCode.AU12,
            'mouthSmileLeft': AUCode.AU12,
            'mouthSmileRight': AUCode.AU12,
            'mouthPressLeft': AUCode.AU24,
            'mouthPressRight': AUCode.AU24,
            'mouthUpperUpLeft': AUCode.AU10,
            'mouthUpperUpRight': AUCode.AU10,
            'mouthLowerDownLeft': AUCode.AU17,
            'mouthLowerDownRight': AUCode.AU17,
            'jawOpen': AUCode.AU26,
            'jawForward': AUCode.AU26,
        }

    def analyze(self, image: np.ndarray, timestamp: int) -> Optional[ExpressionResult]:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = vision.Image(image_format=vision.ImageFormat.SRGB, data=rgb_image)
        result = self.detector.detect_for_video(mp_image, timestamp)

        if not result.face_landmarks:
            return None

        landmarks = result.face_landmarks[0]
        blendshapes = result.face_blendshapes[0] if result.face_blendshapes else []

        action_units = self._extract_action_units(blendshapes, landmarks)

        self.au_history.append(action_units)

        emotion_scores = self._calculate_emotion_scores(action_units)
        self.emotion_history.append(emotion_scores)

        primary_emotion = self._get_primary_emotion(emotion_scores)

        smoothed_emotions = self._smooth_emotions()
        smoothed_primary = self._get_primary_emotion(smoothed_emotions)

        is_micro_expr, micro_type = self._detect_micro_expression(
            emotion_scores, primary_emotion
        )

        confidence = max(emotion_scores.values()) if emotion_scores else 0.0

        expression_result = ExpressionResult(
            timestamp=timestamp,
            primary_emotion=smoothed_primary,
            emotion_scores=smoothed_emotions,
            action_units=action_units,
            is_micro_expression=is_micro_expr,
            micro_expression_type=micro_type if is_micro_expr else None,
            confidence=confidence
        )

        self.expression_history.append(expression_result)
        self.frame_count += 1

        return expression_result

    def _extract_action_units(
        self,
        blendshapes,
        landmarks
    ) -> List[ActionUnitIntensity]:
        au_intensities = []

        for blend in blendshapes:
            category_name = blend.category_name
            score = blend.score

            if category_name in self._blendshape_to_au_map:
                au_code = self._blendshape_to_au_map[category_name]
                au_intensities.append(ActionUnitIntensity(
                    au_code=au_code,
                    intensity=score,
                    present=score > self.AU_INTENSITY_THRESHOLD
                ))

        mouth_aspect_ratio = self._calculate_mar(landmarks)
        if mouth_aspect_ratio > self.MAR_THRESHOLD:
            au_intensities.append(ActionUnitIntensity(
                au_code=AUCode.AU25,
                intensity=mouth_aspect_ratio,
                present=True
            ))
        if mouth_aspect_ratio > 0.8:
            au_intensities.append(ActionUnitIntensity(
                au_code=AUCode.AU26,
                intensity=mouth_aspect_ratio,
                present=True
            ))

        smile_score = self._calculate_smile_score(landmarks)
        if smile_score > self.SMILE_THRESHOLD:
            au_intensities.append(ActionUnitIntensity(
                au_code=AUCode.AU12,
                intensity=smile_score,
                present=True
            ))

        return au_intensities

    def _calculate_mar(self, landmarks) -> float:
        mouth_top = landmarks[13]
        mouth_bottom = landmarks[14]
        mouth_left = landmarks[61]
        mouth_right = landmarks[291]

        vertical = np.sqrt(
            (mouth_top.x - mouth_bottom.x) ** 2 +
            (mouth_top.y - mouth_bottom.y) ** 2
        )
        horizontal = np.sqrt(
            (mouth_left.x - mouth_right.x) ** 2 +
            (mouth_left.y - mouth_right.y) ** 2
        )

        return vertical / horizontal if horizontal > 0 else 0.0

    def _calculate_smile_score(self, landmarks) -> float:
        mouth_left = landmarks[61]
        mouth_right = landmarks[291]
        cheek_left = landmarks[234]
        cheek_right = landmarks[454]

        mouth_width = np.sqrt(
            (mouth_right.x - mouth_left.x) ** 2 +
            (mouth_right.y - mouth_left.y) ** 2
        )
        cheek_distance_left = np.sqrt(
            (mouth_left.x - cheek_left.x) ** 2 +
            (mouth_left.y - cheek_left.y) ** 2
        )
        cheek_distance_right = np.sqrt(
            (mouth_right.x - cheek_right.x) ** 2 +
            (mouth_right.y - cheek_right.y) ** 2
        )

        avg_cheek_distance = (cheek_distance_left + cheek_distance_right) / 2

        return mouth_width / (avg_cheek_distance + 1e-6)

    def _calculate_emotion_scores(
        self,
        action_units: List[ActionUnitIntensity]
    ) -> Dict[EmotionType, float]:
        au_dict = {au.au_code: au.intensity for au in action_units}

        scores = {
            EmotionType.HAPPINESS: self._calc_happiness_score(au_dict),
            EmotionType.SADNESS: self._calc_sadness_score(au_dict),
            EmotionType.ANGER: self._calc_anger_score(au_dict),
            EmotionType.FEAR: self._calc_fear_score(au_dict),
            EmotionType.DISGUST: self._calc_disgust_score(au_dict),
            EmotionType.SURPRISE: self._calc_surprise_score(au_dict),
            EmotionType.CONTEMPT: self._calc_contempt_score(au_dict),
            EmotionType.NEUTRAL: 0.0
        }

        max_score = max(scores.values()) if scores else 1.0
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}

        scores[EmotionType.NEUTRAL] = 1.0 - max(scores.values()) if scores else 0.0

        return scores

    def _calc_happiness_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU12 in au_dict:
            score += au_dict[AUCode.AU12] * 0.6
        if AUCode.AU6 in au_dict:
            score += au_dict[AUCode.AU6] * 0.3
        if AUCode.AU25 in au_dict:
            score += au_dict[AUCode.AU25] * 0.1
        return min(score, 1.0)

    def _calc_sadness_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU1 in au_dict:
            score += au_dict[AUCode.AU1] * 0.4
        if AUCode.AU4 in au_dict:
            score += au_dict[AUCode.AU4] * 0.4
        if AUCode.AU17 in au_dict:
            score += au_dict[AUCode.AU17] * 0.2
        return min(score, 1.0)

    def _calc_anger_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU4 in au_dict:
            score += au_dict[AUCode.AU4] * 0.6
        if AUCode.AU9 in au_dict:
            score += au_dict[AUCode.AU9] * 0.2
        if AUCode.AU10 in au_dict:
            score += au_dict[AUCode.AU10] * 0.2
        return min(score, 1.0)

    def _calc_fear_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU1 in au_dict:
            score += au_dict[AUCode.AU1] * 0.3
        if AUCode.AU2 in au_dict:
            score += au_dict[AUCode.AU2] * 0.3
        if AUCode.AU4 in au_dict:
            score += au_dict[AUCode.AU4] * 0.2
        if AUCode.AU5 in au_dict:
            score += au_dict[AUCode.AU5] * 0.2
        return min(score, 1.0)

    def _calc_disgust_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU9 in au_dict:
            score += au_dict[AUCode.AU9] * 0.5
        if AUCode.AU10 in au_dict:
            score += au_dict[AUCode.AU10] * 0.3
        if AUCode.AU17 in au_dict:
            score += au_dict[AUCode.AU17] * 0.2
        return min(score, 1.0)

    def _calc_surprise_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU1 in au_dict:
            score += au_dict[AUCode.AU1] * 0.25
        if AUCode.AU2 in au_dict:
            score += au_dict[AUCode.AU2] * 0.25
        if AUCode.AU5 in au_dict:
            score += au_dict[AUCode.AU5] * 0.25
        if AUCode.AU26 in au_dict:
            score += au_dict[AUCode.AU26] * 0.25
        return min(score, 1.0)

    def _calc_contempt_score(self, au_dict: Dict[AUCode, float]) -> float:
        score = 0.0
        if AUCode.AU12 in au_dict:
            score += au_dict[AUCode.AU12] * 0.5
        if AUCode.AU15 in au_dict:
            score += au_dict[AUCode.AU15] * 0.3
        if AUCode.AU24 in au_dict:
            score += au_dict[AUCode.AU24] * 0.2
        return min(score, 1.0)

    def _smooth_emotions(self) -> Dict[EmotionType, float]:
        if not self.emotion_history:
            return {e: 0.0 for e in EmotionType}

        smoothed = {}
        for emotion in EmotionType:
            values = [
                h.get(emotion, 0.0)
                for h in self.emotion_history
            ]
            smoothed[emotion] = np.mean(values)
        return smoothed

    def _get_primary_emotion(
        self,
        emotion_scores: Dict[EmotionType, float]
    ) -> EmotionType:
        if not emotion_scores:
            return EmotionType.NEUTRAL

        primary = max(emotion_scores.items(), key=lambda x: x[1])
        if primary[1] < 0.2:
            return EmotionType.NEUTRAL
        return primary[0]

    def _detect_micro_expression(
        self,
        current_scores: Dict[EmotionType, float],
        current_emotion: EmotionType
    ) -> Tuple[bool, Optional[EmotionType]]:
        if len(self.emotion_history) < 5:
            return False, None

        recent_scores = list(self.emotion_history)

        if len(recent_scores) >= 5:
            older_avg = np.mean([
                scores.get(current_emotion, 0.0)
                for scores in recent_scores[:-2]
            ])
            recent_max = max([
                scores.get(current_emotion, 0.0)
                for scores in recent_scores[-3:]
            ])

            if (recent_max - older_avg) > self.micro_expression_threshold:
                if older_avg < 0.15 and recent_max > 0.35:
                    return True, current_emotion

        return False, None

    def detect_micro_expression_sequence(
        self,
        duration_frames: int = 10
    ) -> Optional[MicroExpressionDetection]:
        if len(self.expression_history) < duration_frames:
            return None

        recent = list(self.expression_history)[-duration_frames:]

        emotions = [r.primary_emotion for r in recent]
        emotion_changes = []

        for i in range(1, len(emotions)):
            if emotions[i] != emotions[i-1]:
                emotion_changes.append({
                    'frame': i,
                    'from': emotions[i-1],
                    'to': emotions[i],
                    'intensity': recent[i].emotion_scores.get(emotions[i], 0.0)
                })

        if len(emotion_changes) >= 2:
            first_change = emotion_changes[0]
            peak_change = max(emotion_changes, key=lambda x: x['intensity'])

            if (peak_change['frame'] - first_change['frame']) <= duration_frames:
                return MicroExpressionDetection(
                    detected=True,
                    start_time=recent[first_change['frame']].timestamp,
                    peak_time=recent[peak_change['frame']].timestamp,
                    duration=peak_change['frame'] - first_change['frame'],
                    expression_type=peak_change['to'],
                    intensity=peak_change['intensity']
                )

        return None

    def get_temporal_features(self) -> TemporalExpressionFeature:
        feature = TemporalExpressionFeature(
            timestamps=[],
            au_intensities={},
            emotion_scores={}
        )

        for expr in self.expression_history:
            feature.add_frame(expr.timestamp, expr)

        return feature

    def reset(self):
        self.expression_history.clear()
        self.au_history.clear()
        self.emotion_history.clear()
        self.micro_expression_candidates.clear()
        self.frame_count = 0

    def get_statistics(self) -> dict:
        return {
            'total_frames': self.frame_count,
            'history_size': len(self.expression_history),
            'average_emotions': self._smooth_emotions() if self.emotion_history else {}
        }