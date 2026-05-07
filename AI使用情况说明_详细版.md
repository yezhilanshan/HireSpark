# AI 工具使用情况说明（详细版）

> 适用场景：比赛申报材料、答辩佐证  
> 项目名称：天枢智面（HireSpark）  
> 更新日期：2026年5月3日

---

## 一、AI 工具使用总览表

### （一）AI 服务 API 集成类（作为系统核心能力引擎）

| 序号 | AI工具的名称、版本、访问方式，使用时间 | 使用AI工具的环节与目的 | 关键提示词 / 配置 | AI服务的关键作用（含佐证） | 人工修改说明 | 采纳比例与说明 |
|------|--------------------------------------|---------------------|-------------------|--------------------------|-------------|--------------|
| 1 | **阿里云 DashScope Paraformer**（语音识别 ASR），API 调用（`dashscope.audio.asr.Recognition`），2025年3月–5月 | **实时语音识别**：面试过程中将候选人语音实时转写为文本，支持流式传输、多会话并发、自动断句和音量检测。是整个"三层语音处理链路"的核心引擎。 | 系统通过 `AsrCallbackHandler` 管理实时识别生命周期，配置 16kHz 采样率的 PCM 音频流输入，回调模式获取 `on_event` 的实时转写结果与最终确认文本 | （1）实现实时流式语音转写，延迟 < 500ms；（2）支持多会话并发识别（每个面试会话独立一个 `Recognition` 实例）；（3）提供 `on_partial`（中间结果）与 `on_final`（确认结果）双回调，支撑前端字幕实时展示。代码位于 `backend/utils/asr_manager.py`（52KB，约1200行） | 在阿里原生 `RecognitionCallback` 基础上增加：（1）`audioop` 音量检测实现自适应静音触发；（2）标点恢复与敏感词过滤后处理；（3）面试专用语音指令识别（如"下一题""重复""跳过"）；（4）音频缓冲队列管理，防止数据积压；（5）降级与重连机制 | 核心识别能力由阿里 ASR 提供（约60%核心代码），人工在此基础上补充业务层适配、容错与面试场景定制（约40%），整体采纳率约65% |
| 2 | **阿里云 DashScope CosyVoice-v3-flash**（语音合成 TTS），API 调用 + 独立 HTTP 服务封装，2025年3月–5月 | **AI 语音播报**：将面试官的提问文本合成为自然语音进行播报，用于面试场景中的"AI虚拟面试官"口语输出。独立部署于 `tts_service/app.py`（端口 5001），主后端通过 HTTP 远程调用。 | 主后端 `tts_manager.py` 调用 `POST /synthesize` 接口，传入 `{"text": "面试官提问文本", "voice": "default"}`；CosyVoice API 接收分词后的文本，返回 WAV 音频流 | （1）实现面试官提问的语音合成，输出自然流畅的中文语音；（2）独立服务架构（FastAPI），与主后端解耦；（3）文本预处理模块 `prepare_tts_text()` 处理面试场景的长文本分段与口语化适配。代码位于 `tts_service/app.py`、`backend/utils/tts_manager.py` | 在 CosyVoice API 基础上：（1）封装为独立 FastAPI 服务，支持异步合成与结果缓存；（2）增加 Edge-TTS（Microsoft）降级方案，当 CosyVoice 不可用时自动切换；（3）文本预处理逻辑：分句、去Markdown、数字口语化、面试用语优化；（4）环境变量驱动的多Provider配置（`TTS_PROVIDER`），支持 auto/cosyvoice/edge 动态切换 | 核心合成能力由阿里 CosyVoice 提供（约55%），人工补充服务架构、降级策略、文本预处理（约45%），整体采纳率约60% |
| 3 | **阿里云 DashScope Qwen-Max**（大语言模型），API 调用（`dashscope.Generation`），2025年3月–5月 | **AI 面试官智能对话**：作为核心技术引擎，驱动"AI虚拟面试官"的多轮对话能力，包括：出题、追问、难度调控、面试节奏控制。覆盖技术基础面、项目深度面、系统设计面、HR综合面四轮面试 | 系统为每一轮面试设计了专用 System Prompt（详见 `llm_manager.py` 第 40-136 行）。例如技术基础面提示词核心指令："每次只问一个问题，由浅入深；不要给标准答案；不直接解释概念；控制200字以内" | （1）实现四轮差异化面试对话（技术/项目/系统设计/HR），每轮有独立的系统提示词、考察重点与提问风格；（2）支持基于候选人回答的智能追问与深度挖掘；（3）支持简历数据注入（`load_resume_data`），使提问个性化；（4）语音播报约束：强制输出纯文本、禁止 Markdown 和代码块。代码位于 `backend/utils/llm_manager.py`（58KB，约1200行） | 在 Qwen-Max API 基础上：（1）人工设计四套轮次专用 System Prompt（每个 100-200 字的精炼提示词）；（2）增加候选人卡顿/不会时的"反应规则"（`INTERVIEWER_STRUGGLE_RESPONSE_RULES`），包括不否定、不教学、给短提示后落回明确问题等 9 条规则；（3）后处理层：过滤授课句式、Meta提问、教学语句；（4）问题抽取正则匹配；（5）最终输出文本的后处理清洗。Qwen-Max 负责生成核心内容（约70%），人工设计的 Prompt工程、后处理清洗和业务逻辑约占30%，整体采纳率约70% | 核心推理能力由 Qwen-Max 提供，人工投入主要在 Prompt Engineering、后处理质量把控和面试业务逻辑上。采纳率约70% |
| 4 | **阿里云 DashScope Qwen-Plus**（大语言模型），API 调用（`dashscope.Generation`）cope.Generation），2025年3月–5月	AI 问答助手：驱动右侧栏 AI 助手（/assistant 页面）的多轮对话能力，回答用户的岗位知识问答、面试技巧咨询、简历优化建议等。与面试官LL，2025年3月–5月 | **AI 问答助手**：驱动右侧栏 AI 助手（`/assistant` 页面）的多轮对话能力，回答用户的岗位知识问答、面试技巧咨询、简历优化建议等。与面试官LLM分离部署，使用不同模型实例 | 配置系统提示词（`config.yaml` 第 148 行）："你是一个专业、简洁、可信的中文求职助手。重点帮助用户准备技术面试、梳理项目表达、优化简历表述，并提供可执行建议。回答请直奔主题，先给结论，再给关键理由。" | （1）支持多会话管理（新建、切换、删除）；（2）RAG 检索增强后生成带引用的回答；（3）异步任务模式（`POST /api/assistant/chat` → `GET /api/assistant/tasks/{task_id}`），支持长回答流式返回；（4）会话历史持久化，支持续聊与回看。代码位于 `backend/utils/assistant_service.py`（33KB） | 在 Qwen-Plus API 基础上：（1）RAG 检索结果注入上下文（检索优先、知识库引用标记）；（2）证据不足时标注"模型补充"，避免伪装成知识库事实；（3）max_history=6 的历史窗口管理；（4）force_plain_text 模式确保输出不含 Markdown；（5）支持 OpenRouter/Ollama 作为备选 Provider | Qwen-Plus 提供核心回答生成（约65%），人工补充 RAG 集成、会话管理、引用标记和 Provider 切换逻辑（约35%），采纳率约65% |
| 5 | **阿里云 DashScope Qwen-VL-Max**（多模态视觉模型），API 调用（`dashscope.MultiModalConversation`），2025年3月–5月 | **简历识别与 OCR**：识别上传的简历图片/PDF 中的文本内容并进行结构化提取，支持中文简历的字段抽取（姓名、学校、技能、项目经历、工作经历等） | 将简历图片转为 Base64 后调用 Qwen-VL-Max，提示词要求其输出结构化 JSON，包含 `name`、`education`、`skills`、`projects`、`experiences` 等字段 | （1）支持图片格式（JPG/PNG）和 PDF 简历的 OCR 识别；（2）结构化字段提取，自动回填到用户资料表单（`/me` 页面）；（3）技术关键词自动打标（与岗位知识库交叉匹配）。代码位于 `backend/utils/resume_parser.py`（20KB） | 在 Qwen-VL-Max 视觉识别基础上：（1）增加字段自动校验（必填项检查、格式规范化）；（2）技术关键词二次匹配（与 `COMMON_KEYWORD_HINTS` 词表交叉比对）；（3）解析结果版本管理（每次解析独立存储，支持历史查看与回退）；（4）异常格式兼容（拍照简历、扫描件、非标准模板） | Qwen-VL-Max 提供OCR与结构化提取核心能力（约60%），人工补充校验、关键词匹配和版本管理（约40%），采纳率约60% |
| 6 | **shibing624/text2vec-base-chinese**（开源 Embedding 模型），本地加载（`sentence-transformers`），2025年3月–5月 | **RAG 向量化**：将岗位知识库中的面试题目、参考答案、考点解释等文本转为 768 维向量，存入 ChromaDB，支撑语义检索与相似度匹配 | 无提示词（非生成式模型）。通过 `SentenceTransformer.encode(text, convert_to_numpy=True)` 将文本转为向量 | （1）将岗位知识库文档（`interview_knowledge/`、`basic_knowledge/` 目录）全部向量化索引；（2）支持语义搜索（`search_type: similarity`），top_k=5，最小相似度 0.45；（3）支撑 RAG 检索增强评估和 AI 助手知识问答；（4）提供 `encode_batch` 批量编码能力。代码位于 `backend/rag/embedding.py`、`backend/rag/chroma_db.py`（23KB） | 在 text2vec 模型基础上：（1）封装 `_mock_encode` 降级方案（基于关键词 hash 的稀疏向量），当模型不可用时自动切换；（2）模型加载失败时的优雅降级提示；（3）支持 `BAAI/bge-base-zh-v1.5` 等替代模型的热切换 | 模型提供标准 Embedding 能力，人工补充降级策略和多模型热切换（改动量约15%），采纳率约90% |
| 7 | **Google MediaPipe Tasks Vision**（`face_landmarker.task`），前端 WASM/CDN 加载（`@mediapipe/tasks-vision@0.10.21`），2025年3月–5月 | **人脸行为指标采集**：在面试过程中实时追踪候选人 478 个人脸关键点（Landmarks），计算眨眼频率、视线偏移（gaze drift）、头部姿态（pitch/yaw/roll）、嘴部活动等行为指标 | 无提示词（视觉推理模型）。前端每 125ms 采集一帧视频，通过 MediaPipe WASM 推理人脸网格，提取 478 个关键点坐标与 52 个融合变形（BlendShapes）权重 | （1）实时人脸检测与 478 点关键点追踪（8 FPS 分析帧率）；（2）眨眼检测（EAR 阈值 0.55）；（3）视线方向估计（虹膜关键点 468-477）；（4）头部姿态欧拉角计算（`pitch/yaw/roll`）；（5）微表情 BlendShapes（`eyeBlinkLeft/Right`、`mouthSmileLeft/Right`、`jawOpen` 等）。代码位于 `frontend/lib/facephys/useFaceBehaviorMetrics.ts` | 在 MediaPipe 原生输出基础上：（1）将原始关键点坐标转为有业务含义的指标（视线偏移比例、眨眼频率、头部晃动幅度）；（2）人脸距离稳定性检测（防止远离/靠近镜头作弊）；（3）UI 更新节流（240ms 间隔）；（4）`mounted` 状态检查避免 SSR 端报错 | MediaPipe 提供人脸关键点推理（约75%），人工补充指标计算、业务含义映射和性能优化（约25%），采纳率约80% |
| 8 | **TensorFlow Lite + rPPG 自定义模型**（`facephys/models/*.tflite`），前端 Web Worker 加载，2025年3月–5月 | **远程心率检测（rPPG）**：通过分析人脸视频中的皮肤颜色微变化，无接触式实时估计候选人的心率（HR），作为面试"状态层"评估的生理指标依据 | 无提示词（生理信号模型）。前端以 30 FPS 采集人脸 ROI 区域像素，输入 rPPG 模型（TFLite），输出心率估计值（BPM）与信号质量指数（SQI） | （1）非接触式心率估计（面部皮肤反射光电容积描记）；（2）信号质量评估（SQI < 0.38 时标记为 unreliable）；（3）人脸丢失超时检测（500ms 无脸则停止计算）；（4）Web Worker 独立线程推理，不阻塞主线程 UI。代码位于 `frontend/lib/facephys/useFacePhysRppg.ts` | 在 TensorFlow Lite 推理基础上：（1）Web Worker 封装（`inferenceWorker` + `psdWorker`），避免主线程卡顿；（2）输入缓冲区管理（450帧环形缓冲）；（3）信号质量门控（SQI 阈值、人脸在位检查）；（4）模型文件分片加载与 CDN 回退；（5）`requestAnimationFrame` 驱动的采集-推理同步 | rPPG 模型提供核心生理信号推理（约70%），人工补充 Worker 架构、信号质量控制和性能优化（约30%），采纳率约75% |

