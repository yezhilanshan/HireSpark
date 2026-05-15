# Conda 环境依赖清单

本项目一键启动脚本 `start_all.ps1` 默认使用两个 Conda 环境：

- `interview`：主后端、ASR、RAG、面试流程、检测统计服务，监听 `http://localhost:5000`
- `interview-tts`：独立 TTS HTTP 服务，监听 `http://localhost:5001`

当前验证过的 Python 版本为 `Python 3.10.20`。

## 1. 主后端环境：interview

用途：

- Flask 后端 API
- Socket.IO 实时面试流程
- ASR 调用
- RAG / 题库 / 知识库
- 简历解析、报告生成、统计分析
- 摄像头行为检测与复盘相关后端逻辑

安装命令：

```powershell
conda create -n interview python=3.10 -y
conda activate interview
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

依赖文件：

- `requirements.txt`

主要依赖类别：

- Web/API：`Flask`、`Flask-Cors`、`Flask-SocketIO`、`eventlet`、`fastapi`、`uvicorn`
- 实时通信：`python-socketio`、`python-engineio`、`websocket-client`、`websockets`
- AI/LLM/ASR：`dashscope`、`qwen-asr`、`transformers`、`sentence-transformers`、`torch`、`torchaudio`
- RAG/向量库：`chromadb`、`numpy`、`scikit-learn`、`scipy`、`nltk`、`jieba`
- 视觉/检测：`opencv-contrib-python`、`mediapipe`
- 文档/简历/报告：`pdf2image`、`pypdf`、`python-docx`、`reportlab`、`Pillow`
- 数据与工具：`pandas`、`requests`、`python-dotenv`、`PyYAML`、`psutil`

启动验证：

```powershell
conda run -n interview python .\backend\app.py
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:5000/api/interviews?limit=1 -UseBasicParsing
```

## 2. TTS 环境：interview-tts

用途：

- 独立 TTS 服务
- Edge TTS 合成
- 音频处理与播放相关工具

安装命令：

```powershell
conda create -n interview-tts python=3.10 -y
conda activate interview-tts
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-tts.txt
```

依赖文件：

- `requirements.txt`
- `requirements-tts.txt`

说明：

- `requirements.txt` 提供 TTS 服务运行所需的基础 Web/API 依赖，例如 `fastapi`、`uvicorn`、`pydantic`。
- `requirements-tts.txt` 只包含 TTS 专用补充依赖，不能单独替代 `requirements.txt`。

TTS 专用依赖：

- `edge-tts`
- `dashscope`
- `playsound`
- `audioread`
- `ffmpy`
- `librosa`
- `PyAudio`
- `pydub`
- `resampy`
- `sounddevice`
- `soundfile`

启动验证：

```powershell
conda run -n interview-tts python -m uvicorn tts_service.app:app --host 0.0.0.0 --port 5001
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:5001/health -UseBasicParsing
```

## 3. 一键启动

两个环境安装完成后，可直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_all.ps1
```

脚本会检查：

- `interview` 是否存在
- `interview-tts` 是否存在
- 前端依赖是否安装
- 5000 / 5001 / 3000 等端口是否被占用

## 4. 外部系统依赖

部分 Python 包还依赖系统组件：

- `pdf2image`：需要 Poppler 可执行文件可用，或配置 Poppler 路径。
- `PyAudio` / `sounddevice`：需要本机音频设备和驱动正常。
- `pydub` / `ffmpy`：如需更完整的音频格式支持，建议安装 FFmpeg 并加入 `PATH`。

