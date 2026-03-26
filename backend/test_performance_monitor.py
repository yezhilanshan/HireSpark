"""
性能监控系统测试
"""
import sys
import os
import time

# 确保能导入 backend 模块
sys.path.insert(0, os.path.dirname(__file__))

from utils.performance_monitor import (
    performance_monitor, 
    measure_time, 
    PerformanceContext,
    get_stats,
    get_summary
)


def test_fps_tracking():
    """测试 FPS 追踪"""
    print("\n" + "="*60)
    print("FPS 追踪测试")
    print("="*60)
    
    # 重置统计
    performance_monitor.reset_stats()
    
    # 模拟 30 FPS 的帧处理
    print("\n模拟 30 FPS 帧处理...")
    for i in range(60):
        time.sleep(0.033)  # ~30 FPS
        performance_monitor.record_frame(0.025)
    
    fps = performance_monitor.get_fps()
    avg_time = performance_monitor.get_avg_processing_time()
    
    print(f"✓ 记录了 {performance_monitor.frame_count} 帧")
    print(f"✓ 当前 FPS: {fps}")
    print(f"✓ 平均处理时间: {avg_time}ms")
    
    # 验证（放宽范围，因为 sleep 时间不精确）
    assert 15 <= fps <= 35, f"FPS 超出预期范围: {fps}"
    assert 20 <= avg_time <= 30, f"处理时间超出预期: {avg_time}ms"
    
    print("✓ FPS 追踪测试通过")
    return True


def test_system_resources():
    """测试系统资源监控"""
    print("\n" + "="*60)
    print("系统资源监控测试")
    print("="*60)
    
    # 强制更新系统资源
    performance_monitor._update_system_resources()
    time.sleep(0.1)  # 等待更新
    
    stats = get_stats()
    
    print(f"CPU 使用率: {stats['cpu_percent']}%")
    print(f"内存使用: {stats['memory_percent']}% ({stats['memory_used_mb']}MB)")
    
    # 验证
    assert 0 <= stats['cpu_percent'] <= 100, "CPU 百分比超出范围"
    assert 0 <= stats['memory_percent'] <= 100, "内存百分比超出范围"
    assert stats['memory_used_mb'] >= 0, "内存使用量无效"
    
    print("✓ 系统资源监控测试通过")
    return True


def test_function_timing_decorator():
    """测试函数执行时间装饰器"""
    print("\n" + "="*60)
    print("函数执行时间测量测试")
    print("="*60)
    
    # 重置统计
    performance_monitor.function_stats.clear()
    
    @measure_time()
    def slow_function():
        """慢函数"""
        time.sleep(0.1)
        return "完成"
    
    @measure_time("fast_operation")
    def fast_function():
        """快函数"""
        time.sleep(0.01)
        return "完成"
    
    # 执行多次
    print("\n执行测试函数...")
    for _ in range(5):
        slow_function()
        fast_function()
    
    # 获取统计
    summary = get_summary()
    
    if 'function_stats' in summary:
        print("\n函数执行统计:")
        for func_name, stats in summary['function_stats'].items():
            print(f"  {func_name}:")
            print(f"    平均: {stats['avg_time_ms']}ms")
            print(f"    最小: {stats['min_time_ms']}ms")
            print(f"    最大: {stats['max_time_ms']}ms")
            print(f"    调用次数: {stats['count']}")
        
        # 验证
        assert len(summary['function_stats']) >= 2, "应该有至少2个函数统计"
        
        print("\n✓ 函数执行时间测量测试通过")
        return True
    else:
        print("✗ 未收集到函数统计数据")
        return False


def test_context_manager():
    """测试上下文管理器"""
    print("\n" + "="*60)
    print("上下文管理器测试")
    print("="*60)
    
    # 清空统计
    performance_monitor.function_stats.clear()
    
    print("\n使用上下文管理器测量操作...")
    
    # 测试 1
    with PerformanceContext("operation_1"):
        time.sleep(0.05)
    
    # 测试 2
    with PerformanceContext("operation_2"):
        time.sleep(0.03)
    
    # 检查统计
    assert "operation_1" in performance_monitor.function_stats
    assert "operation_2" in performance_monitor.function_stats
    
    stats = performance_monitor.function_stats
    print(f"\n✓ operation_1: {stats['operation_1']['total_time']*1000:.2f}ms")
    print(f"✓ operation_2: {stats['operation_2']['total_time']*1000:.2f}ms")
    
    print("✓ 上下文管理器测试通过")
    return True


