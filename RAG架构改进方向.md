如果你采用这版 schema，下一步就不要再把 RAG 当成“文本检索器”了，而要把它改成：

# **面向结构化面试单元的双通道 RAG**

也就是：

* 一条链路负责**找题**
* 一条链路负责**判题/追问**
* LLM 不直接决定流程，只负责表达

---

# 一句话先定版

你的新架构应该改成：

# **Interview-Oriented Modular RAG**

核心由 6 个部分组成：

1. **Schema Adapter**
2. **Question Index**
3. **Rubric Index**
4. **Interview State**
5. **Answer Analyzer**
6. **Response Generator**

---

# 先说你现在最需要改的，不是 Prompt，而是数据流

你现在旧架构大概是：

* JSON 题库
* embedding `retrieval_text`
* 向量召回
* 词法打分
* rerank
* 拼上下文给 LLM

如果换成你这个新 schema，建议改成下面这样。

---

# 一、先把“单索引”改成“二视图索引”

你现在一条题大概率只会进一个库，主召回文本还是 `retrieval_text`。
新 schema 下，不够了。

因为这份数据里其实混了两种用途：

## 用途 1：出题

要看这些字段：

* `question`
* `category`
* `subcategory`
* `competency`
* `difficulty`
* `question_type`
* `round_type`
* `question_intent`
* `keywords`
* `tags`

## 用途 2：判题 / 追问

要看这些字段：

* `answer_summary`
* `key_points`
* `optional_points`
* `expected_answer_signals`
* `common_mistakes`
* `scoring_rubric`
* `followups`

所以第一步不是“小修小补”，而是：

# **一条题生成两种索引文档**

---

## 1. Question Index

专门给“下一题选择”用。

### 索引内容建议

把这些字段拼成 question view：

```json id="qidx"
{
  "doc_id": "llm_001#question",
  "source_id": "llm_001",
  "view_type": "question",
  "role": "大模型算法工程师",
  "question": "Attention 机制的计算公式是什么？为什么要除以 dk？",
  "category": "Transformer 基础",
  "subcategory": "注意力机制",
  "competency": ["attention_formula", "scaled_dot_product_attention"],
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["Attention", "Transformer", "缩放点积", "dk", "softmax"],
  "tags": ["Transformer", "高频面试题", "基础概念"],
  "dense_text": "岗位：大模型算法工程师。题目：Attention 机制的计算公式是什么？为什么要除以 dk？类别：Transformer 基础 / 注意力机制。能力点：attention_formula, scaled_dot_product_attention。难度：中等。题型：技术基础。轮次：technical。意图：screening。关键词：Attention, Transformer, 缩放点积, dk, softmax。"
}
```

### 这个库解决什么

* 当前该问什么题
* 适合哪个轮次
* 适合哪个能力缺口
* 题目之间如何去重与排序

---

## 2. Rubric Index

专门给“答案分析”和“追问触发”用。

### 索引内容建议

把这些字段拼成 rubric view：

```json id="ridx"
{
  "doc_id": "llm_001#rubric",
  "source_id": "llm_001",
  "view_type": "rubric",
  "role": "大模型算法工程师",
  "question": "Attention 机制的计算公式是什么？为什么要除以 dk？",
  "competency": ["attention_formula", "scaled_dot_product_attention"],
  "answer_summary": "Attention 机制的核心计算公式为 ...",
  "key_points": [...],
  "optional_points": [...],
  "expected_answer_signals": [...],
  "common_mistakes": [...],
  "scoring_rubric": {...},
  "followups": [...],
  "dense_text": "题目：Attention 机制的计算公式是什么？为什么要除以 dk？标准答案：Attention(Q,K,V)=softmax(QK^T/√dk)V。关键点：Q/K/V 含义，缩放原因，dk 增大导致方差变大，softmax 饱和，梯度稳定。加分点：Self-Attention 中 QKV 来源，dk 是键向量维度。常见错误：只写公式，不解释缩放原因；混淆 dk 与 hidden_size；未解释 softmax 饱和。"
}
```

### 这个库解决什么

* 用户答到了哪些点
* 漏了哪些点
* 应该怎么打分
* 应该追问什么

---

# 二、把 Retriever 拆成两个，不要一个通吃

你现在的 retriever 最好拆成：

# **QuestionRetriever**

和

# **RubricRetriever**

---

## QuestionRetriever

输入：

* session state
* 当前岗位
* 当前轮次
* 已覆盖能力
* 待补能力
* 已问题目
* 当前 topic

输出：

* 下一题候选列表

### 排序要看

* `role` 匹配
* `round_type` 匹配
* `question_intent` 匹配
* `competency` 覆盖收益
* `difficulty` 是否合适
* `asked_question_ids` 去重
* 与当前 topic 的连续性

---

## RubricRetriever

输入：

* 当前题目 id
* 用户答案
* 当前问题上下文

输出：

* 对应 rubric profile
* 评分基准
* 常见错误
* 候选追问

