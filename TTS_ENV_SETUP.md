# TTS 独立环境与双服务拆分

## 目标

- 主后端继续使用原有环境，保留 `mediapipe`、`sentence-transformers` 等依赖。
- TTS 单独使用一个 Conda 环境，避免 `transformers`、`protobuf`、`numpy` 的版本互相污染。
- 运行时拆成两个 HTTP 服务：
  - 主后端：`http://localhost:5000`
  - TTS 服务：`http://localhost:5001`

## 推荐环境

### 1. 主后端环境

```powershell
conda create -n interview-anti-cheat python=3.9 -y
conda activate interview-anti-cheat
pip install -r requirements.txt
```

### 2. TTS 专用环境

只使用 Edge TTS：

```powershell
conda create -n interview-tts python=3.10 -y
conda activate interview-tts
pip install -r requirements.txt
```

使用 MeloTTS：

```powershell
conda create -n interview-tts python=3.10 -y
conda activate interview-tts
pip install -r requirements.txt
```

## 为什么这样拆

- `mediapipe 0.10.14` 要求 `protobuf < 5`
- 你在 TTS 安装链里拉进来的 `gradio/opentelemetry-proto` 需要 `protobuf >= 5`
- `sentence-transformers 5.3.0` 需要 `transformers >= 4.41`
- `MeloTTS 0.1.2` 固定依赖 `transformers == 4.27.4`

这些要求在同一个环境里不可同时满足，但拆成两个环境后就没有冲突了。

## 启动方式

### 一键启动

```powershell
powershell -ExecutionPolicy Bypass -File .\start_all.ps1
```

### 单独启动 TTS 服务

```powershell
$env:TTS_PROVIDER = "auto"
powershell -ExecutionPolicy Bypass -File .\tts_service\start_tts_service.ps1
```

强制只用 Edge TTS：

```powershell
$env:TTS_PROVIDER = "edge"
powershell -ExecutionPolicy Bypass -File .\tts_service\start_tts_service.ps1
```

默认优先 `edge-tts`，若合成失败自动回退到 `MeloTTS`。若要指定 Melo 参数：

```powershell
$env:TTS_PROVIDER = "auto"
$env:TTS_MELO_LANGUAGE = "ZH"
$env:TTS_MELO_SPEAKER = "ZH"
powershell -ExecutionPolicy Bypass -File .\tts_service\start_tts_service.ps1
```

若你需要“只允许首选 provider，不允许回退”，可开启严格模式：

```powershell
$env:TTS_PROVIDER = "edge"  # 或 auto，严格模式下 auto 仅使用 edge
$env:TTS_PROVIDER_STRICT = "true"
powershell -ExecutionPolicy Bypass -File .\tts_service\start_tts_service.ps1
```

## 接口

- TTS 健康检查：`GET /health`
- TTS 合成：`POST /synthesize`

请求体示例：

```json
{
  "text": "你好，这是一个 TTS 测试。"
}
```
