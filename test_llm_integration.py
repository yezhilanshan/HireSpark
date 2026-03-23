#!/usr/bin/env python
"""
LLM 集成测试脚本
用于验证阿里通义 Qwen 大模型功能
"""

import os
import sys
import time
from pathlib import Path
from dashscope import Generation

# 添加后端路径
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from utils.config_loader import config
from utils.logger import get_logger
from utils.llm_manager import llm_manager

logger = get_logger(__name__)


def _extract_request_id(response):
    """兼容不同 SDK 版本的 request_id 字段。"""
    return (
        getattr(response, 'request_id', None)
        or getattr(response, 'requestId', None)
        or getattr(response, 'id', None)
    )


def _is_generation_call_mocked() -> bool:
    """粗略检测 Generation.call 是否被 mock/替换。"""
    module_name = getattr(Generation.call, '__module__', '') or ''
    return 'dashscope' not in module_name


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_llm_enabled():
    """测试 LLM 是否启用"""
    print_header("测试 1: LLM 状态检查")
    
    if llm_manager.check_enabled():
        print("✅ LLM 已启用")
        print(f"   提供商: {llm_manager.provider}")
        print(f"   模型: {llm_manager.model}")
        return True
    else:
        print("❌ LLM 未启用或 API Key 未配置")
        print("   请设置环境变量: BAILIAN_API_KEY")
        return False


def test_direct_dashscope_call():
    """直接调用 DashScope，验证真实在线请求。"""
    print_header("测试 2: 直连 DashScope 烟雾测试")

    if _is_generation_call_mocked():
        print("❌ Generation.call 似乎被 mock，非真实在线调用")
        return False

    if not llm_manager.check_enabled():
        print("⏭️  跳过 - LLM 未启用")
        return False

    try:
        start = time.perf_counter()
        response = Generation.call(
            model=llm_manager.model,
            messages=[
                {"role": "system", "content": "你是一个简洁助手"},
                {"role": "user", "content": "只回复OK"}
            ],
            temperature=0,
            max_tokens=8,
            timeout=llm_manager.timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        status_code = getattr(response, 'status_code', None)
        request_id = _extract_request_id(response)
        text = getattr(getattr(response, 'output', None), 'text', '') or ''

        print(f"✅ 状态码: {status_code}")
        print(f"✅ 请求ID: {request_id}")
        print(f"✅ 耗时: {latency_ms:.2f} ms")
        print(f"✅ 返回文本: {text}")

        if status_code == 200 and text.strip():
            return True

        print("❌ 直连调用未返回有效结果")
        return False
    except Exception as e:
        print(f"❌ 直连调用失败: {e}")
        return False


def test_generate_question():
    """测试生成面试问题"""
    print_header("测试 3: 生成面试问题")
    
    if not llm_manager.check_enabled():
        print("⏭️  跳过 - LLM 未启用")
        return False
    
    try:
        print("🔄 正在生成 Java 后端工程师面试问题...")
        question = llm_manager.generate_interview_question(
            position="Java后端工程师",
            difficulty="medium",
            context="候选人有 5 年以上工作经验"
        )
        
        if question:
            print(f"✅ 成功生成：\n   {question}")
            return True
        else:
            print("❌ 生成失败")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_process_answer():
    """测试处理用户回答"""
    print_header("测试 4: 处理用户回答")
    
    if not llm_manager.check_enabled():
        print("⏭️  跳过 - LLM 未启用")
        return False
    
    try:
        question = "请解释一下 Java 中的多线程概念"
        answer = "多线程是指在一个程序中同时进行多个执行流，可以提高程序性能和响应性。" \
                "在 Java 中可以通过 Thread 类或 Runnable 接口实现。"
        
        print(f"❓ 问题: {question}")
        print(f"💬 用户回答: {answer}")
        print("\n🔄 正在生成面试官反馈...")
        
        feedback = llm_manager.process_answer(
            user_answer=answer,
            current_question=question,
            position="Java后端工程师",
            chat_history=[]
        )
        
        if feedback:
            print(f"✅ 收到反馈：\n   {feedback}")
            return True
        else:
            print("❌ 生成反馈失败")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_evaluate_answer():
    """测试评估用户回答"""
    print_header("测试 5: 评估用户回答")
    
    if not llm_manager.check_enabled():
        print("⏭️  跳过 - LLM 未启用")
        return False
    
    try:
        question = "什么是 Spring Boot 的自动配置原理?"
        answer = "Spring Boot 通过 @SpringBootApplication 注解和自动配置类来实现。" \
                "它会根据 classpath 上的 jar 包进行智能配置。"
        
        print(f"❓ 问题: {question}")
        print(f"💬 用户回答: {answer}")
        print("\n🔄 正在评估回答质量...")
        
        evaluation = llm_manager.evaluate_answer(
            user_answer=answer,
            question=question,
            position="Java后端工程师"
        )
        
        if evaluation.get('score'):
            print(f"✅ 评估完成:")
            print(f"   ⭐ 分数: {evaluation.get('score')}/10")
            if 'feedback' in evaluation:
                print(f"   📝 反馈: {evaluation.get('feedback')}")
            if 'strengths' in evaluation:
                print(f"   ✅ 优点: {evaluation.get('strengths')}")
            if 'weaknesses' in evaluation:
                print(f"   ⚠️  缺点: {evaluation.get('weaknesses')}")
            return True
        else:
            print(f"❌ 评估失败: {evaluation.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_configuration():
    """测试配置加载"""
    print_header("测试 1: 配置检查")
    
    try:
        llm_enabled = config.get('llm.enabled')
        llm_provider = config.get('llm.provider')
        llm_model = config.get('llm.model')
        
        print(f"✅ 配置已加载:")
        print(f"   LLM 启用: {llm_enabled}")
        print(f"   提供商: {llm_provider}")
        print(f"   模型: {llm_model}")
        
        # 检查 API Key
        api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('BAILIAN_API_KEY')
        if api_key:
            masked_key = api_key[:10] + '*' * (len(api_key) - 20) + api_key[-10:]
            print(f"   API Key: {masked_key}")
        else:
            print(f"   ⚠️  API Key 未设置")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "🧪 LLM 集成测试套件".center(60))
    print("🎯 目标: 验证阿里通义 Qwen 大模型集成功能")
    print("⏰ 时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    
    results = []
    
    # 运行测试
    results.append(("配置检查", test_configuration()))
    results.append(("LLM 状态", test_llm_enabled()))
    results.append(("直连 DashScope", test_direct_dashscope_call()))
    
    if llm_manager.check_enabled():
        results.append(("生成问题", test_generate_question()))
        results.append(("处理回答", test_process_answer()))
        results.append(("评估回答", test_evaluate_answer()))
    
    # 打印总结
    print_header("测试总结")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败/跳过"
        print(f"{status:10} - {test_name}")
    
    print(f"\n总体: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试都通过了！系统准备就绪。")
        return True
    else:
        print("\n⚠️  某些测试未通过，请检查配置。")
        return False


if __name__ == '__main__':
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⛔ 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