### 排序要看

* 当前 question id 精确命中
* 同 competency 的相近题兜底
* `expected_answer_signals` 覆盖
* `common_mistakes` 相似命中

---

# 三、你的 `RAGService` 要从“检索入口”升级成“面试编排入口”

你原来的 `RAGService` 更像：

* 初始化 embedding / store / retriever
* build index
* search

现在要升级成面试业务入口。

建议改成 4 类接口。

---

## 1. 建库接口

```python
build_indexes()
```

作用：

* 读取 schema 化 JSON
* 校验字段
* 生成 Question Index
* 生成 Rubric Index
* 构建 metadata 索引

---

## 2. 出题接口

```python
get_next_question(session_state) -> QuestionCard
```

作用：

* 从 QuestionRetriever 取候选
* 结合 Interview Planner 决定下一题
* 返回结构化题目对象

---

## 3. 判题接口

```python
analyze_answer(question_id, candidate_answer, session_state) -> AnalysisResult
```

作用：

* 从 RubricRetriever 取当前题的 rubric
* 做 coverage / depth / correctness 分析
* 输出结构化分析结果

---

## 4. 追问接口

```python
get_followup(question_id, analysis_result, session_state) -> FollowupDecision
```

作用：

* 根据结构化评估 + followups + 策略器
* 决定是追问、提示、切题还是结束

---

# 四、把 `build_question_context()` 和 `build_answer_context()` 改成真正的两阶段流程

你现在已有：

* `build_question_context()`
* `build_answer_context()`

很好，但还不够。建议变成这样。

---

## 旧逻辑

* build_question_context：给出题参考
* build_answer_context：给纠偏参考

## 新逻辑

### A. 出题阶段

`build_question_context(session_state)`

输出不再是大段自然语言，而是：

```json id="qctx"
{
  "target_competency": ["attention_formula"],
  "round_type": "technical",
  "difficulty_target": "中等",
  "candidate_questions": [
    {"id": "llm_001", "score": 0.91},
    {"id": "llm_007", "score": 0.84}
  ],
  "selection_reason": "当前未覆盖 attention 相关基础能力，且该题适合作为 screening 题"
}
```

### B. 判题阶段

`build_answer_context(question_id, candidate_answer, session_state)`

输出不再是直接给 LLM 的自由文本，而是：

```json id="actx"
{
  "question_id": "llm_001",
  "matched_rubric_id": "llm_001#rubric",
  "key_points": [...],
  "optional_points": [...],
  "expected_answer_signals": [...],
  "common_mistakes": [...],
  "followups": [...]
}
```

---

# 五、加一个 Interview State，不然新 schema 价值发挥不出来

如果你已经有：

* `competency`
* `round_type`
* `question_intent`

那就必须配套一个 session state，不然这些字段只是摆设。

---

## 建议的最小 state

```json id="state"
{
  "session_id": "xxx",
  "role": "大模型算法工程师",
  "target_round_type": "technical",
  "target_difficulty": "中等",

  "asked_question_ids": [],
  "covered_competencies": [],
  "weak_competencies": [],
  "current_topic": null,

  "followup_depth": 0,
  "round_goal_progress": 0.0
}
```

---

## 这个 state 用来做什么

### 出题时

* 避免重复问
* 优先补齐未覆盖能力
* 控制难度爬升
* 控制 topic 连续性

### 判题后

* 更新 covered_competencies
* 识别 weak_competencies
* 决定是否继续追问
* 决定是否换题

---

# 六、把回答分析从“文本生成”改成“结构化判断”

这是你新 schema 最大的收益点之一。

因为你现在已经有：

* `key_points`
* `optional_points`
* `expected_answer_signals`
* `common_mistakes`
* `scoring_rubric`
* `followups`

那就不应该让 LLM 直接自由输出“你回答得不错”。

应该先输出结构化结果。

---

## 建议的 AnalysisResult

```json id="analysis"
{
  "question_id": "llm_001",
  "coverage": {
    "basic": 1.0,
    "good": 0.5,
    "excellent": 0.0
  },
  "correctness": 0.82,
  "depth": 0.46,
  "confidence": 0.78,

  "covered_points": [
    "Attention 基本公式",
    "除以√dk 防止点积过大"
  ],
  "missed_points": [
    "dk 增大导致方差变大",
    "softmax 饱和导致梯度变小"
  ],
  "hit_signals": [
    "softmax(QK^T/√dk)V",
    "缩放"
  ],
  "red_flags": [
    "混淆 dk 与 hidden_size"
  ],
  "suggested_followup_type": "missing_explanation",
  "recommended_followup_ids": [1]
}
```

---

## 这一步怎么做

先别追求特别复杂，第一版可以：

### 规则层

* `expected_answer_signals` 命中率
* `key_points` 语义匹配率
* `common_mistakes` 反向匹配
* rubric 层级覆盖率

### LLM 层

只做辅助判断：

