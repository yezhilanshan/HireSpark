import os
import signal  # for keyboard events handling (press "Ctrl+C" to terminate recording)
import sys
import asyncio
import queue
import tempfile
import threading
import time
import uuid
import importlib.util

import dashscope
import pyaudio
from dashscope.audio.asr import *
import socketio

TTS_AVAILABLE = (
    importlib.util.find_spec('edge_tts') is not None
    and importlib.util.find_spec('playsound') is not None
)

# Socket.IO 客户端配置
BACKEND_URL = os.environ.get('BACKEND_URL', 'http://localhost:5000')
sio = socketio.Client()

# 全局变量
mic = None
stream = None
recognition = None
interview_session_id = None
current_question = None
chat_history = []
is_tts_playing = False
tts_queue = queue.Queue()
tts_thread = None
stop_tts_worker = False

TTS_VOICE = os.environ.get('EDGE_TTS_VOICE', 'zh-CN-XiaoxiaoNeural')
TTS_RATE = os.environ.get('EDGE_TTS_RATE', '+0%')
TTS_VOLUME = os.environ.get('EDGE_TTS_VOLUME', '+0%')
TTS_CONNECT_TIMEOUT_SEC = float(os.environ.get('EDGE_TTS_TIMEOUT_SEC', '8'))

# Set recording parameters
sample_rate = 16000  # sampling rate (Hz)
channels = 1  # mono channel
dtype = 'int16'  # data type
format_pcm = 'pcm'  # the format of the audio data
block_size = 3200  # number of frames per buffer

# DashScope ASR 模型配置。可通过环境变量 ASR_MODEL 指定，默认优先 v2。
ASR_MODEL = os.environ.get('ASR_MODEL', 'fun-asr-realtime')
ASR_MODEL_FALLBACKS = [
    ASR_MODEL,
    'paraformer-v1',
]


def init_dashscope_api_key():
    """初始化阿里 DashScope API Key"""
    api_key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('BAILIAN_API_KEY')
    if api_key:
        dashscope.api_key = api_key
    else:
        print('Error: Please set DASHSCOPE_API_KEY (or BAILIAN_API_KEY) in environment variables.')


async def _synthesize_to_file(text: str, output_path: str):
    """将文本合成为语音文件。"""
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=TTS_VOICE,
        rate=TTS_RATE,
        volume=TTS_VOLUME,
    )
    await asyncio.wait_for(communicate.save(output_path), timeout=TTS_CONNECT_TIMEOUT_SEC)


def _tts_worker():
    """串行播报队列中的面试官语音，避免多段语音重叠。"""
    global is_tts_playing

    while True:
        text = tts_queue.get()
        try:
            if text is None:
                break

            if not TTS_AVAILABLE:
                print('⚠️  未安装 edge-tts/playsound，跳过语音播报')
                continue

            cleaned = (text or '').strip()
            if not cleaned:
                continue

            is_tts_playing = True
            filename = f"interviewer_{uuid.uuid4().hex}.mp3"
            file_path = os.path.join(tempfile.gettempdir(), filename)

            asyncio.run(_synthesize_to_file(cleaned, file_path))
            from playsound import playsound
            playsound(file_path)

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

        except Exception as e:
            print(f'⚠️  语音播报失败: {e}')
        finally:
            is_tts_playing = False


def start_tts_worker():
    """启动 TTS 播报线程。"""
    global tts_thread
    if tts_thread is None or not tts_thread.is_alive():
        tts_thread = threading.Thread(target=_tts_worker, daemon=True)
        tts_thread.start()


def speak_interviewer_text(text: str):
    """将面试官文本加入语音播报队列。"""
    if text:
        tts_queue.put(text)


def stop_tts():
    """停止 TTS 播报线程。"""
    try:
        tts_queue.put(None)
    except Exception:
        pass


# ==================== Socket.IO 事件处理 ====================

