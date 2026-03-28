"""
Face Detection Module Usage Example
人脸检测模块使用示例
"""

import cv2
import time

from face_detect.face_analyzer import FaceAnalyzer
from face_detect.eyes_track import GazeTracker, GazeDirection
from face_detect.micro_expression import ExpressionAnalyzer, EmotionType


def example_combined():
    print("=" * 50)
    print("Combined Face Analyzer Example")
    print("=" * 50)

    analyzer = FaceAnalyzer()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return

    print("Press 'q' to quit, 's' to print statistics")

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        timestamp = int(time.time() * 1000)

        result = analyzer.analyze(frame, timestamp)

        if result:
            frame = analyzer.draw_debug_visualization(frame, result)

            eye_state = result['eye_state']
            expression = result['expression']

            if eye_state:
                print(f"\rGaze: L={eye_state.left_gaze.value:10s} R={eye_state.right_gaze.value:10s} | "
                      f"EAR: {eye_state.left_ear:.2f}/{eye_state.right_ear:.2f}", end='')

        cv2.imshow("Face Analyzer", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            summary = analyzer.get_summary()
            print("\n" + "=" * 50)
            print("Summary Statistics:")
            print(f"  Total Frames: {summary['total_frames']}")
            print(f"  Blink Count: {summary['gaze_statistics']['blink_count']}")
            print(f"  Micro-expression Detected: {summary['micro_expression_detected']}")
            print("=" * 50)

    cap.release()
    cv2.destroyAllWindows()


def example_gaze_only():
    print("=" * 50)
    print("Gaze Tracker Only Example")
    print("=" * 50)

    gaze_tracker = GazeTracker()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return

    print("Press 'q' to quit")

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        timestamp = int(time.time() * 1000)

        eye_state = gaze_tracker.detect(frame, timestamp)

        if eye_state:
            h, w, _ = frame.shape

            left_gaze_text = f"Left: {eye_state.left_gaze.value}"
            right_gaze_text = f"Right: {eye_state.right_gaze.value}"
            ear_text = f"EAR: L={eye_state.left_ear:.2f} R={eye_state.right_ear:.2f}"

            cv2.putText(frame, left_gaze_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, right_gaze_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, ear_text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if eye_state.blink_state.value != 'open':
                cv2.putText(frame, f"Blink: {eye_state.blink_state.value}",
                           (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Gaze Tracker", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    stats = gaze_tracker.get_statistics()
    print("\n" + "=" * 50)
    print("Statistics:")
    print(f"  Total Frames: {stats['total_frames']}")
    print(f"  Blink Count: {stats['blink_count']}")
    print("=" * 50)


def example_expression_only():
    print("=" * 50)
    print("Expression Analyzer Only Example")
    print("=" * 50)

    expression_analyzer = ExpressionAnalyzer()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return

    print("Press 'q' to quit")

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        timestamp = int(time.time() * 1000)

        expr_result = expression_analyzer.analyze(frame, timestamp)

        if expr_result:
            h, w, _ = frame.shape

            emotion_text = f"Emotion: {expr_result.primary_emotion.value} ({expr_result.confidence:.2f})"
            cv2.putText(frame, emotion_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

            y_offset = 60
            for emotion, score in sorted(expr_result.emotion_scores.items(),
                                         key=lambda x: x[1], reverse=True)[:3]:
                if score > 0.1:
                    score_text = f"  {emotion.value}: {score:.2f}"
                    cv2.putText(frame, score_text, (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 0), 1)
                    y_offset += 25

            if expr_result.is_micro_expression:
                micro_text = f"Micro-Expression: {expr_result.micro_expression_type.value if expr_result.micro_expression_type else 'N/A'}"
                cv2.putText(frame, micro_text, (10, y_offset + 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Expression Analyzer", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    stats = expression_analyzer.get_statistics()
    print("\n" + "=" * 50)
    print("Statistics:")
    print(f"  Total Frames: {stats['total_frames']}")
    print(f"  Average Emotions: {stats['average_emotions']}")
    print("=" * 50)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "combined":
            example_combined()
        elif mode == "gaze":
            example_gaze_only()
        elif mode == "expression":
            example_expression_only()
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python example.py [combined|gaze|expression]")
    else:
        example_combined()