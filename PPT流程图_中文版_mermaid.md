# 职跃星辰 流程图（中文版 Mermaid，中等比例版）

这版是中等比例（不过宽、不过高），适合放在 16:9 PPT 的主体区域。  
重点突出：训练闭环、多模态评估、RAG 可追溯、阶段画像驱动提升。

---

## 1）项目主流程（中等比例）

```mermaid
flowchart LR
    A[用户登录] --> B[选择训练模式<br/>岗位/轮次/题目]
    B --> C[进入模拟面试]

    C --> C1[语音采集与转写<br/>ASR]
    C --> C2[镜头行为采集<br/>注视/姿态/异常]
    C --> C3[会话上下文记录<br/>题目-回答-时间线]

    C1 --> D[会话数据汇总]
    C2 --> D
    C3 --> D

    D --> E[结构化评估引擎<br/>内容轴+语音轴+镜头轴]
    E --> F[单场面试报告]
    F --> G[阶段总结与综合画像]
    G --> H[成长建议与训练重心]
    H --> B

    F --> I[AI 问答助手]
    I --> J[RAG 检索<br/>岗位知识库/题库]
    J --> K[带引用回答<br/>证据可追溯]
    K --> H

    subgraph V[项目优势]
    direction TB
    V1[[优势① 训练-评估-复盘闭环]]
    V2[[优势② 多模态证据化评估]]
    V3[[优势③ RAG 优先且可追溯]]
    V4[[优势④ 阶段画像驱动持续提升]]
    end

    F -.体现.-> V1
    E -.体现.-> V2
    J -.体现.-> V3
    G -.体现.-> V4

    classDef user fill:#E8F2FF,stroke:#5B8FF9,stroke-width:1.3px,color:#1F2D3D;
    classDef process fill:#F6F8FB,stroke:#98A2B3,stroke-width:1.1px,color:#1F2937;
    classDef ai fill:#F0E9FF,stroke:#8B6DD8,stroke-width:1.2px,color:#2D1E5F;
    classDef value fill:#EAF8EC,stroke:#41A05F,stroke-width:1.2px,color:#0F5132;

    class A,B,C user;
    class C1,C2,C3,D,E,F,G,H process;
    class I,J,K ai;
    class V1,V2,V3,V4 value;
```

---

## 2）技术架构流程（中等比例）

```mermaid
flowchart LR
    FE[前端应用<br/>Next.js + React] --> API[后端入口<br/>app.py]
    API --> ORCH[会话编排层<br/>训练流程控制]

    ORCH --> AUTH[认证与会话管理]
    ORCH --> EVAL[评估服务<br/>内容/语音/镜头]
    ORCH --> RPT[报告生成服务]
    ORCH --> INSIGHT[阶段总结服务]
    ORCH --> ASSIST[AI 助手服务]

    ASSIST --> RET[Retriever 检索]
    RET --> VDB[(向量库 Chroma)]
    RET --> KB[知识文档库<br/>岗位知识/题库]
    KB --> BUILD[知识构建脚本<br/>Embedding + 索引更新]
    BUILD --> VDB

    AUTH --> DB[(业务数据库<br/>会话/报告/助手历史)]
    RPT --> DB
    INSIGHT --> DB
    ASSIST --> DB

    subgraph ADV[架构优势]
    direction TB
    A1[[模块解耦，迭代快]]
    A2[[RAG 与业务评估融合]]
    A3[[数据沉淀形成长期成长资产]]
    end

    ORCH -.体现.-> A1
    ASSIST -.体现.-> A2
    DB -.体现.-> A3

    classDef entry fill:#E8F2FF,stroke:#5B8FF9,stroke-width:1.3px,color:#1F2D3D;
    classDef service fill:#F7F7F9,stroke:#9AA4B2,stroke-width:1.1px,color:#1F2937;
    classDef rag fill:#F0E9FF,stroke:#8B6DD8,stroke-width:1.2px,color:#2D1E5F;
    classDef store fill:#FFF4E5,stroke:#D48806,stroke-width:1.1px,color:#5C3B00;
    classDef value fill:#EAF8EC,stroke:#41A05F,stroke-width:1.2px,color:#0F5132;

    class FE,API,ORCH entry;
    class AUTH,EVAL,RPT,INSIGHT,ASSIST,RET,BUILD service;
    class KB,VDB,DB store;
    class A1,A2,A3 value;
```

---

## 3）PPT 讲解词（约 90 秒）

这张图展示的是 职跃星辰 的完整训练闭环。用户先选择岗位、轮次和题目进入模拟面试，系统会同步采集语音、镜头行为和会话上下文，然后通过结构化评估引擎生成单场报告。

报告不是只给一个总分，而是告诉用户具体短板在哪里、证据来自哪里。接下来系统会把最近多场结果聚合成阶段画像，判断用户当前是上升、波动还是某些能力反复卡住，并给出下一轮训练重心。  

更关键的是，用户可以基于报告里的薄弱点直接进入 AI 助手继续追问，比如“系统设计回答怎么更有层次”。助手会先检索知识库，再结合当前会话给出答案，并展示引用来源。这样用户拿到的不只是建议，而是可以立即执行的训练动作，最终回流到下一轮训练，形成“发现问题—理解问题—执行改进—再次验证”的持续提升闭环。