@sio.event
def connect():
    """连接到后端成功"""
    global interview_session_id
    print('✅ 已连接到后端服务器')
    print(f'   连接 ID: {sio.sid}')
    interview_session_id = sio.sid


@sio.event
def disconnect():
    """断开连接"""
    print('❌ 已断开连接')


@sio.on('llm_response')
def on_llm_response(data):
    """接收 LLM 的追问回应"""
    if data.get('success'):
        feedback = data.get('feedback', '')
        print(f'\n👤 面试官反馈: {feedback}')
        speak_interviewer_text(feedback)
        print('\n🎤 请继续回答或等待下一个问题...\n')
    else:
        print(f'❌ 错误: {data.get("error")}')


@sio.on('llm_question')
def on_llm_question(data):
    """接收 LLM 生成的新问题"""
    global current_question
    if data.get('success'):
        current_question = data.get('question')
        position = data.get('position', '')
        difficulty = data.get('difficulty', '')
        print(f'\n📝 【{difficulty} 难度】{position}')
        print(f'❓ {current_question}')
        speak_interviewer_text(current_question)
        print('🎤 请开始回答...\n')
    else:
        print(f'❌ 错误: {data.get("error")}')


@sio.on('llm_evaluation')
def on_llm_evaluation(data):
    """接收 LLM 的评估结果"""
    if data.get('success'):
        evaluation = data.get('evaluation', {})
        score = evaluation.get('score', 0)
        feedback = evaluation.get('feedback', '')
        print(f'\n⭐ 评分: {score}/10')
        print(f'📊 评价: {feedback}')
        print('\n' + '='*50 + '\n')
    else:
        print(f'❌ 错误: {data.get("error")}')


@sio.on('interview_started')
def on_interview_started(data):
    """面试开始"""
    print('✅ 面试会话已启动')
    print('🎤 请开始讲话...\n')


@sio.on('error')
def on_error(data):
    """错误处理"""
    error_msg = data.get('error', 'Unknown error')
    print(f'\n❌ 服务器错误: {error_msg}')
    if 'details' in data:
        print(f'   详情: {data["details"]}')


# ==================== 语音识别回调 ====================

class AsrCallback(RecognitionCallback):
    """实时语音识别回调处理"""
    
    def on_open(self) -> None:
        """打开麦克风"""
        global mic, stream
        print('🎤 麦克风已打开，开始录音...')
        mic = pyaudio.PyAudio()
        stream = mic.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True
        )

    def on_close(self) -> None:
        """关闭麦克风"""
        global mic, stream
        print('\n🎤 麦克风已关闭')
        if stream:
            stream.stop_stream()
            stream.close()
        if mic:
            mic.terminate()
        stream = None
        mic = None

    def on_complete(self) -> None:
        """识别完成"""
        print('\n✅ 识别完成')

    def on_error(self, message) -> None:
        """错误处理"""
        print(f'\n❌ 错误 (RequestID: {message.request_id})')
        print(f'   {message.message}')
        if stream is not None:
            try:
                if stream.active:
                    stream.stop()
                    stream.close()
            except:
                pass
        sys.exit(1)

    def on_event(self, result: RecognitionResult) -> None:
        """处理识别结果"""
        global current_question, chat_history
        
        sentence = result.get_sentence()
        if 'text' in sentence:
            text = sentence['text']
            is_end = RecognitionResult.is_sentence_end(sentence)
            
            if is_end:
                # 句子识别完成
                print(f'\n✅ 完整回答: {text}')
                
                # 如果连接到后端，则发送到 LLM 处理
                if sio.connected and current_question:
                    print('📤 正在发送到后端...')
                    
                    # 保存到对话历史
                    chat_history.append({
                        'role': 'user',
                        'content': text
                    })
                    
                    # 发送到后端处理
                    sio.emit('llm_process_answer', {
                        'user_answer': text,
                        'current_question': current_question,
                        'position': 'Java后端工程师',  # 可配置
                        'chat_history': chat_history
                    })
                else:
                    if not sio.connected:
                        print('⚠️  未连接到后端，请启动后端服务')
                    if not current_question:
                        print('⚠️  没有当前问题')
            else:
                # 实时部分识别结果
                print(f'   {text}', end='\r')


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    print('\n\n⛔ 停止识别...')
    try:
        if 'recognition' in globals():
            recognition.stop()
    except:
        pass
    
    # 断开连接
    if sio.connected:
        sio.disconnect()

    stop_tts()
    
    print('👋 已退出')
    sys.exit(0)


