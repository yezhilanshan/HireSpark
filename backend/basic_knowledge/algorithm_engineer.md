算法工程师面试题库

{
  "id": "algo_simple_001",
  "role": "算法工程师",
  "question": "为什么 Scaled Dot-Product Attention 要除以根号下的 dk？如果不除会出现什么问题？",
  "category": "大模型/算法工程",
  "subcategory": "Transformer基础",
  "competency": ["deep_learning", "llm_foundation"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["attention", "dk", "softmax", "数值稳定"],
  "tags": ["真实面经", "算法工程师", "Transformer", "大模型"],
  "answer_summary": "需要从点积方差、softmax饱和和梯度稳定性三个层面解释缩放原因，并说明它本质上是在做尺度归一化。",
  "key_points": ["QK点积方差随维度增大而增大", "不缩放时softmax更容易饱和", "梯度会变小且训练不稳定", "除以根号dk是在控制数值范围", "最终目的是让训练更稳定"],
  "optional_points": ["可补充与初始化、LayerNorm的关系", "可说明是否存在等价替代方案"],
  "expected_answer_signals": ["方差", "softmax饱和", "梯度稳定"],
  "common_mistakes": ["只说经验做法，不解释原因", "把缩放误解为单纯让值变小"],
  "scoring_rubric": {
    "basic": ["能说明缩放是为了稳定softmax"],
    "good": ["能从方差和梯度角度解释原因"],
    "excellent": ["能结合训练稳定性和工程实践展开"]
  },
  "followups": [
    {"question": "如果改成除以其他常数，会带来什么影响？", "trigger_type": "missing_analysis", "trigger_signals": ["dk", "softmax"]},
    {"question": "多头注意力里不同 head 是否共享这套缩放逻辑？", "trigger_type": "missing_detail", "trigger_signals": ["attention"]}
  ],
  "retrieval_text": "算法工程师 attention 基础题，考察为什么 attention 要除以根号dk，以及 softmax 饱和和梯度稳定性。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_002",
  "role": "算法工程师",
  "question": "请你介绍一下 Transformer 的整体架构，并说明为什么大模型通常选择 Decoder-only。",
  "category": "大模型/算法工程",
  "subcategory": "Transformer基础",
  "competency": ["deep_learning", "llm_foundation", "model_architecture"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["Transformer", "Encoder", "Decoder", "Decoder-only"],
  "tags": ["真实面经", "算法工程师", "架构设计", "大模型"],
  "answer_summary": "回答应覆盖 Encoder/Decoder 组成、自注意力与交叉注意力差异，以及 Decoder-only 在自回归建模、推理一致性和工程生态上的优势。",
  "key_points": ["Transformer核心组件包括注意力、FFN、残差和归一化", "Encoder偏向表征建模，Decoder偏向生成", "Decoder-only天然适合下一token预测", "训练目标与推理过程更一致", "便于做 KV Cache 和推理优化"],
  "optional_points": ["可对比 Encoder-only 与 Encoder-Decoder 的适用场景", "可补充推理效率和扩展性讨论"],
  "expected_answer_signals": ["自回归", "预训练目标", "推理效率"],
  "common_mistakes": ["混淆 Encoder 和 Decoder 的职责", "只背结构，不解释为什么选择 Decoder-only"],
  "scoring_rubric": {
    "basic": ["能说明 Transformer 的基本结构"],
    "good": ["能解释 Decoder-only 与自回归生成的关系"],
    "excellent": ["能结合推理、扩展性和生态做对比分析"]
  },
  "followups": [
    {"question": "Encoder-only、Encoder-Decoder、Decoder-only 分别更适合哪些任务？", "trigger_type": "missing_point", "trigger_signals": ["Encoder", "Decoder"]},
    {"question": "机器翻译场景为什么很多时候仍然选择 Encoder-Decoder？", "trigger_type": "missing_analysis", "trigger_signals": ["Decoder-only"]}
  ],
  "retrieval_text": "算法工程师 Transformer 架构题，考察 Encoder Decoder 差异和为什么大模型常用 Decoder-only。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_003",
  "role": "算法工程师",
  "question": "常见的位置编码有哪些？RoPE 的核心思想、优缺点和长上下文影响是什么？",
  "category": "大模型/算法工程",
  "subcategory": "位置编码",
  "competency": ["deep_learning", "llm_foundation"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["位置编码", "RoPE", "相对位置编码", "长上下文"],
  "tags": ["真实面经", "算法工程师", "Transformer", "位置编码"],
  "answer_summary": "需要先概述绝对和相对位置编码，再重点说明 RoPE 如何通过旋转变换把位置信息融入 Q/K 点积，以及它在长上下文外推中的优势与限制。",
  "key_points": ["位置编码用于补足注意力对顺序不敏感的问题", "RoPE把相对位置信息写入点积相似度", "RoPE对长序列更友好", "长上下文外推时仍会遇到频率和尺度问题", "二维或多模态场景需要额外设计位置策略"],
  "optional_points": ["可补充 ALiBi 与 RoPE 的对比", "可说明长上下文时常见插值或缩放技巧"],
  "expected_answer_signals": ["绝对位置", "相对位置", "旋转"],
  "common_mistakes": ["只会背 RoPE 名称，不会解释机制", "忽略长上下文外推边界"],
  "scoring_rubric": {
    "basic": ["能列举常见位置编码并说出 RoPE 基本用途"],
    "good": ["能说明 RoPE 的旋转机制和相对位置性质"],
    "excellent": ["能结合长上下文和多模态展开分析"]
  },
  "followups": [
    {"question": "ViT 或多模态模型里的二维位置编码与文本 RoPE 有什么不同？", "trigger_type": "missing_detail", "trigger_signals": ["RoPE", "二维"]},
    {"question": "长上下文扩展时，RoPE 为什么经常成为瓶颈？", "trigger_type": "missing_analysis", "trigger_signals": ["长上下文"]}
  ],
  "retrieval_text": "算法工程师位置编码题，考察绝对位置、相对位置、RoPE 原理、优缺点和长上下文应用。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_004",
  "role": "算法工程师",
  "question": "RAG 的整体流程是什么？用户输入后是不是应该直接召回？",
  "category": "大模型/算法工程",
  "subcategory": "RAG基础",
  "competency": ["rag_system", "retrieval_engineering"],
  "difficulty": "简单",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["RAG", "召回", "query rewrite", "重排"],
  "tags": ["真实面经", "算法工程师", "RAG", "应用开发"],
  "answer_summary": "需要说明文档清洗、切分、索引、查询理解、召回、重排、上下文拼装和生成的完整链路，并强调很多场景下不能把原始问题直接拿去召回。",
  "key_points": ["离线阶段包括清洗、切分和索引", "在线阶段包括查询理解、召回、重排和生成", "原始 query 可能存在噪声、指代和多轮上下文问题", "需要 query rewrite 或检索路由", "效果评估要看命中率和最终回答质量"],
  "optional_points": ["可补充 GraphRAG 与传统向量RAG差异", "可补充权限过滤和时效性处理"],
  "expected_answer_signals": ["切分", "召回", "重排"],
  "common_mistakes": ["只讲向量检索，不讲重排", "默认用户输入可以直接召回"],
  "scoring_rubric": {
    "basic": ["能说明 RAG 主流程"],
    "good": ["能解释 query 改写和重排的重要性"],
    "excellent": ["能结合多轮对话和评估闭环给出完整答案"]
  },
  "followups": [
    {"question": "如果问题很模糊，你会在召回前做哪些 query 处理？", "trigger_type": "missing_detail", "trigger_signals": ["召回"]},
    {"question": "GraphRAG 和传统向量 RAG 分别适合什么场景？", "trigger_type": "missing_point", "trigger_signals": ["GraphRAG", "RAG"]}
  ],
  "retrieval_text": "RAG 基础流程题，考察离线构建、在线召回、重排、query rewrite 和为什么不能总是直接召回。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_001",
  "role": "算法工程师",
  "question": "PPO、DPO、GRPO、DAPO、GSPO 分别是什么？它们的核心区别、适用场景和工程问题有哪些？",
  "category": "大模型/算法工程",
  "subcategory": "强化学习与对齐",
  "competency": ["rlhf", "llm_alignment"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["PPO", "DPO", "GRPO", "DAPO", "GSPO"],
  "tags": ["真实面经", "算法工程师", "后训练", "强化学习"],
  "answer_summary": "需要从是否依赖奖励模型、是否基于偏好数据、训练稳定性、样本效率、显存成本和实现复杂度等角度比较这些对齐算法。",
  "key_points": ["PPO是经典RLHF方案，依赖策略更新与约束", "DPO偏向离线偏好优化", "GRPO/GSPO强调群组相对比较", "不同方法在样本效率和成本上权衡不同", "工程落地要考虑奖励来源和训练稳定性"],
  "optional_points": ["可补充各方法常见失败模式", "可结合项目说明为什么最终选某一种"],
  "expected_answer_signals": ["偏好优化", "KL约束", "样本效率"],
  "common_mistakes": ["只会罗列缩写，不会比较差异", "忽略数据条件和系统成本"],
  "scoring_rubric": {
    "basic": ["能说清 PPO、DPO、GRPO 等基本定位"],
    "good": ["能比较训练目标、数据依赖和适用场景"],
    "excellent": ["能结合工程成本和项目经验说明取舍"]
  },
  "followups": [
    {"question": "如果偏好数据不多且算力也有限，你更倾向于选哪种方法？为什么？", "trigger_type": "missing_analysis", "trigger_signals": ["DPO", "PPO"]},
    {"question": "GRPO/GSPO 在大模型里通常如何组织一组候选输出？", "trigger_type": "missing_detail", "trigger_signals": ["GRPO", "GSPO"]}
  ],
  "retrieval_text": "算法工程师后训练高频题，考察 PPO DPO GRPO DAPO GSPO 的区别、适用场景与工程问题。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_002",
  "role": "算法工程师",
  "question": "PPO 的损失函数包含哪些部分？ratio、advantage、returns 和 GAE 分别是什么意思？",
  "category": "大模型/算法工程",
  "subcategory": "强化学习与对齐",
  "competency": ["rlhf", "llm_alignment"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["PPO", "ratio", "advantage", "returns", "GAE"],
  "tags": ["真实面经", "算法工程师", "PPO", "强化学习"],
  "answer_summary": "需要系统解释 policy loss、value loss、entropy bonus、clip/KL 约束，并说明 ratio、advantage、returns 和 GAE 的含义及它们在流程中的关系。",
  "key_points": ["ratio表示新旧策略概率比", "advantage反映动作相对基线的好坏", "returns描述目标回报", "GAE是折中偏差与方差的优势估计", "PPO核心是限制策略更新幅度"],
  "optional_points": ["可补充为什么 λ 常取 0.95", "可说明 token 级与 sequence 级 advantage 的差异"],
  "expected_answer_signals": ["clip", "advantage", "value loss"],
  "common_mistakes": ["只会背公式，不会解释含义", "把 returns 和 advantage 混为一谈"],
  "scoring_rubric": {
    "basic": ["能说出 PPO 的主要损失项"],
    "good": ["能解释 ratio、advantage、returns、GAE 的关系"],
    "excellent": ["能联系大模型 RLHF 讲清实现细节"]
  },
  "followups": [
    {"question": "为什么 PPO 需要 clip？如果不 clip 会怎样？", "trigger_type": "missing_point", "trigger_signals": ["clip", "ratio"]},
    {"question": "如果 KL 系数太大或太小，训练会分别出现什么现象？", "trigger_type": "missing_detail", "trigger_signals": ["KL", "PPO"]}
  ],
  "retrieval_text": "PPO 细节题，考察 PPO 损失组成、ratio、advantage、returns、GAE 以及大模型中的计算方式。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_003",
  "role": "算法工程师",
  "question": "Qwen3-Embedding、BM25、BGE-M3 这类召回方式有什么区别？RRF 融合和 Rerank 各自解决什么问题？",
  "category": "大模型/算法工程",
  "subcategory": "RAG检索优化",
  "competency": ["rag_system", "retrieval_engineering"],
  "difficulty": "中等",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Embedding", "BM25", "BGE-M3", "RRF", "Rerank"],
  "tags": ["真实面经", "算法工程师", "RAG", "检索"],
  "answer_summary": "需要从稀疏召回、稠密召回和多向量召回的原理与适用场景切入，再说明 RRF 用于多路结果融合，Rerank 用于高精度精排。",
  "key_points": ["BM25擅长关键词精确匹配", "Embedding擅长语义相似", "BGE-M3兼顾多粒度表示", "RRF用于融合多路召回减少偏差", "Rerank负责最终精排提升上下文质量"],
  "optional_points": ["可补充 query rewrite 与 chunk 粒度影响", "可说明 cross-encoder 为什么适合做重排"],
  "expected_answer_signals": ["稀疏召回", "稠密召回", "重排"],
  "common_mistakes": ["把 RRF 和 Rerank 混为一谈", "只说某个模型好，不解释适用场景"],
  "scoring_rubric": {
    "basic": ["能区分 BM25、向量召回和重排"],
    "good": ["能解释 RRF 与 Rerank 的不同职责"],
    "excellent": ["能结合系统成本设计多路检索策略"]
  },
  "followups": [
    {"question": "如果向量召回和 BM25 结果冲突很大，你会如何分析和调参？", "trigger_type": "missing_analysis", "trigger_signals": ["BM25", "RRF"]},
    {"question": "既然已经有相似度分数，为什么还要引入 cross-encoder 做 Rerank？", "trigger_type": "missing_detail", "trigger_signals": ["Rerank"]}
  ],
  "retrieval_text": "RAG 检索优化题，考察 BM25、Embedding、BGE-M3、RRF 融合与 Rerank 的差异和作用。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_004",
  "role": "算法工程师",
  "question": "LoRA 和 QLoRA 有什么区别？在微调训练过程中，batch_size、seq_len 和 OOM 问题通常如何权衡？",
  "category": "大模型/算法工程",
  "subcategory": "训练工程",
  "competency": ["training_optimization", "parameter_efficient_finetuning"],
  "difficulty": "中等",
  "question_type": "训练工程",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["LoRA", "QLoRA", "batch_size", "seq_len", "OOM"],
  "tags": ["真实面经", "算法工程师", "微调", "训练工程"],
  "answer_summary": "回答应先说明 LoRA 与 QLoRA 的核心思路，再结合显存构成分析 batch_size、seq_len、梯度累计、混合精度、checkpoint 等常见权衡和 OOM 处理办法。",
  "key_points": ["LoRA通过低秩适配减少可训练参数", "QLoRA通过量化底座模型进一步省显存", "batch_size 和 seq_len 都会显著影响激活开销", "OOM 常见处理包括梯度累计、checkpoint 和降精度", "调参时要同时考虑吞吐、稳定性和效果"],
  "optional_points": ["可补充 target modules、rank、alpha 的选择", "可说明 packing 和长短样本混合策略"],
  "expected_answer_signals": ["量化", "显存", "梯度累计"],
  "common_mistakes": ["只说 QLoRA 更省显存，不解释为什么", "OOM 只会回答减 batch_size"],
  "scoring_rubric": {
    "basic": ["能说明 LoRA 和 QLoRA 的基本区别"],
    "good": ["能说明 batch_size、seq_len 与显存的关系"],
    "excellent": ["能给出较完整的 OOM 排查与调优策略"]
  },
  "followups": [
    {"question": "如果显存预算固定但必须支持更长上下文，你会优先牺牲哪些训练配置？", "trigger_type": "missing_analysis", "trigger_signals": ["seq_len", "OOM"]},
    {"question": "LoRA 的 target modules 和 rank 一般如何选择？", "trigger_type": "missing_detail", "trigger_signals": ["LoRA"]}
  ],
  "retrieval_text": "大模型微调工程题，考察 LoRA、QLoRA、batch_size、seq_len 和 OOM 处理权衡。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_001",
  "role": "算法工程师",
  "question": "Agent 中的 skills、MCP、短期记忆、长期记忆、ReAct、CoT、ToT 分别是什么？它们在系统里如何协同？",
  "category": "大模型/算法工程",
  "subcategory": "Agent系统",
  "competency": ["agent_system", "rag_system", "system_design"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Agent", "skills", "MCP", "memory", "ReAct", "ToT"],
  "tags": ["真实面经", "算法工程师", "Agent", "应用开发"],
  "answer_summary": "回答应先区分 Agent 的工具、协议、记忆与推理范式，再说明 skills 更像能力封装、MCP 更像标准化接入协议，以及短期和长期记忆、ReAct、CoT、ToT 的协同方式。",
  "key_points": ["skills是能力或流程的可复用封装", "MCP用于标准化外部资源和工具接入", "短期记忆偏会话态，长期记忆偏可检索持久化知识", "ReAct强调边思考边行动，ToT强调多路径搜索", "系统设计要考虑成本、上下文预算和失败回退"],
  "optional_points": ["可补充 workflow 与 agent 的区别", "可补充工具超时或空结果时的降级策略"],
  "expected_answer_signals": ["协议", "记忆", "推理范式"],
  "common_mistakes": ["把 skills 与 MCP 当成同一个概念", "只讲概念，不说明系统里如何协同"],
  "scoring_rubric": {
    "basic": ["能区分 Agent 中常见组件和概念"],
    "good": ["能说明短期记忆、长期记忆和工具协议的关系"],
    "excellent": ["能结合故障处理、上下文预算和编排策略给出系统化答案"]
  },
  "followups": [
    {"question": "workflow 和 agent 的边界在哪里？什么场景更适合 workflow？", "trigger_type": "missing_point", "trigger_signals": ["workflow", "Agent"]},
    {"question": "如果工具调用超时或参数解析失败，你会如何设计反馈链路？", "trigger_type": "missing_detail", "trigger_signals": ["工具调用", "Agent"]}
  ],
  "retrieval_text": "Agent 系统设计题，考察 skills、MCP、记忆机制、ReAct、CoT、ToT 及其协同方式。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_002",
  "role": "算法工程师",
  "question": "如果要把模型上下文长度扩展到 1000K，你会从哪些方面设计方案？主要难点和资源估算方式是什么？",
  "category": "大模型/算法工程",
  "subcategory": "长上下文建模",
  "competency": ["long_context", "training_optimization", "system_design"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["长上下文", "1000K", "RoPE", "显存", "算力估算"],
  "tags": ["真实面经", "算法工程师", "长文本", "系统设计"],
  "answer_summary": "回答应覆盖位置编码外推、注意力复杂度、数据构造、阶段式训练、显存热点、算力估算和评估策略，强调 1000K 不是只改一个 max_length。",
  "key_points": ["需要同时考虑架构外推和训练分阶段策略", "注意力复杂度、KV Cache 和激活保存是主要瓶颈", "RoPE 与注意力机制通常要联动调整", "显存估算要分参数、优化器、激活和通信开销", "评估要看长上下文检索、跨段推理和稳定性"],
  "optional_points": ["可补充 needle-in-a-haystack 等评测", "可说明训练和推理阶段的瓶颈差异"],
  "expected_answer_signals": ["位置编码外推", "复杂度瓶颈", "阶段训练"],
  "common_mistakes": ["把长上下文扩展理解成只增加窗口参数", "只谈算法，不谈显存和算力预算"],
  "scoring_rubric": {
    "basic": ["能说出长上下文扩展会遇到注意力和显存问题"],
    "good": ["能从架构、训练和评估三个层面展开"],
    "excellent": ["能给出资源估算、阶段方案和实际风险"]
  },
  "followups": [
    {"question": "训练到 1000K 时，显存最容易在哪几个部分暴涨？", "trigger_type": "missing_detail", "trigger_signals": ["显存", "1000K"]},
    {"question": "如果只能分阶段扩窗口，你会怎样设计 curriculum？", "trigger_type": "missing_analysis", "trigger_signals": ["阶段训练", "长上下文"]}
  ],
  "retrieval_text": "长上下文系统设计题，考察 1000K 上下文扩展方案、显存与算力估算、位置编码和评估设计。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_003",
  "role": "算法工程师",
  "question": "FlashAttention、DP/TP/PP、FSDP、ZeRO 这些训练与推理优化方案分别解决什么问题？你会如何组合它们？",
  "category": "大模型/算法工程",
  "subcategory": "系统优化与并行",
  "competency": ["training_optimization", "distributed_system"],
  "difficulty": "困难",
  "question_type": "训练工程",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["FlashAttention", "DP", "TP", "PP", "FSDP", "ZeRO"],
  "tags": ["真实面经", "算法工程师", "并行训练", "系统优化"],
  "answer_summary": "回答应先分别说明算子级优化、数据并行、张量并行、流水并行、参数切分的作用，再根据模型大小、序列长度和集群拓扑说明组合策略。",
  "key_points": ["FlashAttention主要优化注意力算子的显存和访存效率", "DP、TP、PP 分别解决不同维度的切分问题", "FSDP/ZeRO通过分片参数、梯度和优化器状态降显存", "组合方式取决于模型规模、序列长度和带宽", "不同方案的通信成本和调试复杂度差异很大"],
  "optional_points": ["可补充 hybrid engine 或 auto mapping 思路", "可说明训练和推理侧并行方式的差异"],
  "expected_answer_signals": ["算子优化", "并行切分", "通信成本"],
  "common_mistakes": ["只会背术语，不知道各方案切分对象", "忽视通信开销和集群拓扑"],
  "scoring_rubric": {
    "basic": ["能区分 FlashAttention、DP、TP、PP、FSDP、ZeRO 的基本作用"],
    "good": ["能根据场景说明组合方式和权衡"],
    "excellent": ["能结合显存、带宽和吞吐给出完整方案"]
  },
  "followups": [
    {"question": "如果瓶颈主要是 attention 显存而不是参数显存，你会优先动哪些方案？", "trigger_type": "missing_analysis", "trigger_signals": ["FlashAttention", "显存"]},
    {"question": "ZeRO-1、2、3 和 FSDP 的本质差异是什么？", "trigger_type": "missing_detail", "trigger_signals": ["ZeRO", "FSDP"]}
  ],
  "retrieval_text": "大模型系统优化题，考察 FlashAttention、DP/TP/PP、FSDP、ZeRO 的职责与组合策略。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_004",
  "role": "算法工程师",
  "question": "请手写多头注意力机制，或解释从数学公式到工程实现时最容易踩坑的地方有哪些。",
  "category": "大模型/算法工程",
  "subcategory": "编程实现",
  "competency": ["coding", "deep_learning", "model_implementation"],
  "difficulty": "困难",
  "question_type": "编程实现",
  "round_type": "technical",
  "question_intent": "coding",
  "keywords": ["多头注意力", "MHA", "mask", "shape"],
  "tags": ["真实面经", "算法工程师", "手撕代码", "Transformer"],
  "answer_summary": "这题既考察公式理解，也考察工程实现细节。需要说明线性投影、reshape/split head、mask、缩放、softmax、concat 和输出映射的完整流程。",
  "key_points": ["要明确 Q、K、V 的输入输出维度", "split head 和 transpose 的 shape 变化必须清楚", "mask 的形状与广播规则常见出错", "需要做缩放和数值稳定处理", "实现时还要关注 causal mask 和 mixed precision"],
  "optional_points": ["可补充 KV Cache 场景下的增量推理实现", "可说明如何从 MHA 演化到 GQA/MQA"],
  "expected_answer_signals": ["shape", "mask", "缩放"],
  "common_mistakes": ["只会写公式，不会落到张量形状", "mask 维度和广播关系处理错误"],
  "scoring_rubric": {
    "basic": ["能写出多头注意力主流程"],
    "good": ["能处理好 shape 变换、mask 和缩放"],
    "excellent": ["能结合工程细节解释常见坑位和优化方向"]
  },
  "followups": [
    {"question": "如果改成 causal self-attention，需要额外注意什么？", "trigger_type": "missing_detail", "trigger_signals": ["mask", "causal"]},
    {"question": "如果线上要支持 KV Cache，这段实现会发生哪些变化？", "trigger_type": "missing_analysis", "trigger_signals": ["KV Cache", "推理"]}
  ],
  "retrieval_text": "算法工程师手撕大模型代码题，考察多头注意力从公式到实现的完整链路和常见坑点。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_005",
  "role": "算法工程师",
  "question": "vLLM 是怎么实现推理加速的？它和普通 HuggingFace 推理链路相比核心优化点在哪里？",
  "category": "大模型/算法工程",
  "subcategory": "推理优化",
  "competency": ["llm_inference", "system_design"],
  "difficulty": "简单",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["vLLM", "PagedAttention", "KV Cache", "推理加速"],
  "tags": ["真实面经", "算法工程师", "推理优化", "大模型"],
  "answer_summary": "需要说明 vLLM 通过更高效的 KV Cache 管理、连续批处理和调度优化提升吞吐，核心不是只换了一个框架，而是针对 LLM 推理中的内存碎片和批处理效率做了系统优化。",
  "key_points": ["PagedAttention 改善 KV Cache 内存管理", "连续批处理提升 GPU 利用率", "调度策略减少请求间浪费", "吞吐和时延之间需要平衡", "适合多请求并发和长上下文推理场景"],
  "optional_points": ["可补充 speculative decoding 或 prefix cache", "可说明与 TensorRT-LLM 等方案的差异"],
  "expected_answer_signals": ["KV Cache", "批处理", "吞吐"],
  "common_mistakes": ["只说 vLLM 更快，不解释为什么", "把优化点全归因于 CUDA 算子"],
  "scoring_rubric": {
    "basic": ["能说明 vLLM 是为 LLM 推理优化的框架"],
    "good": ["能解释 KV Cache 和批处理优化"],
    "excellent": ["能结合并发场景和吞吐时延权衡展开"]
  },
  "followups": [
    {"question": "PagedAttention 主要解决了传统 KV Cache 的什么问题？", "trigger_type": "missing_detail", "trigger_signals": ["PagedAttention", "KV Cache"]},
    {"question": "如果线上请求长度差异很大，vLLM 的调度为什么更有优势？", "trigger_type": "missing_analysis", "trigger_signals": ["调度", "吞吐"]}
  ],
  "retrieval_text": "大模型推理优化题，考察 vLLM、PagedAttention、KV Cache 管理和连续批处理。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_006",
  "role": "算法工程师",
  "question": "GraphRAG 是怎么做检索的？它和普通向量检索型 RAG 的区别是什么？",
  "category": "大模型/算法工程",
  "subcategory": "RAG检索优化",
  "competency": ["rag_system", "retrieval_engineering", "knowledge_graph"],
  "difficulty": "简单",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["GraphRAG", "知识图谱", "实体关系", "向量检索"],
  "tags": ["真实面经", "算法工程师", "RAG", "GraphRAG"],
  "answer_summary": "需要解释 GraphRAG 会先抽取实体和关系形成图结构，再结合图遍历或子图检索组织上下文；它更擅长多跳关系和结构化知识，而传统向量 RAG 更擅长语义相似召回。",
  "key_points": ["GraphRAG 依赖实体关系抽取和图构建", "检索时通常会做实体定位和子图扩展", "更适合多跳推理和结构化知识场景", "传统向量 RAG 更偏语义相似匹配", "两者也可以混合使用"],
  "optional_points": ["可补充图构建成本和更新难题", "可说明图遍历与重排如何配合"],
  "expected_answer_signals": ["实体关系", "多跳推理", "子图"],
  "common_mistakes": ["把 GraphRAG 说成只是多加一个数据库", "忽视图构建和维护成本"],
  "scoring_rubric": {
    "basic": ["能区分 GraphRAG 与普通向量 RAG"],
    "good": ["能说明图构建和多跳检索流程"],
    "excellent": ["能结合适用场景和系统成本给出取舍建议"]
  },
  "followups": [
    {"question": "如果知识不断更新，GraphRAG 的图维护会遇到哪些挑战？", "trigger_type": "missing_detail", "trigger_signals": ["GraphRAG", "更新"]},
    {"question": "你会如何设计 GraphRAG 和向量检索混合链路？", "trigger_type": "missing_analysis", "trigger_signals": ["向量检索", "混合"]}
  ],
  "retrieval_text": "GraphRAG 基础题，考察实体关系图检索、多跳推理和与传统向量 RAG 的差异。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_simple_007",
  "role": "算法工程师",
  "question": "ROC、PR、AUC、GAUC、DCG、NDCG 分别是什么？为什么线上不能只看 GAUC？",
  "category": "大模型/算法工程",
  "subcategory": "评估指标",
  "competency": ["machine_learning", "evaluation"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["ROC", "PR", "AUC", "GAUC", "NDCG"],
  "tags": ["真实面经", "算法工程师", "评估指标", "排序"],
  "answer_summary": "需要说明 ROC/PR 曲线定义、AUC 的排序含义、GAUC 的分组加权思想，以及 DCG/NDCG 对位置敏感的特点，并解释线上仍需结合 AUC、业务指标和分桶分析。",
  "key_points": ["AUC衡量整体排序能力", "GAUC按用户或group加权更适合推荐场景", "PR 在样本不平衡时更敏感", "DCG/NDCG 更关注排序位置", "线上还要结合 CTR/CVR 等业务结果"],
  "optional_points": ["可补充 AUC 与校准能力不同", "可说明长尾用户对 GAUC 的影响"],
  "expected_answer_signals": ["排序能力", "分组加权", "位置敏感"],
  "common_mistakes": ["把所有指标混成一类", "认为 GAUC 高就一定线上效果最好"],
  "scoring_rubric": {
    "basic": ["能说清主要指标的定义"],
    "good": ["能解释不同指标对应的问题类型"],
    "excellent": ["能联系线上业务和分布差异说明指标选择"]
  },
  "followups": [
    {"question": "在极度不平衡样本场景下，为什么 PR 常比 ROC 更有解释力？", "trigger_type": "missing_analysis", "trigger_signals": ["PR", "ROC"]},
    {"question": "GAUC 的局限性主要体现在哪些线上场景？", "trigger_type": "missing_detail", "trigger_signals": ["GAUC"]}
  ],
  "retrieval_text": "算法工程师指标题，考察 ROC、PR、AUC、GAUC、DCG、NDCG 的区别和线上使用边界。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_005",
  "role": "算法工程师",
  "question": "SFT 的 loss 是怎么计算的？它和 DPO、PPO 这类后训练目标有什么本质差别？",
  "category": "大模型/算法工程",
  "subcategory": "监督微调与后训练",
  "competency": ["sft", "llm_alignment"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["SFT", "cross entropy", "DPO", "PPO", "后训练"],
  "tags": ["真实面经", "算法工程师", "SFT", "对齐训练"],
  "answer_summary": "回答应说明 SFT 主要是对参考答案做 teacher forcing 的 token-level 交叉熵优化，而 DPO/PPO 关注偏好或奖励信号，本质区别在于监督信号来源和优化目标不同。",
  "key_points": ["SFT 通常是 next-token 交叉熵损失", "SFT 偏向学习示范分布", "DPO/PPO 偏向做偏好或奖励对齐", "SFT 更稳定但未必最符合人类偏好", "常见训练流程是 SFT 在前、偏好优化在后"],
  "optional_points": ["可补充 label masking 和 prompt-only 部分是否参与loss", "可说明为什么只靠 SFT 往往不够"],
  "expected_answer_signals": ["teacher forcing", "交叉熵", "偏好优化"],
  "common_mistakes": ["把 SFT 和 DPO/PPO 说成只是不同数据集", "不解释监督信号差异"],
  "scoring_rubric": {
    "basic": ["能说明 SFT 的损失形式"],
    "good": ["能对比 SFT 与 DPO/PPO 的目标差异"],
    "excellent": ["能结合训练链路和稳定性分析给出完整解释"]
  },
  "followups": [
    {"question": "指令微调时，prompt 部分的 token 一般是否参与 loss？为什么？", "trigger_type": "missing_detail", "trigger_signals": ["SFT", "loss"]},
    {"question": "为什么很多模型即便做了大量 SFT，仍然还要继续做偏好优化？", "trigger_type": "missing_analysis", "trigger_signals": ["DPO", "PPO"]}
  ],
  "retrieval_text": "SFT 基础题，考察 SFT 的交叉熵损失以及与 DPO、PPO 等后训练目标的差异。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_006",
  "role": "算法工程师",
  "question": "Sequence 级别与 token 级别的强化学习训练有什么区别？各自更适合哪些场景？",
  "category": "大模型/算法工程",
  "subcategory": "强化学习与对齐",
  "competency": ["rlhf", "llm_alignment"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["sequence-level", "token-level", "RLHF", "advantage"],
  "tags": ["真实面经", "算法工程师", "后训练", "强化学习"],
  "answer_summary": "需要说明 token 级方法更细粒度、信用分配更充分，而 sequence 级方法实现更直接、常用于整段输出质量评估；两者在奖励设计、方差和工程复杂度上各有权衡。",
  "key_points": ["token 级训练能提供更细粒度反馈", "sequence 级训练更贴近整体回答评分", "两者的 credit assignment 难度不同", "token 级通常实现更复杂、方差控制更难", "要根据奖励来源和任务粒度来选"],
  "optional_points": ["可补充 reward shaping 方法", "可说明 sequence 奖励如何回传到 token"],
  "expected_answer_signals": ["粒度", "credit assignment", "奖励设计"],
  "common_mistakes": ["只说一个按 token 一个按句子，没有解释训练影响", "忽略方差和信用分配问题"],
  "scoring_rubric": {
    "basic": ["能区分 sequence 级与 token 级训练"],
    "good": ["能解释它们在奖励和信用分配上的差异"],
    "excellent": ["能结合任务场景说明为什么选某一种"]
  },
  "followups": [
    {"question": "如果奖励只来自整段回答评分，token 级 advantage 一般如何构造？", "trigger_type": "missing_detail", "trigger_signals": ["token-level", "advantage"]},
    {"question": "数学推理和通用对话场景里，你会更倾向哪一类训练方式？为什么？", "trigger_type": "missing_analysis", "trigger_signals": ["sequence-level", "token-level"]}
  ],
  "retrieval_text": "强化学习细节题，考察 sequence 级与 token 级训练的区别、信用分配和适用场景。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_007",
  "role": "算法工程师",
  "question": "Qwen3 或类似 MoE 大模型架构做了哪些关键改进？专家网络一般是怎么工作的？",
  "category": "大模型/算法工程",
  "subcategory": "模型架构进阶",
  "competency": ["model_architecture", "llm_foundation"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Qwen3", "MoE", "专家网络", "路由"],
  "tags": ["真实面经", "算法工程师", "模型架构", "MoE"],
  "answer_summary": "回答应从 MoE 的路由、专家选择、负载均衡、激活参数量与总参数量差异出发，说明这类架构为什么能在成本可控的情况下提升容量与性能。",
  "key_points": ["MoE 通过门控路由只激活部分专家", "总参数量和激活参数量不同", "专家网络通常放在 FFN 位置", "需要做负载均衡避免专家塌缩", "架构改进往往还会配合注意力、位置编码和训练策略优化"],
  "optional_points": ["可补充 Top-k 路由和容量限制", "可结合 DeepSeek-V3、Qwen 等公开技术报告说明"],
  "expected_answer_signals": ["路由", "激活参数", "负载均衡"],
  "common_mistakes": ["只说 MoE 更大更强，不说明工作机制", "不知道专家一般替换的是哪一层"],
  "scoring_rubric": {
    "basic": ["能解释 MoE 的基本思想"],
    "good": ["能说明路由、负载均衡和成本优势"],
    "excellent": ["能结合公开模型架构细节展开分析"]
  },
  "followups": [
    {"question": "MoE 为什么会出现专家塌缩？如何缓解？", "trigger_type": "missing_detail", "trigger_signals": ["MoE", "负载均衡"]},
    {"question": "MoE 在推理侧通常会遇到哪些额外系统挑战？", "trigger_type": "missing_analysis", "trigger_signals": ["推理", "专家网络"]}
  ],
  "retrieval_text": "模型架构进阶题，考察 Qwen3/MoE 架构、专家路由和负载均衡原理。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_008",
  "role": "算法工程师",
  "question": "多模态大模型里的 Q-Former 或交叉注意力模块为什么重要？如果视觉 token 很多，你会如何压缩与对齐？",
  "category": "大模型/算法工程",
  "subcategory": "多模态建模",
  "competency": ["multimodal", "model_architecture"],
  "difficulty": "中等",
  "question_type": "算法原理",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Q-Former", "cross attention", "视觉 token", "对齐"],
  "tags": ["真实面经", "算法工程师", "多模态", "架构设计"],
  "answer_summary": "这类题要说明桥接模块的作用不仅是投影维度，更重要的是做信息选择、压缩和对齐；当视觉 token 很多时，需要兼顾保真度、成本和下游任务需求。",
  "key_points": ["Q-Former 可用少量 query 提取视觉关键信息", "cross attention 是模态对齐的重要手段", "视觉 token 过多会带来上下文和算力压力", "常见做法包括 token pooling、learnable query、分层压缩", "压缩策略要兼顾下游任务效果"],
  "optional_points": ["可补充视频场景的时间维压缩", "可说明不同桥接方案的取舍"],
  "expected_answer_signals": ["压缩", "对齐", "跨注意力"],
  "common_mistakes": ["把桥接层看成纯线性层", "忽视视觉 token 数量带来的系统成本"],
  "scoring_rubric": {
    "basic": ["能说明 Q-Former 或 cross attention 的基本作用"],
    "good": ["能解释视觉 token 压缩与对齐问题"],
    "excellent": ["能结合成本和任务效果设计合理方案"]
  },
  "followups": [
    {"question": "如果是视频多模态，时间维上的压缩会怎么设计？", "trigger_type": "missing_detail", "trigger_signals": ["视频", "压缩"]},
    {"question": "为什么很多场景不直接把全部视觉 token 喂给 LLM？", "trigger_type": "missing_analysis", "trigger_signals": ["视觉 token", "LLM"]}
  ],
  "retrieval_text": "多模态进阶题，考察 Q-Former、交叉注意力、视觉 token 压缩与模态对齐。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_mid_009",
  "role": "算法工程师",
  "question": "Prompt 好坏应该怎么评估？如果工具调用超时或返回空值，你会如何设计 Prompt 和反馈链路？",
  "category": "大模型/算法工程",
  "subcategory": "Prompt与Agent应用",
  "competency": ["agent_system", "evaluation", "prompt_engineering"],
  "difficulty": "中等",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Prompt", "工具调用", "超时", "反馈链路"],
  "tags": ["真实面经", "算法工程师", "Prompt", "Agent"],
  "answer_summary": "回答应说明 Prompt 评估不能只靠主观感觉，需要结合任务成功率、结构化约束遵守率、工具调用正确率和用户体验指标；异常场景下还要设计清晰的降级反馈和恢复策略。",
  "key_points": ["Prompt 评估要看任务成功率和稳定性", "可以结合离线case集与线上行为数据", "工具超时或空值需要有明确降级文案", "要避免模型编造工具结果", "反馈链路要兼顾可理解性和下一步行动建议"],
  "optional_points": ["可补充 A/B 测试和人工评审", "可说明 prompt 版本管理方法"],
  "expected_answer_signals": ["成功率", "降级", "异常处理"],
  "common_mistakes": ["把 Prompt 评估等同于主观好不好看", "异常时只会说重试，没有用户反馈策略"],
  "scoring_rubric": {
    "basic": ["能说出 Prompt 评估要看结果而非主观感觉"],
    "good": ["能说明工具异常场景下的处理策略"],
    "excellent": ["能给出可落地的评估指标和反馈链路设计"]
  },
  "followups": [
    {"question": "如果模型频繁在工具失败后编造答案，你会如何约束？", "trigger_type": "missing_analysis", "trigger_signals": ["工具调用", "编造"]},
    {"question": "Prompt 的离线评测集应该如何构建，才能比较不同版本？", "trigger_type": "missing_detail", "trigger_signals": ["Prompt", "评测"]}
  ],
  "retrieval_text": "Prompt 与 Agent 应用题，考察 Prompt 评估、工具调用失败处理和用户反馈设计。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_005",
  "role": "算法工程师",
  "question": "增量预训练中的“增量”具体指什么？数据闭环、自动化评分和模型迭代应该如何设计成一套体系？",
  "category": "大模型/算法工程",
  "subcategory": "数据与评估体系",
  "competency": ["pretraining", "evaluation", "data_engineering"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["增量预训练", "数据闭环", "自动化评分", "模型迭代"],
  "tags": ["真实面经", "算法工程师", "数据工程", "模型评估"],
  "answer_summary": "需要说明增量预训练如何在已有底座模型上继续吸收新知识，同时通过自动化评分和数据闭环识别高价值样本、回流训练并监控灾难性遗忘。",
  "key_points": ["增量预训练是基于已有底座继续训练新分布数据", "要控制灾难性遗忘和分布漂移", "自动化评分用于发现失败样本与薄弱能力", "数据闭环强调采集、清洗、筛选、回流和复盘", "最终目标是支持稳定迭代而非一次性调优"],
  "optional_points": ["可补充线上 A/B 与离线评估协同", "可说明数据筛选标准和难例挖掘"],
  "expected_answer_signals": ["灾难性遗忘", "失败样本回流", "评估闭环"],
  "common_mistakes": ["把增量预训练理解成简单追加数据训练", "只讲评分指标，不讲如何驱动迭代"],
  "scoring_rubric": {
    "basic": ["能说明增量预训练和数据闭环的基本概念"],
    "good": ["能描述评分、样本筛选和迭代回流的主流程"],
    "excellent": ["能结合风险控制和线上验证给出完整设计"]
  },
  "followups": [
    {"question": "什么样的数据更值得进入数据闭环？筛选标准应该如何定义？", "trigger_type": "missing_detail", "trigger_signals": ["数据闭环", "筛选"]},
    {"question": "如果自动化评分与人工判断差异很大，你会如何校准体系？", "trigger_type": "missing_analysis", "trigger_signals": ["评分", "校准"]}
  ],
  "retrieval_text": "模型迭代体系题，考察增量预训练、数据闭环、自动化评分与持续优化设计。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_006",
  "role": "算法工程师",
  "question": "如果一个 RAG 系统存在多轮对话，你会从哪些方面提升模型的上下文能力，避免检索和回答脱节？",
  "category": "大模型/算法工程",
  "subcategory": "RAG多轮对话",
  "competency": ["rag_system", "retrieval_engineering", "agent_system"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["多轮对话", "RAG", "上下文能力", "query rewrite"],
  "tags": ["真实面经", "算法工程师", "RAG", "多轮对话"],
  "answer_summary": "回答应围绕会话状态建模、query rewrite、历史压缩、记忆选择、检索路由和答案一致性控制展开，重点说明多轮场景中不能把每一轮都当成独立 query。",
  "key_points": ["多轮对话需要显式维护会话状态", "要区分哪些历史信息应该进检索、哪些只用于生成", "query rewrite 和指代消解非常关键", "可以做会话摘要、长期记忆和短期窗口结合", "还要关注上下文污染、时效性和回答一致性"],
  "optional_points": ["可补充 session memory 与向量记忆结合", "可说明多轮场景的评估方法"],
  "expected_answer_signals": ["会话状态", "指代消解", "历史压缩"],
  "common_mistakes": ["把多轮问题直接拼接原文做召回", "忽略历史污染和时效性冲突"],
  "scoring_rubric": {
    "basic": ["能说明多轮场景比单轮多了会话状态问题"],
    "good": ["能提出 query rewrite、摘要和记忆机制"],
    "excellent": ["能系统设计检索、记忆和生成协同方案"]
  },
  "followups": [
    {"question": "如果历史中有语义相关但时间很久的信息，能不能直接用？你会如何判断？", "trigger_type": "missing_detail", "trigger_signals": ["历史信息", "时效性"]},
    {"question": "多轮 RAG 的离线评测集应该怎么构造，才能反映真实效果？", "trigger_type": "missing_analysis", "trigger_signals": ["多轮对话", "评测"]}
  ],
  "retrieval_text": "多轮 RAG 系统设计题，考察会话状态、query rewrite、历史压缩和检索生成协同。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_007",
  "role": "算法工程师",
  "question": "Rerank 的 Top-K 应该怎么定？长文档切片粒度和重排有效性通常怎么评估？",
  "category": "大模型/算法工程",
  "subcategory": "RAG检索优化",
  "competency": ["rag_system", "retrieval_engineering", "evaluation"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Rerank", "Top-K", "切片粒度", "评估"],
  "tags": ["真实面经", "算法工程师", "RAG", "检索评估"],
  "answer_summary": "需要说明 Top-K 不是拍脑袋定的，而要结合召回覆盖率、重排成本、上下文窗口和最终回答质量联合调节；同时切片粒度会直接影响召回和重排效果。",
  "key_points": ["Top-K 要结合召回覆盖率和重排成本一起看", "切片过细会丢上下文，过粗会稀释语义", "重排效果应评估命中率、NDCG、最终回答质量", "离线评估和线上反馈都很重要", "不同 query 类型可能需要不同 Top-K 策略"],
  "optional_points": ["可补充 dynamic top-k 或 query-aware chunking", "可说明 chunk overlap 的作用"],
  "expected_answer_signals": ["覆盖率", "成本", "切片粒度"],
  "common_mistakes": ["固定一个 Top-K 到处用", "只看检索相似度，不看最终回答效果"],
  "scoring_rubric": {
    "basic": ["能说明 Top-K 与切片粒度都会影响检索效果"],
    "good": ["能提出离线和线上联合评估方式"],
    "excellent": ["能结合 query 类型和系统预算设计动态策略"]
  },
  "followups": [
    {"question": "如果 chunk 很短导致召回命中但回答质量反而下降，你会怎么分析？", "trigger_type": "missing_analysis", "trigger_signals": ["切片粒度", "回答质量"]},
    {"question": "为什么向量检索已有相似度，还需要 Rerank 再筛一次？", "trigger_type": "missing_detail", "trigger_signals": ["Rerank", "相似度"]}
  ],
  "retrieval_text": "RAG 精排评估题，考察 Rerank Top-K、长文档切片粒度和检索效果评估方法。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
{
  "id": "algo_hard_008",
  "role": "算法工程师",
  "question": "如果你要解释一个项目的技术部分，应该怎样从业务出发点、技术方案、评估方式到落地效果讲清楚？",
  "category": "面试综合",
  "subcategory": "项目深挖",
  "competency": ["project_communication", "system_design", "evaluation"],
  "difficulty": "困难",
  "question_type": "项目实战",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["项目介绍", "业务出发点", "技术方案", "评估效果"],
  "tags": ["真实面经", "算法工程师", "项目深挖", "表达能力"],
  "answer_summary": "这类题本质是在看你是否能把项目讲成一个闭环：为什么做、数据和约束是什么、方案为什么这样选、如何评估、上线后产生了什么效果，以及还有哪些局限和迭代方向。",
  "key_points": ["先说业务背景和核心问题", "再说数据、约束和方案选型原因", "解释关键模块如何解决核心问题", "给出离线和线上评估方法与结果", "最后说明局限、风险和下一步优化方向"],
  "optional_points": ["可补充自己在团队中的具体贡献", "可说明替代方案为什么没选"],
  "expected_answer_signals": ["业务背景", "方案取舍", "评估结果"],
  "common_mistakes": ["直接堆技术名词，不讲业务目标", "只说做了什么，不说为什么这样做"],
  "scoring_rubric": {
    "basic": ["能按背景、方案、效果讲清项目主线"],
    "good": ["能解释关键技术选择与评估方法"],
    "excellent": ["能形成完整闭环并体现个人判断与取舍"]
  },
  "followups": [
    {"question": "如果面试官追问某一步为什么这么做而不是另一种方案，你会如何回答？", "trigger_type": "missing_analysis", "trigger_signals": ["方案选择", "取舍"]},
    {"question": "如果项目效果没有达到预期，你会优先从哪些层面排查？", "trigger_type": "missing_detail", "trigger_signals": ["评估", "效果"]}
  ],
  "retrieval_text": "项目深挖综合题，考察算法工程师如何从业务目标、技术方案、评估方式和落地结果完整讲清项目。",
  "source": "basic_knowledge/mianjing.md",
  "source_type": "面经整理"
}
