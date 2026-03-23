#!/usr/bin/env python
"""
AI 面试系统启动助手
一键启动后端、语音识别和前端
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目路径
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / 'backend'
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# 配置
BACKEND_HOST = '0.0.0.0'
BACKEND_PORT = 5000
FRONTEND_PORT = 3000
ASR_BACKEND_URL = f'http://localhost:{BACKEND_PORT}'


def print_header(title):
    """打印标题"""
    print("\n" + "🎬 ".center(60) + title.center(60) + " 🎬".center(60))
    print("=" * 60)


def check_api_key():
    """检查 API Key 配置"""
    api_key = os.environ.get('BAILIAN_API_KEY')
    if not api_key:
        print("⚠️  警告: BAILIAN_API_KEY 未设置")
        print("   请设置环境变量或查看 .env.example")
        return False
    else:
        masked = api_key[:5] + '*' * (len(api_key) - 10) + api_key[-5:]
        print(f"✅ API Key 已配置: {masked}")
        return True


def start_backend():
    """启动后端服务"""
    print_header("启动后端服务")
    
    if not BACKEND_DIR.exists():
        print(f"❌ 后端目录不存在: {BACKEND_DIR}")
        return None
    
    print(f"📁 后端路径: {BACKEND_DIR}")
    print(f"🌐 服务地址: http://{BACKEND_HOST}:{BACKEND_PORT}")
    
    try:
        print("🔄 启动中...")
        # 使用 conda 环境
        cmd = [
            sys.executable,
            str(BACKEND_DIR / 'app.py')
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"✅ 后端已启动 (PID: {process.pid})")
        return process
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return None


def start_asr():
    """启动语音识别"""
    print_header("启动语音识别")
    
    asr_script = PROJECT_ROOT / 'live_asr.py'
    if not asr_script.exists():
        print(f"❌ ASR 脚本不存在: {asr_script}")
        return None
    
    print(f"🎤 ASR 脚本: {asr_script}")
    print(f"🔗 后端地址: {ASR_BACKEND_URL}")
    
    try:
        print("🔄 启动中...")
        env = os.environ.copy()
        env['BACKEND_URL'] = ASR_BACKEND_URL
        
        process = subprocess.Popen(
            [sys.executable, str(asr_script)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        
        print(f"✅ ASR 已启动 (PID: {process.pid})")
        return process
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return None


def start_frontend():
    """启动前端服务"""
    print_header("启动前端服务")
    
    if not FRONTEND_DIR.exists():
        print(f"❌ 前端目录不存在: {FRONTEND_DIR}")
        return None
    
    print(f"📁 前端路径: {FRONTEND_DIR}")
    print(f"🌐 前端地址: http://localhost:{FRONTEND_PORT}")
    
    try:
        # 检查 node_modules
        if not (FRONTEND_DIR / 'node_modules').exists():
            print("📦 node_modules 不存在，正在安装依赖...")
            subprocess.run(['npm', 'install'], cwd=str(FRONTEND_DIR), check=True)
        
        print("🔄 启动中...")
        process = subprocess.Popen(
            ['npm', 'run', 'dev'],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print(f"✅ 前端已启动 (PID: {process.pid})")
        return process
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return None


def run_tests():
    """运行 LLM 集成测试"""
    print_header("运行 LLM 集成测试")
    
    test_script = PROJECT_ROOT / 'test_llm_integration.py'
    if not test_script.exists():
        print(f"⏭️  测试脚本不存在: {test_script}")
        return
    
    try:
        print("🔄 运行测试...")
        subprocess.run(
            [sys.executable, str(test_script)],
            cwd=str(PROJECT_ROOT)
        )
    except Exception as e:
        print(f"❌ 测试失败: {e}")


def show_menu():
    """显示主菜单"""
    print("\n" + "=" * 60)
    print("  AI 面试系统启动菜单".center(60))
    print("=" * 60)
    print("""
1. 启动后端服务
2. 启动语音识别
3. 启动前端（需要 Node.js）
4. 运行全部（后端 + ASR）
5. 运行测试
6. 查看配置
0. 退出
""")


def show_status(backend, asr, frontend):
    """显示进程状态"""
    print("\n" + "-" * 60)
    print(f"后端:     {'✅ 运行中' if backend and backend.poll() is None else '❌ 未运行'}")
    print(f"ASR:      {'✅ 运行中' if asr and asr.poll() is None else '❌ 未运行'}")
    print(f"前端:     {'✅ 运行中' if frontend and frontend.poll() is None else '❌ 未运行'}")
    print("-" * 60)


def interactive_mode():
    """交互模式"""
    backend = None
    asr = None
    frontend = None
    
    print("\n🎯 欢迎使用 AI 模拟面试系统")
    print("版本 2.0.0 | 集成阿里通义 Qwen LLM")
    
    # 检查 API Key
    check_api_key()
    
    running = True
    while running:
        show_menu()
        choice = input("请选择操作 (0-6): ").strip()
        
        if choice == '1':
            if backend is None or backend.poll() is not None:
                backend = start_backend()
                if backend:
                    time.sleep(2)  # 等待后端启动
            else:
                print("⚠️  后端已在运行")
        
        elif choice == '2':
            if not backend or backend.poll() is not None:
                print("⚠️  请先启动后端服务")
            elif asr is None or asr.poll() is not None:
                asr = start_asr()
            else:
                print("⚠️  ASR 已在运行")
        
        elif choice == '3':
            if frontend is None or frontend.poll() is not None:
                frontend = start_frontend()
                if frontend:
                    time.sleep(3)  # 等待前端启动
            else:
                print("⚠️  前端已在运行")
        
        elif choice == '4':
            print("\n🚀 启动后端和 ASR...")
            if backend is None or backend.poll() is not None:
                backend = start_backend()
            time.sleep(2)
            if asr is None or asr.poll() is not None:
                asr = start_asr()
        
        elif choice == '5':
            run_tests()
        
        elif choice == '6':
            print_header("系统配置")
            print(f"项目路径: {PROJECT_ROOT}")
            print(f"后端路径: {BACKEND_DIR}")
            print(f"前端路径: {FRONTEND_DIR}")
            print(f"API Key:  {'✅ 已设置' if os.environ.get('BAILIAN_API_KEY') else '❌ 未设置'}")
            print(f"后端地址: http://{BACKEND_HOST}:{BACKEND_PORT}")
            print(f"前端地址: http://localhost:{FRONTEND_PORT}")
        
        elif choice == '0':
            print("\n🛑 正在关闭所有服务...")
            for proc, name in [(backend, '后端'), (asr, 'ASR'), (frontend, '前端')]:
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                        print(f"✅ {name} 已关闭")
                    except:
                        proc.kill()
                        print(f"⚠️  {name} 被强制关闭")
            running = False
        
        else:
            print("❌ 无效选择")
        
        # 显示状态
        show_status(backend, asr, frontend)
        
        if running:
            input("\n按 Enter 继续...")


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            # 命令行参数模式
            cmd = sys.argv[1]
            if cmd == 'backend':
                start_backend()
            elif cmd == 'asr':
                start_asr()
            elif cmd == 'frontend':
                start_frontend()
            elif cmd == 'test':
                run_tests()
            else:
                print("用法: python start_all.py [backend|asr|frontend|test]")
        else:
            # 交互模式
            interactive_mode()
    
    except KeyboardInterrupt:
        print("\n\n⛔ 程序被中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