---

### （二）AI 开发辅助工具类（编码、文档、调试辅助）

| 序号 | AI工具的名称、版本、访问方式，使用时间 | 使用AI工具的环节与目的 | 关键提示词 | AI回复的关键内容 | 人工修改说明 | 采纳比例与说明 |
|------|--------------------------------------|---------------------|-----------|---------------|-------------|--------------|
| 9 | **Kimi-K2.6**，网页端访问（kimi.moonshot.cn），2025年4月–5月 | **代码编程**：前端页面开发与功能实现（学习社区功能、收藏/错题本、题目讨论区、知识图谱交互优化等） | "请帮我实现一个社区功能，包含面经广场和学习小组，使用 React + TypeScript，数据用 localStorage 存储，风格与现有项目一致" | 生成社区页面组件结构（CommunityPage、PostDetail、GroupDetail）、数据管理模块（community.ts）、路由配置 | 根据项目现有代码风格调整组件命名、样式变量（如项目统一的 `#FAF9F6` 背景色、`#E5E5E5` 边框色）、类型定义；补充错误处理和边界情况；将 AI 建议的通用图标替换为项目统一的 Lucide 图标体系 | AI生成基础框架占60%，人工调整占40%，整体采纳率约70% |
| 10 | **Kimi-K2.6**，网页端访问，2025年4月–5月 | **代码编程**：Bug修复与性能优化（页面跳转卡顿、500错误、字体加载优化、z-index层级问题等） | "点击知识图谱节点时页面跳动，请分析 KnowledgeGraphCanvas 组件并修复" | 定位到 useEffect 依赖数组中包含 `selectedNodeId` 导致频繁重建图谱的问题，提供 useRef 缓存方案避免重建 | 验证修复方案后，发现 SSR 环境下 `createPortal` 报错，补充 `mounted` 状态检查；同时修复了头像弹窗 z-index 被主界面遮挡的问题，采用 React Portal 渲染到 body | AI诊断准确，人工验证后采纳核心方案并补充边界处理，采纳率约80% |
| 11 | **Kimi-K2.6**，网页端访问，2025年5月 | **内容生成**：撰写比赛项目简介与亮点提炼 | "请根据项目功能写一份比赛级项目简介，突出创新亮点，要求专业且有说服力" | 生成完整的项目简介框架，包含痛点分析、功能矩阵、六大创新亮点、技术架构描述 | 精简篇幅至比赛要求范围，调整语言风格符合计算机设计大赛评审偏好，补充社交化学习生态等新增功能描述，将技术架构图转为文字叙述 | AI生成框架占50%，人工重写与润色占50%，采纳率约60% |
| 12 | **Kimi-K2.6**，网页端访问，2025年5月 | **代码编程**：性能优化（next.config.js 配置、loading.tsx 骨架屏、组件懒加载、Bundle分割） | "页面切换反应慢，请分析性能瓶颈并提供 Next.js 15 优化方案" | 提出字体子集化、代码分割（splitChunks）、Suspense 边界、Bundle 分析、optimizePackageImports 等优化方向 | 字体优化方案经测试后回退（用户明确要求保留原本地字体），保留其他优化措施；补充 ClientLayout 懒加载实现；为社区等重页面单独配置 loading.tsx 骨架屏 | 部分采纳，核心优化（loading、splitChunks、懒加载）采纳率约75% |
| 13 | **Kimi-K2.6**，网页端访问，2025年5月 | **代码编程**：数据管理模块设计（localStorage 持久化、收藏/错题本/讨论区数据结构、数据版本兼容） | "设计一个 localStorage 数据管理方案，支持题目收藏、错题本、讨论区，要求类型安全" | 生成 TypeScript 类型定义、CRUD 操作函数、数据版本控制与迁移方案 | 调整数据结构字段命名以匹配现有题库数据格式（如与 `NormalizedQuestion` 类型对齐），增加数据迁移兼容性处理，补充去重逻辑和并发操作保护 | AI生成核心逻辑占70%，人工适配占30%，采纳率约80% |
| 14 | **Kimi-K2.6**，网页端访问，2025年5月 | **内容生成**：精简版项目简介（100-150字）与创新描述 | "写一段100-150字的项目简介，再写一段100-150字的创新描述，要求语言凝练、亮点突出" | 生成两段符合字数要求的精炼文案，涵盖六大亮点 | 微调措辞确保涵盖 RAG 知识引擎、多模态防作弊、社交化学习等核心亮点，调整句式使语言更凝练有力 | AI生成初稿占80%，人工润色占20%，采纳率约90% |
| 15 | **Kimi-K2.6**，网页端访问，2025年5月 | **代码编程**：侧边栏导航更新与路由配置 | "在侧边栏添加社区入口，并配置对应路由，保持与现有导航风格一致" | 生成导航项配置代码、路由文件结构（app/community 目录结构） | 调整图标选择（使用与项目统一的 MessageSquare、Users 等 Lucide 图标）、验证路由与页面组件匹配，补充移动端适配 | AI生成基础代码占90%，人工微调占10%，采纳率约95% |
| 16 | **Kimi-K2.6**，网页端访问，2025年5月 | **语言润色**：技术架构图转文字描述、闭环描述优化 | "把ASCII架构图转成流畅的文字描述，把bullet列表转成连贯的学术段落" | 生成流畅的技术架构文字描述和成长闭环段落，保持专业术语准确 | 微调专业术语使用（如明确区分 RAG 检索增强生成、ChromaDB 向量数据库等），确保与全文风格一致 | AI生成占85%，人工润色占15%，采纳率约90% |
| 17 | **Kimi-K2.6**，网页端访问，2025年5月 | **内容生成**：开发制作工具章节撰写 | "写一段开发制作工具说明，采用文字描述，涵盖前后端、数据库、部署运维" | 生成前端、后端、数据库、开发工具、部署运维五个方面的说明段落 | 补充具体版本号（Next.js 15、React 19、Python 3.11 等），调整表述符合比赛文档规范，补充 AI 辅助开发说明 | AI生成占70%，人工补充与调整占30%，采纳率约80% |
| 18 | **Kimi-K2.6**，网页端访问，2025年5月 | **代码编程**：项目品牌名称统一替换（HireSpark → PanelMind） | "帮我把前端所有可见的 HireSpark 替换为 PanelMind，包括登录页、侧边栏、导航、设置页等" | 定位到 9 个文件中的 12 处可见文本，提供替换清单 | 逐一核对每处替换的上下文，确保不影响 localStorage key 等内部逻辑；替换后执行 `npm run build` 验证编译通过 | AI定位准确，人工复核后全部采纳，采纳率约95% |