def test_bottleneck_detection():
    """测试性能瓶颈识别"""
    print("\n" + "="*60)
    print("性能瓶颈识别测试")
    print("="*60)
    
    # 清空统计
    performance_monitor.function_stats.clear()
    
    # 创建一些有明显性能差异的函数
    @measure_time()
    def very_slow():
        time.sleep(0.15)
    
    @measure_time()
    def moderate():
        time.sleep(0.06)
    
    @measure_time()
    def fast():
        time.sleep(0.01)
    
    print("\n执行不同速度的函数...")
    for _ in range(3):
        very_slow()
        moderate()
        fast()
    
    # 识别瓶颈 (>50ms)
    bottlenecks = performance_monitor.get_bottlenecks(threshold_ms=50.0)
    
    print(f"\n识别到 {len(bottlenecks)} 个性能瓶颈 (>50ms):")
    for bottleneck in bottlenecks:
        print(f"  {bottleneck['function']}: {bottleneck['avg_time_ms']}ms ({bottleneck['count']} 次调用)")
    
    # 验证
    assert len(bottlenecks) >= 2, "应该识别出至少2个瓶颈"
    assert bottlenecks[0]['avg_time_ms'] > bottlenecks[-1]['avg_time_ms'], "瓶颈应按耗时降序排列"
    
    print("\n✓ 性能瓶颈识别测试通过")
    return True


def test_monitoring_thread():
    """测试后台监控线程"""
    print("\n" + "="*60)
    print("后台监控线程测试")
    print("="*60)
    
    print("\n启动监控线程...")
    performance_monitor.start_monitoring()
    
    # 等待几秒让线程运行
    print("运行 3 秒...")
    time.sleep(3)
    
    # 检查系统资源是否有更新
    stats = get_stats()
    assert stats['cpu_percent'] >= 0, "CPU 监控应该正常工作"
    
    print("\n停止监控线程...")
    performance_monitor.stop_monitoring()
    
    print("✓ 后台监控线程测试通过")
    return True


def test_integration():
    """集成测试 - 模拟真实使用场景"""
    print("\n" + "="*60)
    print("集成测试 - 模拟视频处理")
    print("="*60)
    
    # 重置统计
    performance_monitor.reset_stats()
    performance_monitor.start_monitoring()
    
    @measure_time("video_decode")
    def decode_frame():
        time.sleep(0.005)  # 5ms 解码
    
    @measure_time("face_detection")
    def detect_face():
        time.sleep(0.015)  # 15ms 人脸检测
    
    @measure_time("gaze_tracking")
    def track_gaze():
        time.sleep(0.010)  # 10ms 眼神追踪
    
    print("\n模拟处理 30 帧视频...")
    for i in range(30):
        frame_start = time.time()
        
        # 模拟视频处理流程
        decode_frame()
        detect_face()
        track_gaze()
        
        # 记录帧
        frame_time = time.time() - frame_start
        performance_monitor.record_frame(frame_time)
        
        time.sleep(0.003)  # 其他开销
    
    # 等待一下让监控线程更新
    time.sleep(1)
    
    # 获取完整摘要
    summary = get_summary()
    
    print("\n" + "="*60)
    print("性能摘要")
    print("="*60)
    print(f"FPS: {summary['fps']}")
    print(f"平均处理时间: {summary['avg_processing_time_ms']}ms")
    print(f"CPU: {summary['cpu_percent']}%")
    print(f"内存: {summary['memory_percent']}% ({summary['memory_used_mb']}MB)")
    print(f"已处理帧数: {summary['frame_count']}")
    
    if 'function_stats' in summary:
        print("\n各阶段耗时:")
        for func_name, stats in summary['function_stats'].items():
            print(f"  {func_name}: {stats['avg_time_ms']}ms (x{stats['count']})")
    
    # 停止监控
    performance_monitor.stop_monitoring()
    
    # 验证
    assert summary['frame_count'] == 30, "应该处理了30帧"
    assert summary['fps'] > 0, "FPS 应该大于0"
    
    print("\n✓ 集成测试通过")
    return True


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("性能监控系统完整测试")
    print("="*60)
    
    results = []
    
    # 运行所有测试
    try:
        results.append(("FPS 追踪", test_fps_tracking()))
        results.append(("系统资源监控", test_system_resources()))
        results.append(("函数执行时间测量", test_function_timing_decorator()))
        results.append(("上下文管理器", test_context_manager()))
        results.append(("性能瓶颈识别", test_bottleneck_detection()))
        results.append(("后台监控线程", test_monitoring_thread()))
        results.append(("集成测试", test_integration()))
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status} - {name}")
    
    all_passed = all(result[1] for result in results)
    
    print("="*60)
    if all_passed:
        print("✓ 所有测试通过！")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


if __name__ == '__main__':
    exit(main())
