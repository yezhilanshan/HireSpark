"""
数据管理模块 - 内存中管理面试数据
"""
import time
from typing import Dict, List
from datetime import datetime


class DataManager:
    """
    数据管理器 - 在内存中存储面试数据
    """
    
    def __init__(self):
        """初始化数据管理器"""
        self.interview_data = {
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'frames_processed': 0,
            'timeline': [],  # 时间轴数据
            'events': [],    # 异常事件列表
            'statistics': {  # 统计数据
                'max_probability': 0,
                'avg_probability': 0,
                'total_deviations': 0,
                'total_mouth_open': 0,
                'multi_person_detected': False,
                'off_screen_ratio': 0
            }
        }
        
        self.probability_history = []  # 概率历史记录
        
    def start_interview(self):
        """开始面试记录"""
        self.interview_data['start_time'] = datetime.now()
        print(f"Interview started at {self.interview_data['start_time']}")
        
    def end_interview(self):
        """结束面试记录"""
        self.interview_data['end_time'] = datetime.now()
        if self.interview_data['start_time']:
            duration = self.interview_data['end_time'] - self.interview_data['start_time']
            self.interview_data['duration'] = duration.total_seconds()
        
        # 计算统计数据
        self._calculate_statistics()
        
        print(f"Interview ended at {self.interview_data['end_time']}")
        print(f"Duration: {self.interview_data['duration']:.2f} seconds")
        
    def add_frame_data(self, data: Dict):
        """
        添加帧数据到时间轴
        
        Args:
            data: 包含检测结果的字典
        """
        self.interview_data['frames_processed'] += 1
        
        # 添加时间戳
        data['timestamp'] = time.time()
        data['frame_number'] = self.interview_data['frames_processed']
        
        # 添加到时间轴
        self.interview_data['timeline'].append(data)
        
        # 记录概率
        if 'probability' in data:
            self.probability_history.append(data['probability'])
        
    def add_event(self, event: Dict):
        """
        添加异常事件
        
        Args:
            event: 事件字典
        """
        event['timestamp'] = time.time()
        event['datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.interview_data['events'].append(event)
        
    def _calculate_statistics(self):
        """计算统计数据"""
        if len(self.probability_history) > 0:
            self.interview_data['statistics']['max_probability'] = max(self.probability_history)
            self.interview_data['statistics']['avg_probability'] = sum(self.probability_history) / len(self.probability_history)
        
        # 统计事件数量
        for event in self.interview_data['events']:
            if event['type'] == 'gaze_deviation':
                self.interview_data['statistics']['total_deviations'] += 1
            elif event['type'] == 'mouth_open':
                self.interview_data['statistics']['total_mouth_open'] += 1
            elif event['type'] == 'multi_person':
                self.interview_data['statistics']['multi_person_detected'] = True
        
        # 计算屏幕外时间占比
        if len(self.interview_data['timeline']) > 0:
            deviated_frames = sum(1 for frame in self.interview_data['timeline'] 
                                if frame.get('gaze_deviated', False))
            self.interview_data['statistics']['off_screen_ratio'] = \
                (deviated_frames / len(self.interview_data['timeline'])) * 100
        
    def get_interview_data(self) -> Dict:
        """
        获取完整的面试数据
        
        Returns:
            Dict: 面试数据
        """
        return self.interview_data
    
    def get_summary(self) -> Dict:
        """
        获取面试摘要（用于报告生成）
        
        Returns:
            Dict: 面试摘要
        """
        return {
            'start_time': self.interview_data['start_time'],
            'end_time': self.interview_data['end_time'],
            'duration': self.interview_data['duration'],
            'frames_processed': self.interview_data['frames_processed'],
            'total_events': len(self.interview_data['events']),
            'statistics': self.interview_data['statistics']
        }
    
    def get_probability_timeline(self) -> List[float]:
        """
        获取概率时间轴
        
        Returns:
            List[float]: 概率列表
        """
        return self.probability_history
    
    def get_events(self) -> List[Dict]:
        """
        获取所有事件
        
        Returns:
            List[Dict]: 事件列表
        """
        return self.interview_data['events']
    
    def reset(self):
        """重置数据管理器"""
        self.interview_data = {
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'frames_processed': 0,
            'timeline': [],
            'events': [],
            'statistics': {
                'max_probability': 0,
                'avg_probability': 0,
                'total_deviations': 0,
                'total_mouth_open': 0,
                'multi_person_detected': False,
                'off_screen_ratio': 0
            }
        }
        self.probability_history = []
        
    def export_for_report(self) -> Dict:
        """
        导出用于报告生成的数据
        
        Returns:
            Dict: 格式化的报告数据
        """
        summary = self.get_summary()
        
        # 格式化时间
        if summary['start_time']:
            summary['start_time_str'] = summary['start_time'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            summary['start_time_str'] = 'N/A'
            
        if summary['end_time']:
            summary['end_time_str'] = summary['end_time'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            summary['end_time_str'] = 'N/A'
        
        # 格式化持续时间
        if summary['duration'] > 0:
            minutes = int(summary['duration'] // 60)
            seconds = int(summary['duration'] % 60)
            summary['duration_str'] = f"{minutes}分{seconds}秒"
        else:
            summary['duration_str'] = '0秒'
        
        return {
            'summary': summary,
            'events': self.interview_data['events'],
            'probability_timeline': self.probability_history,
            'statistics': self.interview_data['statistics']
        }