---

## 二、AI 服务在系统架构中的分布图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Next.js 15)                       │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │ MediaPipe Tasks Vision │  │ TensorFlow Lite (rPPG 心率)  │  │
│  │ (人脸478点关键点追踪)   │  │ (远程光电容积描记)            │  │
│  │ CDN: jsdelivr WASM    │  │ /facephys/models/*.tflite   │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Socket.IO + HTTP REST
┌──────────────────────────────▼──────────────────────────────┐
│                        后端 (Flask)                            │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │ ASR 识别      │ │ LLM 面试官    │ │ LLM AI助手            │ │
│  │ Paraformer   │ │ Qwen-Max     │ │ Qwen-Plus            │ │
│  │ (实时流式)    │ │ (多轮对话)    │ │ (RAG增强问答)         │ │
│  └─────────────┘ └──────────────┘ └───────────────────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │ 简历OCR      │ │ Embedding     │ │ 结构化评估             │ │
│  │ Qwen-VL-Max │ │ text2vec     │ │ Qwen-Max (评分推理)   │ │
│  │ (图片识别)    │ │ (768维向量)   │ │                       │ │
│  └─────────────┘ └──────────────┘ └───────────────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼──────────────────────────────┐
│                    TTS 独立服务 (端口 5001)                      │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │ CosyVoice-v3-flash    │  │ Edge-TTS (Microsoft)         │  │
│  │ (主 TTS 引擎)          │  │ (降级备选方案)                │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、各 AI 服务的职责边界与调用关系

| 层级 | AI 服务 | 系统角色 | 输入 | 输出 | 调用时机 |
|------|--------|---------|------|------|---------|
| 前端-视觉 | MediaPipe Tasks Vision | 人脸行为指标采集器 | `<video>` 帧 | 478 个人脸关键点 + BlendShapes | 面试进行中，每 ~125ms 一帧 |
| 前端-生理 | TensorFlow Lite rPPG | 远程心率检测器 | 人脸 ROI 像素序列 | 心率 BPM + 信号质量 SQI | 面试进行中，30 FPS 持续采集 |
| 后端-语音 | DashScope Paraformer | 语音转文字引擎 | PCM 16kHz 音频流 | 实时转写文本（partial + final） | 面试中用户说话时 |
| 后端-对话 | DashScope Qwen-Max | AI 虚拟面试官 | 面试上下文 + 候选人回答 | 面试官提问文本 | 面试每轮对话 |
| 后端-问答 | DashScope Qwen-Plus | AI 问答助手 | 用户问题 + RAG 检索结果 | 带引用的知识回答 | 用户主动在助手页提问 |
| 后端-视觉 | DashScope Qwen-VL-Max | 简历 OCR 识别器 | 简历图片 Base64 | 结构化字段 JSON | 用户上传简历时 |
| 后端-评分 | DashScope Qwen-Max | 评估推理引擎 | 评估 Prompt + 参考知识 | 结构化评分 JSON | 每道题回答完成后（异步） |
| 后端-向量 | text2vec-base-chinese | 文本向量化 | 知识库文档文本 | 768 维向量 | 知识库构建时 + 实时检索时 |
| 后端-语音 | CosyVoice-v3-flash | 文本转语音引擎 | 预处理后文本 | WAV 音频 | 面试官提问需语音播报时 |
| 后端-语音 | Edge-TTS | TTS 降级备选 | 预处理后文本 | WAV 音频 | CosyVoice 不可用时自动切换 |

---

## 四、使用说明与声明

### 1. AI 服务使用原则

本项目以**人工设计与开发为主，AI 服务作为系统核心能力引擎与开发辅助手段**。具体分层如下：

- **系统能力层（API 集成类）**：阿里云 DashScope（ASR/TTS/LLM/Vision）、MediaPipe、TensorFlow Lite、text2vec 等 AI 服务作为系统的核心技术能力组件，负责语音识别、对话生成、人脸分析、向量检索等特定任务。所有 AI 输出均经过系统后处理、质量校验与业务逻辑包装后才呈现给用户。
- **开发辅助层（工具类）**：Kimi-K2.6 用于加速代码实现、提供优化思路、辅助文案撰写。所有 AI 生成内容均经过人工审核、修改与验证。

### 2. 代码安全与隐私保护

- 未将任何 API 密钥、数据库密码、服务器地址等敏感信息输入外部 AI 工具（Kimi 等）
- 阿里云 API 密钥通过环境变量（`${BAILIAN_API_KEY}`）注入，不硬编码在代码中（参考 `config.yaml` 第 124 行）
- AI 生成的代码均经过安全审查，确保无潜在 XSS、SQL 注入等安全风险
- 未使用外部 AI 工具处理用户隐私数据
- 前端 MediaPipe/TensorFlow Lite 推理全部在本地浏览器端完成，人脸数据不出浏览器

### 3. 知识产权声明

- 项目使用的 AI 服务（阿里云 DashScope、MediaPipe、text2vec 等）均通过公开 API 或开源协议合法调用
- AI 服务提供商的模型权重与推理能力归各自厂商所有
- 项目在此基础上构建的**三层语音处理链路、RAG 检索增强评估、三层评分体系、知识图谱构建、社交化学习生态、面试流程编排**等系统设计与业务逻辑具有原创性
- AI 开发辅助工具（Kimi）生成的代码框架与文案素材已根据项目实际需求进行**深度修改与重构**，融入项目独特的业务逻辑与设计理念

### 4. 采纳比例说明

| 采纳比例范围 | 含义 |
|------------|------|
| 90%+ | AI 输出质量高，人工仅做微调（如文本润色、图标替换） |
| 70-89% | AI 提供核心逻辑/框架，人工补充边界处理、适配与容错 |
| 50-69% | AI 提供基础实现，人工进行了大量定制化改造 |
| <50% | AI 提供思路参考，人工进行了主导性设计与重构 |

低采纳率不代表 AI 质量差，而是说明人工进行了大量定制化改造以适应项目特定的技术栈、设计风格与业务需求。

---

## 五、附录：关键佐证材料

### 附录1：AI 服务 API 集成类佐证（对应序号 1-8）

| 序号 | AI 服务 | 关键代码文件 | 行数/大小 |
|------|--------|------------|----------|
| 1 | Paraformer ASR | `backend/utils/asr_manager.py` | ~1200行 / 52KB |
| 2 | CosyVoice TTS | `tts_service/app.py`、`backend/utils/tts_manager.py` | 合计 ~350行 |
| 3 | Qwen-Max (面试官) | `backend/utils/llm_manager.py` | ~1200行 / 58KB |
| 4 | Qwen-Plus (助手) | `backend/utils/assistant_service.py` | ~800行 / 33KB |
| 5 | Qwen-VL-Max (简历OCR) | `backend/utils/resume_parser.py` | ~500行 / 20KB |
| 6 | text2vec (Embedding) | `backend/rag/embedding.py`、`backend/rag/chroma_db.py` | 合计 ~600行 / 27KB |
| 7 | MediaPipe Face | `frontend/lib/facephys/useFaceBehaviorMetrics.ts` | ~200行 |
| 8 | TensorFlow Lite rPPG | `frontend/lib/facephys/useFacePhysRppg.ts` | ~200行 |

**配置证据**：
- `backend/config.yaml` 第 118-124 行：`llm.provider: qwen`、`llm.model: qwen-max`、`llm.vision_model: qwen-vl-max`、`llm.tts_model: cosyvoice-v3-flash`
- `backend/config.yaml` 第 179 行：`rag.embedding_model: shibing624/text2vec-base-chinese`
- `backend/config.yaml` 第 148 行：助手系统提示词配置
- `backend/config.yaml` 第 160-161 行：OpenRouter 和 Ollama 备选 Provider 配置

### 附录2：AI 开发辅助工具类佐证（对应序号 9-18）

- **社区功能实现**：`frontend/app/community/page.tsx`、`frontend/lib/community.ts`、`frontend/app/community/post/[id]/page.tsx`
- **收藏/错题本功能**：`frontend/lib/question-book.ts`、`frontend/app/dashboard/questions/bookmarks/page.tsx`
- **性能优化配置**：`frontend/next.config.js`（含 `optimizePackageImports`、`splitChunks` 配置）、`frontend/app/loading.tsx`
- **Bug 修复记录**：`frontend/components/KnowledgeGraphCanvas.tsx`（useEffect 依赖优化）、`frontend/components/ProfileEditorModal.tsx`（mounted 状态检查）
- **品牌替换记录**：`frontend/app/page.tsx`、`frontend/components/PersistentSidebar.tsx`、`frontend/app/layout.tsx` 等 9 个文件的 Git 修改记录
- **项目简介文档**：`项目简介_比赛版.md`、`项目简介_精简版.md`
- **TTS 语音合成**：`tts_service/app.py`（独立 FastAPI 服务）、`backend/utils/tts_manager.py`（远程调用客户端）
- **ASR 语音识别**：`backend/utils/asr_manager.py`（Paraformer 实时识别管理器，含 `AsrCallbackHandler` 类）

### 附录3：人工修改深度示例

**以序号 3（Qwen-Max 面试官 LLM）为例**：

- **AI 服务提供**：Qwen-Max 提供基于 Prompt 的文本生成能力
- **人工设计的核心资产**：
  1. 四套轮次专用 System Prompt（技术基础面/项目深度面/系统设计面/HR综合面），每个 100-200 字，精确定义考察重点与提问风格
  2. 候选人卡顿/不会时的反应规则（`INTERVIEWER_STRUGGLE_RESPONSE_RULES`），包含 9 条规则，确保面试官行为符合专业面试规范
  3. 语音播报约束（`VOICE_SAFE_OUTPUT_RULES`），强制禁止 Markdown、代码块、特殊格式
  4. 后处理过滤层：正则匹配过滤授课句式、Meta 提问、教学语句；自动抽取追问问题
- **结论**：Qwen-Max 提供推理能力（约70%），但决定面试官"像一个真正的面试官"的关键因素——系统提示词设计、行为规则、后处理——全部是人工设计的结果

**以序号 7（MediaPipe 人脸分析）为例**：

- **AI 服务提供**：MediaPipe 提供人脸关键点坐标（478 个 xyz）和 BlendShapes 权重（52 个）
- **人工设计的核心资产**：
  1. 将原始坐标转为业务指标：眨眼频率（EAR 阈值 0.55）、视线偏移比例（虹膜关键点向量计算）、头部晃动幅度（欧拉角时序分析）
  2. 人脸距离稳定性检测（防止远离/靠近镜头作弊）
  3. UI 更新节流与性能优化（240ms 间隔、8 FPS 分析帧率）
- **结论**：MediaPipe 提供底层视觉推理能力，但"如何将 478 个点变成面试评估的有意义指标"是人工分析设计的结果

---

**文档版本**：v3.0（详细版）  
**最后更新**：2026年5月3日  
**适用范围**：比赛申报 AI 使用情况说明、答辩佐证材料
