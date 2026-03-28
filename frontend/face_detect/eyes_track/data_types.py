from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional


class GazeDirection(Enum):
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class BlinkState(Enum):
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    OPENING = "opening"


@dataclass
class EyeState:
    left_ear: float
    right_ear: float
    blink_state: BlinkState
    left_gaze: GazeDirection
    right_gaze: GazeDirection
    left_pupil_offset: Tuple[float, float]
    right_pupil_offset: Tuple[float, float]
    left_iris_size: float
    right_iris_size: float


@dataclass
class GazeData:
    timestamp: int
    gaze_direction: GazeDirection
    pupil_positions: Tuple[Tuple[float, float], Tuple[float, float]]
    eye_openness: float
    blink_detected: bool