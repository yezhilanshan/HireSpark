from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class EmotionType(Enum):
    NEUTRAL = "neutral"
    HAPPINESS = "happiness"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    DISGUST = "disgust"
    SURPRISE = "surprise"
    CONTEMPT = "contempt"


class AUCode(Enum):
    AU1 = "AU1"   # 眉内侧上扬
    AU2 = "AU2"   # 眉外侧上扬
    AU4 = "AU4"   # 眉下降/皱眉
    AU5 = "AU5"   # 上眼睑上扬
    AU6 = "AU6"   # 脸颊上扬
    AU7 = "AU7"   # 眼睑紧绷
    AU9 = "AU9"   # 鼻唇沟上扬
    AU10 = "AU10" # 上唇上扬
    AU12 = "AU12" # 嘴角上扬 (微笑)
    AU15 = "AU15" # 嘴角下降
    AU17 = "AU17" # 下唇下降
    AU20 = "AU20" # 嘴角水平拉伸
    AU23 = "AU23" # 嘴唇收紧
    AU24 = "AU24" # 嘴唇摩擦/抿嘴
    AU25 = "AU25" # 嘴唇分开
    AU26 = "AU26" # 下巴下垂


@dataclass
class ActionUnitIntensity:
    au_code: AUCode
    intensity: float
    present: bool


@dataclass
class ExpressionResult:
    timestamp: int
    primary_emotion: EmotionType
    emotion_scores: Dict[EmotionType, float]
    action_units: List[ActionUnitIntensity]
    is_micro_expression: bool
    micro_expression_type: Optional[EmotionType] = None
    confidence: float = 0.0


@dataclass
class TemporalExpressionFeature:
    timestamps: List[int]
    au_intensities: Dict[AUCode, List[float]]
    emotion_scores: Dict[EmotionType, List[float]]

    def add_frame(self, timestamp: int, result: ExpressionResult):
        self.timestamps.append(timestamp)
        for au in result.action_units:
            if au.au_code not in self.au_intensities:
                self.au_intensities[au.au_code] = []
            self.au_intensities[au.au_code].append(au.intensity)

        for emotion, score in result.emotion_scores.items():
            if emotion not in self.emotion_scores:
                self.emotion_scores[emotion] = []
            self.emotion_scores[emotion].append(score)


@dataclass
class MicroExpressionDetection:
    detected: bool
    start_time: Optional[int] = None
    peak_time: Optional[int] = None
    duration: int = 0
    expression_type: Optional[EmotionType] = None
    intensity: float = 0.0
    au_sequence: List[AUCode] = field(default_factory=list)