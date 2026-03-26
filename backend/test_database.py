"""
数据库功能测试脚本
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from datetime import datetime
import time


def test_database():
    """测试数据库功能"""
    print("=" * 60)
    print("数据库管理器功能测试")
    print("=" * 60)
    
    # 创建测试数据库
    print("\n1. 创建数据库实例...")
    db = DatabaseManager('test_interview_system.db')
    
    # 测试保存面试记录
    print("\n2. 测试保存面试记录...")
    test_interview = {
        'interview_id': f'test_{int(time.time())}',
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'duration': 300,
        'max_probability': 65.5,
        'avg_probability': 32.8,
        'risk_level': 'MEDIUM',
        'events_count': 5,
        'report_path': f'reports/test_{int(time.time())}.pdf'
    }
    
    result = db.save_interview(test_interview)
    print(f"   结果: {result}")
    assert result['success'], "保存面试记录失败"
    
    interview_id = result['interview_id']
    
    # 测试保存事件
    print("\n3. 测试保存事件记录...")
    test_events = [
        {
            'type': 'gaze_deviation',
            'timestamp': time.time(),
            'score': 30,
            'description': '眼神向左偏离',
            'direction': 'Left'
        },
        {
            'type': 'mouth_open',
            'timestamp': time.time() + 5,
            'score': 20,
            'description': '嘴部张开'
        },
        {
            'type': 'multi_person',
            'timestamp': time.time() + 10,
            'score': 50,
            'description': '检测到多人',
            'num_faces': 2
        }
    ]
    
    result = db.save_events(interview_id, test_events)
    print(f"   结果: {result}")
    assert result['success'], "保存事件记录失败"
    
    # 测试保存统计数据
    print("\n4. 测试保存统计数据...")
    test_stats = {
        'total_deviations': 3,
        'total_mouth_open': 2,
        'total_multi_person': 1,
        'off_screen_ratio': 15.5,
        'frames_processed': 6000
    }
    
    result = db.save_statistics(interview_id, test_stats)
    print(f"   结果: {result}")
    assert result['success'], "保存统计数据失败"
    
    # 测试查询面试记录
    print("\n5. 测试查询面试记录...")
    interviews = db.get_interviews(limit=10)
    print(f"   查询到 {len(interviews)} 条面试记录")
    assert len(interviews) > 0, "查询面试记录失败"
    
    # 测试查询面试详情
    print("\n6. 测试查询面试详情...")
    interview = db.get_interview_by_id(interview_id)
    print(f"   面试ID: {interview['interview_id']}")
    print(f"   风险等级: {interview['risk_level']}")
    print(f"   最大概率: {interview['max_probability']}")
    assert interview is not None, "查询面试详情失败"
    
    # 测试查询事件记录
    print("\n7. 测试查询事件记录...")
    events = db.get_events(interview_id)
    print(f"   查询到 {len(events)} 条事件记录")
    for event in events:
        print(f"   - {event['event_type']}: {event['description']}")
    assert len(events) == len(test_events), "事件数量不匹配"
    
    # 测试筛选特定类型事件
    print("\n8. 测试筛选特定类型事件...")
    gaze_events = db.get_events(interview_id, event_type='gaze_deviation')
    print(f"   查询到 {len(gaze_events)} 条眼神偏离事件")
    assert len(gaze_events) > 0, "筛选事件失败"
    
    # 测试统计摘要
    print("\n9. 测试统计摘要...")
    summary = db.get_statistics_summary()
    print(f"   总面试数: {summary['total_interviews']}")
    print(f"   平均最大概率: {summary['avg_max_probability']}")
    print(f"   总事件数: {summary['total_events']}")
    print(f"   平均时长: {summary['avg_duration']}秒")
    
    # 测试风险等级分布
    print("\n10. 测试风险等级分布...")
    risk_dist = db.get_risk_level_distribution()
    print(f"   LOW: {risk_dist['LOW']}")
    print(f"   MEDIUM: {risk_dist['MEDIUM']}")
    print(f"   HIGH: {risk_dist['HIGH']}")
    
    # 测试事件类型分布
    print("\n11. 测试事件类型分布...")
    event_dist = db.get_event_type_distribution()
    for event_type, count in event_dist.items():
        print(f"   {event_type}: {count}")
    
    # 测试删除面试记录
    print("\n12. 测试删除面试记录...")
    result = db.delete_interview(interview_id)
    print(f"   结果: {result}")
    assert result['success'], "删除面试记录失败"
    
    # 验证已删除
    interview = db.get_interview_by_id(interview_id)
    assert interview is None, "面试记录未被删除"
    print(f"   ✓ 面试记录已成功删除")
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！")
    print("=" * 60)


if __name__ == '__main__':
    try:
        test_database()
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