* 覆盖点归纳
* 深度估计
* 是否存在概念混淆

---

# 七、把 followups 从“静态追问”变成“追问候选”

你现在的 `followups` 已经结构化了，这很好。
接下来不是只拿来直接问，而是让它进入策略器。

---

## 建议新流程

### 先做 FollowupPolicy

输入：

* `analysis_result`
* `followups`
* `session_state`

输出：

```json id="fp"
{
  "next_action": "ask_followup",
  "followup_type": "missing_explanation",
  "followup_question": "softmax 梯度变小的原理是什么？",
  "reason": "候选人提到了缩放，但没有解释 softmax 饱和与梯度的关系"
}
```

---

## next_action 建议枚举

* `ask_followup`
* `ask_hint_then_followup`
* `switch_question`
* `raise_difficulty`
* `end_topic`

---

# 八、你的 Chroma / 向量库层也要随之改 schema

不是数据库换掉，而是 document schema 要变。

建议每个原题变成两条记录：

```text
llm_001#question
llm_001#rubric
```

metadata 至少包含：

```json id="meta"
{
  "source_id": "llm_001",
  "view_type": "question",
  "role": "大模型算法工程师",
  "category": "Transformer 基础",
  "subcategory": "注意力机制",
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "competency": ["attention_formula", "scaled_dot_product_attention"]
}
```

这样你检索时才能做真正的 metadata filter。

---

# 九、你现在的 rerank 逻辑也要重新分层

旧逻辑是：

* 向量召回
* min similarity
* 词法打分
* rerank

新 schema 下建议拆成两套。

---

## QuestionRetriever rerank

优先级：

1. role 匹配
2. round_type 匹配
3. competency 覆盖收益
4. question_intent 是否符合当前阶段
5. difficulty 是否合适
6. 语义相似度
7. 去重与历史惩罚

---

## RubricRetriever rerank

优先级：

1. source_id 精确匹配当前题
2. competency 相似
3. answer_summary / key_points 相似
4. expected_answer_signals 命中
5. common_mistakes 命中

---

# 十、给你一个最推荐的升级后总流程

---

## 离线建库

**JSON schema 题库**
→ schema 校验
→ 生成 question view
→ 生成 rubric view
→ 生成 embeddings
→ 写入向量库 / metadata 索引

---

## 在线出题

**session_state**
→ Interview Planner 决定目标 competency / round / difficulty
→ QuestionRetriever 检索
→ 选中 QuestionCard
→ Response Generator 生成人类面试官风格提问

---

## 在线判题

**candidate_answer**
→ RubricRetriever 取当前题 rubric
→ Answer Analyzer 生成结构化分析结果
→ 更新 session_state

---

## 在线追问

**analysis_result + session_state**
→ FollowupPolicy 决定 next_action
→ 若追问，则从 followups 中选一条或生成变体
→ Response Generator 输出追问

---

# 十一、你代码层面具体该怎么改

我给你最实用的改法，不空谈。

---

## 1. `service.py`

从现在的统一 search 服务，扩成：

* `build_indexes()`
* `get_next_question(session_state)`
* `get_rubric(question_id)`
* `analyze_answer(question_id, answer, session_state)`
* `decide_followup(question_id, analysis_result, session_state)`

---

## 2. `embedding.py`

不需要大改，但输入文本要分两类：

* question dense text
* rubric dense text

---

## 3. `chroma_db.py`

支持：

* `view_type`
* `source_id`
* metadata filter
* 一题两文档

---

## 4. `retriever.py`

拆成：

* `QuestionRetriever`
* `RubricRetriever`

不要再只有一个通用 retriever。

---

## 5. `app.py`

主流程从：

* 直接问题 / 直接追问

改成：

### 出题链

`session_state -> get_next_question -> generate_question_text`

### 回答链

`answer -> analyze_answer -> update_state -> decide_followup -> generate_followup_or_feedback`

---

# 十二、最小改造路径

如果你不想一次改太大，按这个顺序来最稳：

## 第一步

把单索引改成双索引：

* `#question`
* `#rubric`

## 第二步

把 retriever 拆成两个：

* `QuestionRetriever`
* `RubricRetriever`

## 第三步

加 `InterviewState`

## 第四步

把“回答分析”改成先输出 JSON，再生成自然语言

## 第五步

加 `FollowupPolicy`

---

# 最终结论

如果采用你这版 schema，RAG 架构不应该只是“字段变多了”，而应该完成这次升级：

# **从单通道文本检索 RAG，升级为状态驱动的双通道面试 RAG。**

也就是：

* **Question RAG** 负责找题
* **Rubric RAG** 负责判题
* **Interview State** 负责记住过程
* **Answer Analyzer** 负责结构化评估
* **Followup Policy** 负责决定下一步
* **LLM** 只负责把结果说得像真实面试官

这才是你这套 schema 的正确打开方式。

你要的话，我下一步可以直接继续给你一版**新的模块设计图 + Python 类结构草图**。