def connect_to_backend():
    """连接到后端服务"""
    try:
        print(f'🔗 正在连接到后端: {BACKEND_URL}')
        # 先 polling 再自动升级 websocket，避免开发服务器 websocket 兼容问题。
        sio.connect(BACKEND_URL)
        print('✅ 已连接到后端\n')
        return True
    except Exception as e:
        print(f'❌ 连接失败: {e}')
        print('⚠️  将以离线模式运行语音识别\n')
        return False


def start_interview(position='Java后端工程师', difficulty='medium'):
    """启动面试会话"""
    global current_question
    
    if sio.connected:
        print(f'📝 启动面试 - 职位: {position}, 难度: {difficulty}')
        sio.emit('start_interview', {
            'position': position,
            'difficulty': difficulty
        })
        
        # 生成第一个问题
        print('📤 请求生成问题...')
        sio.emit('llm_generate_question', {
            'position': position,
            'difficulty': difficulty
        })
    else:
        print('⚠️  未连接到后端，无法启动面试')


def create_recognition_with_fallback(callback):
    """按候选模型顺序创建识别对象，避免单模型不可用时直接失败。"""
    tried = set()
    last_error = None

    for model_name in ASR_MODEL_FALLBACKS:
        if model_name in tried:
            continue
        tried.add(model_name)

        try:
            print(f'🧠 尝试识别模型: {model_name}')
            return Recognition(
                model=model_name,
                format=format_pcm,
                sample_rate=sample_rate,
                callback=callback,
            )
        except Exception as e:
            last_error = e
            print(f'⚠️  模型不可用: {model_name} ({e})')

    raise RuntimeError(f'所有 ASR 模型均不可用，最后错误: {last_error}')


# ==================== 主函数 ====================

if __name__ == '__main__':
    # 初始化 DashScope
    init_dashscope_api_key()
    print('✅ DashScope 初始化完成\n')
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)

    # 启动语音播报线程
    start_tts_worker()

    if TTS_AVAILABLE:
        print(f'🔊 EdgeTTS 已启用，发音人: {TTS_VOICE}')
    else:
        print('⚠️  EdgeTTS 未启用。请安装 requirements-asr.txt 中新增依赖。')
    
    # 连接到后端
    backend_connected = connect_to_backend()
    
    # 启动面试（如果后端已连接）
    if backend_connected:
        start_interview(position='Java后端工程师', difficulty='medium')
    
    print('🎤 启动实时语音识别...')
    print('💡 提示: 按 Ctrl+C 退出\n')
    
    try:
        # 创建识别回调
        callback = AsrCallback()
        
        # 创建识别对象（带模型回退）
        recognition = create_recognition_with_fallback(callback)
        
        # 启动识别
        recognition.start()

        # 持续将麦克风数据送入识别引擎
        while True:
            if stream:
                data = stream.read(block_size, exception_on_overflow=False)
                # 面试官播报时发送静音帧做 keepalive，避免 ASR 因长时间无音频超时断开。
                if not is_tts_playing:
                    recognition.send_audio_frame(data)
                else:
                    recognition.send_audio_frame(b'\x00' * len(data))
                    time.sleep(0.02)
            else:
                break

        recognition.stop()
        
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f'❌ 启动失败: {e}')
        sys.exit(1)