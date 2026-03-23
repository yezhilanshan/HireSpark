#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
官方示例改造 - 验证 TTS API 是否真的可用
"""
import os
import dashscope

# 设置 API Key
dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('BAILIAN_API_KEY')

if not dashscope.api_key:
    print("❌ 错误：未配置 DASHSCOPE_API_KEY 或 BAILIAN_API_KEY")
    exit(1)

print(f"✓ API Key 已配置")

# 方法1: 尝试官方 v3-flash 模型（最小参数）
print("\n=== 测试1: cosyvoice-v3-flash（官方示例模型）===")
try:
    from dashscope import SpeechSynthesizer
    
    response = SpeechSynthesizer.call(
        model='cosyvoice-v3-flash',
        text='你好，这是一个测试。',
        voice='longanyang'
    )
    
    print(f"响应类型: {type(response)}")
    print(f"响应对象: {response}")
    print(f"状态码: {getattr(response, 'status_code', 'N/A')}")
    print(f"消息: {getattr(response, 'message', 'N/A')}")
    
    if hasattr(response, 'get_audio_data'):
        audio = response.get_audio_data()
        print(f"音频数据获取: {type(audio)}, 大小: {len(audio) if audio else 0} bytes")
        if audio:
            print("✓ TEST 1 成功: 获取到音频数据")
            # 保存音频到文件用于验证
            with open('test_output_v3flash.wav', 'wb') as f:
                f.write(audio)
            print("  已保存到 test_output_v3flash.wav")
        else:
            print("❌ TEST 1 失败: 返回空音频数据")
    else:
        print("❌ TEST 1 失败: response 没有 get_audio_data 方法")
        
except Exception as e:
    print(f"❌ TEST 1 异常: {e}")
    import traceback
    traceback.print_exc()

# 方法2: 尝试 v1 模型（你配置中使用的）
print("\n=== 测试2: cosyvoice-v1（项目配置模型）===")
try:
    from dashscope import SpeechSynthesizer
    
    response = SpeechSynthesizer.call(
        model='cosyvoice-v1',
        text='你好，这是测试二。',
        voice='longanyang'
    )
    
    print(f"响应类型: {type(response)}")
    print(f"状态码: {getattr(response, 'status_code', 'N/A')}")
    print(f"消息: {getattr(response, 'message', 'N/A')}")
    
    if hasattr(response, 'get_audio_data'):
        audio = response.get_audio_data()
        print(f"音频数据获取: {type(audio)}, 大小: {len(audio) if audio else 0} bytes")
        if audio:
            print("✓ TEST 2 成功: 获取到音频数据")
            with open('test_output_v1.wav', 'wb') as f:
                f.write(audio)
            print("  已保存到 test_output_v1.wav")
        else:
            print("❌ TEST 2 失败: 返回空音频数据")
    else:
        print("❌ TEST 2 失败: response 没有 get_audio_data 方法")
        
except Exception as e:
    print(f"❌ TEST 2 异常: {e}")
    import traceback
    traceback.print_exc()

print("\n=== 诊断完成 ===")
print("如果两个都失败，说明 API Key 或账号配置有问题")
print("如果某个成功，说明该模型可用，项目应该改到那个模型")
