Java后端面试题库（优化标签+增强答案版）
简单（10题）
{
  "id": "simple_001",
  "role": "Java后端开发工程师",
  "question": "请用1分钟介绍你最有代表性的一个项目",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "项目",
    "表达"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "采用 STAR 法则结构化表达：1）项目背景：用户规模、业务场景；2）个人角色：承担职责、核心挑战；3）技术方案：架构设计、性能优化、难点攻克；4）量化结果：QPS 提升、耗时降低。控制 1 分钟，选择复杂度适中且能体现技术深度的项目。",
  "key_points": [
    "STAR法则结构化表达：背景→任务→行动→结果",
    "技术亮点：架构设计、性能优化、难点攻克",
    "量化结果：性能指标、业务价值、用户规模",
    "角色定位：独立负责还是团队协作",
    "技术深度：避免停留在表面，要深入到原理层面"
  ],
  "optional_points": [
    "项目技术栈和架构图",
    "遇到的最大的技术挑战和解决方案",
    "项目中最有成就感的一点"
  ],
  "expected_answer_signals": [
    "结构清晰",
    "逻辑分明",
    "有数据支撑",
    "技术深度适中"
  ],
  "common_mistakes": [
    "流水账式叙述，缺乏重点",
    "只描述业务不描述技术",
    "无法回答技术细节追问",
    "项目选择过于简单或复杂",
    "无法量化成果"
  ],
  "scoring_rubric": {
    "basic": [
      "能讲清楚项目是什么",
      "有基本结构"
    ],
    "good": [
      "能突出技术亮点",
      "有量化指标",
      "回答有层次"
    ],
    "excellent": [
      "技术深度足够",
      "能应对各种追问",
      "项目有挑战性且成果显著",
      "表达清晰有感染力"
    ]
  },
  "followups": [
    {
      "question": "你在这个项目中最有挑战的技术点是什么？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "技术深度"
      ]
    },
    {
      "question": "如果重新做这个项目，你会怎么优化？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "反思能力"
      ]
    }
  ],
  "retrieval_text": "项目介绍技巧STAR法则",
  "source_type": "人工整理"
}
{
  "id": "simple_002",
  "role": "Java后端开发工程师",
  "question": "你为什么选择Java而不是其他语言？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "Java",
    "选择"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "从多维度展开：1）生态优势：Spring 全家桶、丰富类库；2）工程化：IDE、调试工具、CI/CD；3）JVM 性能：GC 优化、即时编译；4）对比其他语言：Go/Python/C++ 优劣势；5）结合项目经验说明。同时表现出对 Java 局限性的认知。",
  "key_points": [
    "生态系统：Spring全家桶、丰富类库、成熟框架",
    "工程化成熟度：IDE、调试工具、CI/CD",
    "JVM性能：GC优化、即时编译、性能监控",
    "对比其他语言：Go/Python/C++的优劣势",
    "结合自身项目经验说明选择原因"
  ],
  "optional_points": [
    "Java的不足之处和改进方向",
    "多语言协作经验",
    "对新技术语言的学习计划"
  ],
  "expected_answer_signals": [
    "对Java生态了解深入",
    "有技术对比能力",
    "能结合项目经验",
    "认知客观全面"
  ],
  "common_mistakes": [
    "只说'因为学了Java'",
    "贬低其他语言",
    "不了解Java生态",
    "无法进行语言对比",
    "回答过于主观"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出Java的某个优点"
    ],
    "good": [
      "能进行多语言对比",
      "有项目支撑"
    ],
    "excellent": [
      "理解深入、认知全面",
      "能客观评价语言优劣",
      "有技术视野和前瞻性"
    ]
  },
  "followups": [
    {
      "question": "Java和Go在微服务场景下各有什么优劣？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "技术对比"
      ]
    },
    {
      "question": "如果让你重新选择，你会选什么语言？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "深入思考"
      ]
    }
  ],
  "retrieval_text": "Java语言优势分析",
  "source_type": "人工整理"
}
{
  "id": "simple_003",
  "role": "Java后端开发工程师",
  "question": "介绍一个你解决过的技术难题",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "问题",
    "解决"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "采用问题 - 分析 - 解决 - 结果四段式：1）问题背景：业务场景、影响范围；2）排查思路：监控分析、日志定位、根因分析；3）解决方案：方案对比、选择依据、实施细节；4）结果量化：性能指标提升。选择有复杂度的场景，避免过于简单的问题。",
  "key_points": [
    "问题背景：业务场景、影响范围、紧急程度",
    "排查思路：监控分析、日志定位、根因定位",
    "解决方案：方案对比、选择依据、实施细节",
    "结果量化：性能指标提升、业务价值",
    "复盘反思：是否有更好方案、经验总结"
  ],
  "optional_points": [
    "排查过程中用到的工具和方法",
    "解决过程中最大的挑战",
    "对团队的启示和分享"
  ],
  "expected_answer_signals": [
    "排查思路清晰",
    "分析有逻辑",
    "方案有依据",
    "结果可量化"
  ],
  "common_mistakes": [
    "问题过于简单",
    "排查思路混乱",
    "方案没有对比",
    "无法回答追问",
    "只讲结果不讲过程"
  ],
  "scoring_rubric": {
    "basic": [
      "能描述清楚问题",
      "有基本解决思路"
    ],
    "good": [
      "排查思路清晰",
      "有多种方案对比",
      "能量化结果"
    ],
    "excellent": [
      "问题复杂度足够",
      "分析深入到位",
      "方案权衡合理",
      "有复盘和总结",
      "能应对深度追问"
    ]
  },
  "followups": [
    {
      "question": "当时最大的阻碍是什么？你是如何突破的？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "深入追问"
      ]
    },
    {
      "question": "有没有考虑过其他方案？各自的优缺点是什么？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "方案对比"
      ]
    }
  ],
  "retrieval_text": "技术难题解决案例分析",
  "source_type": "人工整理"
}
{
  "id": "simple_004",
  "role": "Java后端开发工程师",
  "question": "你如何快速学习一个新技术？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "学习",
    "方法"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "展示系统化学习方法：1）目标导向：明确学习目的和适用场景；2）建立框架：官方文档→书籍→源码；3）实践验证：小项目驱动；4）深度研究：理解原理；5）总结输出：博客、分享；6）持续迭代。举例最近学习的具体技术及周期。",
  "key_points": [
    "目标导向：明确学习目的和适用场景",
    "系统化方法：官方文档→书籍→源码→实践",
    "实践验证：小项目驱动学习",
    "深度研究：理解原理和设计思想",
    "输出巩固：博客、分享、技术文档"
  ],
  "optional_points": [
    "最近学习的新技术及学习周期",
    "学习过程中的瓶颈及突破方法",
    "对技术趋势的判断和学习规划"
  ],
  "expected_answer_signals": [
    "有系统学习方法",
    "有实践案例",
    "学习效率高",
    "能持续学习"
  ],
  "common_mistakes": [
    "学习方法零散",
    "只看书不动手",
    "浅尝辄止",
    "无法举出实例",
    "缺乏深度研究"
  ],
  "scoring_rubric": {
    "basic": [
      "有自己的学习方法"
    ],
    "good": [
      "方法系统化",
      "有实践案例",
      "能举一反三"
    ],
    "excellent": [
      "方法论成熟",
      "有深度研究能力",
      "有技术输出",
      "学习效率高",
      "能建立知识体系"
    ]
  },
  "followups": [
    {
      "question": "最近一次学习新技术的经历是怎样的？你是怎么安排时间的？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "实践经历"
      ]
    },
    {
      "question": "你是如何验证自己真正掌握了这门技术的？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "学习效果"
      ]
    }
  ],
  "retrieval_text": "快速学习新技术方法论",
  "source_type": "人工整理"
}
{
  "id": "simple_005",
  "role": "Java后端开发工程师",
  "question": "你如何处理工作中的错误？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "错误",
    "处理"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "展现成熟工程素养：1）快速止血：定位问题、恢复服务；2）根因分析：日志监控、5Why 分析；3）复盘总结：形成文档、团队分享；4）预防改进：增加监控、完善预案；5）文化倡导：安全错误文化。举具体错误案例及教训。",
  "key_points": [
    "快速止血：定位问题、恢复服务、减少损失",
    "根因分析：5Why分析法、监控日志、复盘",
    "复盘总结：形成文档、团队分享、避免追责文化",
    "预防改进：增加监控、完善预案、技术优化",
    "心态成熟：承认错误、积极改进、持续学习"
  ],
  "optional_points": [
    "一个具体的错误案例",
    "错误带来的最大教训",
    "如何推动团队改进"
  ],
  "expected_answer_signals": [
    "心态成熟",
    "处理有条理",
    "有改进措施",
    "能举实例"
  ],
  "common_mistakes": [
    "推卸责任",
    "隐瞒错误",
    "只止血不复盘",
    "无法举实例",
    "心态不端正"
  ],
  "scoring_rubric": {
    "basic": [
      "能承认错误",
      "有基本处理思路"
    ],
    "good": [
      "处理有条理",
      "有复盘意识",
      "能举实例"
    ],
    "excellent": [
      "心态成熟稳重",
      "有系统复盘方法",
      "能推动团队改进",
      "有预防意识",
      "错误转化为成长"
    ]
  },
  "followups": [
    {
      "question": "有没有犯过让你印象深刻的错误？当时是怎么处理的？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "实际经历"
      ]
    },
    {
      "question": "你是如何在团队中倡导'安全错误文化'的？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "团队影响"
      ]
    }
  ],
  "retrieval_text": "工作中的错误处理与复盘",
  "source_type": "人工整理"
}
{
  "id": "simple_006",
  "role": "Java后端开发工程师",
  "question": "你在团队中通常承担什么角色？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "团队",
    "角色"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "结合实际经历展示团队角色：1）技术专家/架构设计者/项目推动者/质量守护者；2）角色价值：如何发挥独特作用；3）协作模式：与其他角色配合；4）影响力：对他人帮助和团队贡献；5）成长规划：希望承担更大角色。举具体例子说明贡献。",
  "key_points": [
    "角色定位：技术专家/架构设计者/推动者/质量守护者",
    "角色价值：如何在团队中发挥独特作用",
    "协作模式：与其他角色的配合方式",
    "影响力：对他人的帮助和团队的贡献",
    "成长规划：希望承担什么更大角色"
  ],
  "optional_points": [
    "与不同类型leader配合的经验",
    "团队冲突的处理经验",
    "培养新人的经历"
  ],
  "expected_answer_signals": [
    "角色认知清晰",
    "有具体贡献",
    "有协作意识",
    "有成长意愿"
  ],
  "common_mistakes": [
    "角色模糊",
    "只讲个人贡献不讲团队",
    "无法举具体例子",
    "过于谦虚或过于自大",
    "缺乏协作意识"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出自己的角色"
    ],
    "good": [
      "角色认知清晰",
      "有具体贡献",
      "有团队意识"
    ],
    "excellent": [
      "有多角色经验",
      "有领导力",
      "能影响他人",
      "有成长规划",
      "协作意识强"
    ]
  },
  "followups": [
    {
      "question": "你如何处理团队中的技术分歧？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "协作能力"
      ]
    },
    {
      "question": "你是如何帮助团队成员成长的？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "影响力"
      ]
    }
  ],
  "retrieval_text": "团队角色与协作能力",
  "source_type": "人工整理"
}
{
  "id": "simple_007",
  "role": "Java后端开发工程师",
  "question": "你如何保证代码质量？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "代码",
    "质量"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "多维度保证代码质量：1）编码规范：Checkstyle、阿里规约；2）Code Review：PR 流程、双人审批；3）单元测试：JUnit、Mockito，核心模块覆盖率 80%+；4）持续集成：自动构建、测试、扫描；5）设计原则：SOLID、DRY、KISS；6）重构习惯：定期改善结构；7）技术债务：识别和偿还。举具体落地例子。",
  "key_points": [
    "编码规范：Checkstyle、阿里规约、团队规范",
    "Code Review：PR流程、Review要点、双人审批",
    "单元测试：覆盖率、测试质量、可维护性",
    "持续集成：CI流水线、自动化检查",
    "设计原则：SOLID、DRY、KISS、设计模式",
    "技术债务：识别、记录、计划偿还"
  ],
  "optional_points": [
    "项目中具体的质量指标",
    "发现的典型代码坏味道及重构",
    "推动团队质量建设的经历"
  ],
  "expected_answer_signals": [
    "有质量意识",
    "方法全面",
    "有具体实践",
    "有量化指标"
  ],
  "common_mistakes": [
    "只注重功能不注重质量",
    "缺乏测试意识",
    "不了解Code Review流程",
    "无法举具体例子",
    "忽视技术债务"
  ],
  "scoring_rubric": {
    "basic": [
      "有基本质量意识"
    ],
    "good": [
      "方法全面",
      "有具体实践",
      "有量化指标"
    ],
    "excellent": [
      "工程素养好",
      "有完整质量体系",
      "能推动团队",
      "有重构能力",
      "平衡质量与效率"
    ]
  },
  "followups": [
    {
      "question": "你是如何在保证质量和保证进度之间做平衡的？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "权衡能力"
      ]
    },
    {
      "question": "你发现过什么典型的代码坏味道？如何重构的？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "实践能力"
      ]
    }
  ],
  "retrieval_text": "代码质量保证体系",
  "source_type": "人工整理"
}
{
  "id": "simple_008",
  "role": "Java后端开发工程师",
  "question": "你如何安排多任务优先级？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "任务",
    "优先级"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "展示时间管理能力：1）紧急重要矩阵：四象限法则区分优先级；2）任务拆分：大任务拆分为可执行小任务；3）估算工时：准确评估，考虑并行；4）沟通同步：与产品、PM 同步进度和风险；5）保护整块时间：重要任务安排在精力充沛时段；6）工具辅助：Jira、Trello。举多任务处理的实际例子。",
  "key_points": [
    "紧急重要矩阵：四象限法则和任务分类",
    "任务拆分：WBS分解、粒度适中",
    "工时估算：考虑复杂度和风险",
    "沟通协调：与PM、干系人同步",
    "时间保护：精力管理、番茄工作法",
    "工具辅助：Jira、Notion等任务管理工具"
  ],
  "optional_points": [
    "一个具体的多任务处理案例",
    "与leader沟通优先级的经验",
    "如何避免多任务切换带来的效率损失"
  ],
  "expected_answer_signals": [
    "有系统方法",
    "沟通协调能力",
    "能举实例",
    "有量化思维"
  ],
  "common_mistakes": [
    "被动接受任务没有优先级判断",
    "无法拒绝不重要的任务",
    "多任务时手忙脚乱",
    "不与干系人沟通期望",
    "无法举具体例子"
  ],
  "scoring_rubric": {
    "basic": [
      "有基本处理思路"
    ],
    "good": [
      "方法系统化",
      "沟通协调好",
      "能举实例"
    ],
    "excellent": [
      "时间管理能力强",
      "有量化思维",
      "沟通能力强",
      "能平衡多方",
      "有成熟方法论"
    ]
  },
  "followups": [
    {
      "question": "当多个任务都很紧急无法区分优先级时，你会怎么处理？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "极端情况"
      ]
    },
    {
      "question": "你是如何让leader了解你的工作负荷的？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "向上管理"
      ]
    }
  ],
  "retrieval_text": "多任务优先级管理",
  "source_type": "人工整理"
}
{
  "id": "simple_009",
  "role": "Java后端开发工程师",
  "question": "你遇到过最难沟通的情况？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "简单",
  "question_type": "行为面试",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": [
    "沟通",
    "冲突"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "采用情境 - 挑战 - 方法 - 结果结构：1）情境：描述难沟通场景；2）挑战：说明难点；3）方法：倾听对方、数据支撑、寻找共同目标、折中方案、寻求支持；4）结果：如何解决及收获。展现情商、沟通技巧和解决问题能力，表现开放心态和反思能力。",
  "key_points": [
    "情境描述：具体的沟通场景和背景",
    "挑战分析：难沟通的根本原因",
    "解决策略：倾听、共情、事实、协作",
    "结果呈现：双赢或折中方案",
    "反思总结：从中学到的沟通经验"
  ],
  "optional_points": [
    "沟通对象的类型：同事/PM/leader/客户",
    "如何处理情绪化沟通",
    "跨文化或远程沟通的挑战"
  ],
  "expected_answer_signals": [
    "沟通成熟",
    "情商高",
    "能换位思考",
    "有解决方法",
    "有反思"
  ],
  "common_mistakes": [
    "抱怨对方不讲理",
    "只讲问题不讲解决方法",
    "无法举具体例子",
    "表现得很强势或很弱势",
    "缺乏反思"
  ],
  "scoring_rubric": {
    "basic": [
      "能描述情况"
    ],
    "good": [
      "有解决方法",
      "结果正面",
      "有反思"
    ],
    "excellent": [
      "沟通能力强",
      "情商高",
      "双赢思维",
      "有成熟方法论",
      "持续改进"
    ]
  },
  "followups": [
    {
      "question": "如果对方一直坚持自己的观点不妥协，你怎么办？",
      "trigger_type": "missing_analysis",
      "trigger_signals": [
        "深入追问"
      ]
    },
    {
      "question": "这次经历对你后续的沟通方式有什么改变？",
      "trigger_type": "missing_point",
      "trigger_signals": [
        "反思成长"
      ]
    }
  ],
  "retrieval_text": "工作中的沟通技巧与冲突处理",
  "source_type": "人工整理"
}
困难（10题）
{
  "id": "hard_001",
  "role": "Java后端开发工程师",
  "question": "JVM垃圾回收器选型时，G1和ZGC的区别是什么？如何根据业务场景选择？",
  "category": "Java核心技术",
  "subcategory": "JVM原理",
  "competency": [
    "analysis",
    "performance",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "技术深度",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "JVM",
    "GC",
    "G1",
    "ZGC"
  ],
  "tags": [
    "JVM原理",
    "性能优化",
    "底层机制",
    "技术选型"
  ],
  "answer_summary": "架构设计：1）流量层：CDN 加速、限流防刷、请求合并；2）缓存层：Redis 预扣库存、本地缓存热点；3）队列层：MQ 削峰填谷、异步下单；4）存储层：分库分表、库存分段。核心问题：1）不超卖：分布式锁、数据库乐观锁；2）高性能：缓存 + 队列、少写数据库；3）公平性：队列顺序、防刷机制。体现完整架构思维。",
  "key_points": [
    "G1的Region设计和标记-整理算法",
    "ZGC的着色指针和并发处理机制",
    "停顿时间 vs 吞吐量的权衡",
    "不同GC的适用场景和选型依据",
    "JVM参数调优的实际经验"
  ],
  "optional_points": [
    "CMS与G1、ZGC的对比",
    "GC日志分析和问题排查"
  ],
  "expected_answer_signals": [
    "原理清晰",
    "有实践",
    "能权衡"
  ],
  "common_mistakes": [
    "只停留在表面概念",
    "缺乏实际调优经验",
    "无法给出具体选型建议"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出G1和ZGC的基本概念"
    ],
    "good": [
      "理解算法原理和性能差异"
    ],
    "excellent": [
      "能结合场景给出合理选型，有实际调优经验"
    ]
  },
  "followups": [
    {
      "question": "如果线上GC停顿时间突然变长，你会如何排查？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "分析能力"
      ]
    },
    {
      "question": "ZGC的并发阶段会影响吞吐量，如何优化？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "深度理解"
      ]
    }
  ],
  "retrieval_text": "JVM垃圾回收器原理",
  "source_type": "人工整理"
}
{
  "id": "hard_002",
  "role": "Java后端开发工程师",
  "question": "MySQL主从复制延迟的成因及解决方案有哪些？",
  "category": "数据库",
  "subcategory": "MySQL原理",
  "competency": [
    "analysis",
    "performance",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "MySQL",
    "主从复制",
    "延迟",
    "解决方案"
  ],
  "tags": [
    "MySQL原理",
    "数据库架构",
    "性能优化",
    "分布式系统"
  ],
  "answer_summary": "设计要点：1）互斥性：SET NX、Redisson、ZK 顺序节点；2）可重入：线程 ID+ 计数器；3）锁超时：TTL 自动释放、看门狗续期；4）死锁防止：等待超时、锁检测；5）可靠性：Redis 主从切换、ZK 集群。方案对比：Redis 性能高但有主从一致性问题，ZK 强一致但性能低。结合业务场景选择。",
  "key_points": [
    "主从复制原理：binlog dump线程、IO线程、SQL线程",
    "延迟产生的根本原因：单线程重放、大事务、网络延迟",
    "并行复制原理：基于库、基于表、基于事务的并行",
    "半同步复制 vs 异步复制",
    "业务层面的解决方案：延迟读、读写分离策略"
  ],
  "optional_points": [
    "GTID复制原理",
    "PXC/Galera集群方案",
    "延迟监控和告警"
  ],
  "expected_answer_signals": [
    "原理清晰",
    "有实战",
    "方案可行"
  ],
  "common_mistakes": [
    "只说表象，不说原因",
    "缺乏实际排查经验",
    "方案不够系统"
  ],
  "scoring_rubric": {
    "basic": [
      "了解主从复制机制"
    ],
    "good": [
      "能分析延迟原因并给出方案"
    ],
    "excellent": [
      "有深度优化经验，方案系统完整"
    ]
  },
  "followups": [
    {
      "question": "如何实现准同步复制？相比异步有什么优缺点？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "原理理解"
      ]
    },
    {
      "question": "如果业务必须强一致读，你怎么处理？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "架构设计"
      ]
    }
  ],
  "retrieval_text": "MySQL主从复制原理",
  "source_type": "人工整理"
}
{
  "id": "hard_003",
  "role": "Java后端开发工程师",
  "question": "如何设计一个高并发的分布式锁系统？需要注意哪些问题？",
  "category": "分布式系统",
  "subcategory": "分布式协调",
  "competency": [
    "analysis",
    "design",
    "architecture"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "分布式锁",
    "Redis",
    "ZooKeeper",
    "一致性"
  ],
  "tags": [
    "分布式系统",
    "一致性",
    "系统设计",
    "高并发"
  ],
  "answer_summary": "容灾架构：1）多机房部署：同城双活、异地灾备；2）流量调度：DNS 智能解析、全局负载均衡；3）数据同步：主从复制、双向同步、数据校验；4）故障切换：自动检测、一键切换、预案演练；5）降级预案：核心功能优先、非核心降级。结合 CAP 理论说明取舍，强调演练重要性。",
  "key_points": [
    "分布式锁的核心特性：互斥、可重入、超时、死锁防止",
    "Redis实现：SETNX、lua脚本、Redisson、RedLock",
    "ZooKeeper实现：临时节点、Watch、羊群效应",
    "锁续期机制：看门狗、自动延期",
    "一致性 vs 可用性的权衡"
  ],
  "optional_points": [
    "Etcd的分布式锁方案",
    "数据库分布式锁的优缺点",
    "线上问题的实际案例"
  ],
  "expected_answer_signals": [
    "方案完整",
    "理解原理",
    "考虑周全"
  ],
  "common_mistakes": [
    "只考虑成功获取锁",
    "忽略锁失效和超时处理",
    "不理解分布式一致性问题"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出基本实现方式"
    ],
    "good": [
      "理解核心问题和解决方案"
    ],
    "excellent": [
      "方案完整，考虑边界情况，有实践经验"
    ]
  },
  "followups": [
    {
      "question": "如果Redis主从切换导致锁失效，如何保证锁的安全性？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "深入理解"
      ]
    },
    {
      "question": "如何实现可重入的分布式锁？",
      "trigger_type": "technical_detail",
      "trigger_signals": [
        "实现细节"
      ]
    }
  ],
  "retrieval_text": "分布式锁设计原理",
  "source_type": "人工整理"
}
{
  "id": "hard_004",
  "role": "Java后端开发工程师",
  "question": "如何设计一个秒杀系统？核心架构和关键技术点是什么？",
  "category": "高并发系统",
  "subcategory": "系统设计",
  "competency": [
    "analysis",
    "design",
    "architecture",
    "performance"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "秒杀",
    "高并发",
    "系统设计",
    "缓存",
    "限流"
  ],
  "tags": [
    "高并发系统",
    "系统设计",
    "架构设计",
    "性能优化"
  ],
  "answer_summary": "方案对比：1）2PC/3PC：强一致，性能差，不推荐；2）TCC：业务实现，性能好，实现复杂；3）Saga：长事务，可补偿，编排式/协作式；4）可靠消息：RocketMQ 事务消息，最终一致；5）Seata AT：自动补偿，无侵入，性能损耗 10-15%。选型建议：金融支付用 TCC/Seata，普通交易用消息队列。体现方案权衡能力。",
  "key_points": [
    "分层架构：流量控制、请求缓存、业务逻辑、数据持久化",
    "库存扣减方案：Redis原子操作、数据库乐观锁、分段锁",
    "消息队列：异步下单、峰值削峰、顺序保证",
    "限流策略：令牌桶、滑动窗口、计数器",
    "幂等性设计：Token机制、唯一索引"
  ],
  "optional_points": [
    "Redis热点key问题解决方案",
    "数据库分库分表策略",
    "降级和熔断策略"
  ],
  "expected_answer_signals": [
    "架构完整",
    "技术点清晰",
    "有实践经验"
  ],
  "common_mistakes": [
    "只谈理论，缺乏实践",
    "忽略库存一致性问题",
    "架构设计过于简单"
  ],
  "scoring_rubric": {
    "basic": [
      "能描述基本架构"
    ],
    "good": [
      "技术点覆盖全面"
    ],
    "excellent": [
      "方案完整可行，有深度优化经验"
    ]
  },
  "followups": [
    {
      "question": "如何保证库存不超卖又不影响性能？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "技术深度"
      ]
    },
    {
      "question": "如果Redis集群故障，如何保证系统可用？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "容错设计"
      ]
    }
  ],
  "retrieval_text": "高并发秒杀系统设计",
  "source_type": "人工整理"
}
{
  "id": "hard_005",
  "role": "Java后端开发工程师",
  "question": "Spring事务传播行为有哪些？请结合实际场景说明如何使用？",
  "category": "Java核心技术",
  "subcategory": "Spring框架",
  "competency": [
    "analysis",
    "design",
    "coding"
  ],
  "difficulty": "困难",
  "question_type": "技术深度",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "Spring",
    "事务",
    "传播行为",
    "ACID"
  ],
  "tags": [
    "Spring框架",
    "事务管理",
    "实际应用",
    "原理理解"
  ],
  "answer_summary": "架构设计：1）采集层：Filebeat/Flume 采集、Kafka 缓冲；2）存储层：Elasticsearch 索引、冷热分离；3）查询层：ES DSL、SQL 引擎、全文检索；4）优化：索引设计、分片策略、查询优化、缓存热点。搜索优化：1）倒排索引：分词器、mapping 设计；2）查询加速：filter 缓存、路由优化；3）大规模：滚动索引、force merge。体现 ELK 栈实战经验。",
  "key_points": [
    "七种传播行为的含义和区别",
    "REQUIRED vs REQUIRES_NEW的隔离性差异",
    "NESTED嵌套事务的Savepoint机制",
    "事务边界的设计原则",
    "常见坑：事务嵌套、事务失效场景"
  ],
  "optional_points": [
    "Spring事务的底层实现原理",
    "声明式 vs 编程式事务",
    "分布式事务的解决方案"
  ],
  "expected_answer_signals": [
    "理解清晰",
    "有实践",
    "能举例"
  ],
  "common_mistakes": [
    "只会背概念",
    "不了解事务边界",
    "忽略事务失效场景"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出传播行为名称"
    ],
    "good": [
      "理解区别和使用场景"
    ],
    "excellent": [
      "能结合场景举例，了解底层原理"
    ]
  },
  "followups": [
    {
      "question": "为什么内部方法调用会导致事务失效？如何解决？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "原理理解"
      ]
    },
    {
      "question": "如果需要跨数据库操作，如何保证事务一致性？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "分布式事务"
      ]
    }
  ],
  "retrieval_text": "Spring事务传播行为",
  "source_type": "人工整理"
}
{
  "id": "hard_006",
  "role": "Java后端开发工程师",
  "question": "如何设计一个可靠的消息队列消费幂等方案？",
  "category": "中间件",
  "subcategory": "消息队列",
  "competency": [
    "analysis",
    "design",
    "architecture"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "消息队列",
    "幂等",
    "Kafka",
    "RocketMQ"
  ],
  "tags": [
    "消息队列",
    "幂等性",
    "分布式系统",
    "可靠性"
  ],
  "answer_summary": "实时性保障：1）数据流：Flink/Storm 实时计算、Kafka 流处理；2）特征更新：实时特征存储、增量更新；3）模型更新：在线学习、模型热更新；4）服务架构：边缘计算、就近推荐、缓存预热。延迟优化：1）异步化：非阻塞 IO、响应式编程；2）缓存：多级缓存、预计算；3）降级：简化模型、规则推荐。体现实时系统架构能力。",
  "key_points": [
    "消息重复的原因：网络重试、消费者超时、生产者重试",
    "唯一key去重：Redis SetNX、数据库唯一索引",
    "状态机幂等：订单状态流转控制",
    "乐观锁方案：版本号机制",
    "消息队列特性：Kafka位移提交、RocketMQ消息ID"
  ],
  "optional_points": [
    "事务消息的幂等处理",
    "消息积压的处理方案",
    "顺序消息的幂等挑战"
  ],
  "expected_answer_signals": [
    "方案完整",
    "理解原理",
    "考虑周全"
  ],
  "common_mistakes": [
    "方案过于简单",
    "忽略消息重复原因",
    "不了解消息队列特性"
  ],
  "scoring_rubric": {
    "basic": [
      "能说出基本方案"
    ],
    "good": [
      "方案覆盖多种场景"
    ],
    "excellent": [
      "方案完整，有深度考虑"
    ]
  },
  "followups": [
    {
      "question": "如果Redis宕机，如何保证幂等性？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "容错设计"
      ]
    },
    {
      "question": "如何处理顺序消息的消费幂等？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "深度理解"
      ]
    }
  ],
  "retrieval_text": "消息队列消费幂等方案",
  "source_type": "人工整理"
}
{
  "id": "hard_007",
  "role": "Java后端开发工程师",
  "question": "如何排查和解决Redis热key问题？对业务有什么影响？",
  "category": "中间件",
  "subcategory": "Redis",
  "competency": [
    "analysis",
    "performance",
    "problem_solving"
  ],
  "difficulty": "困难",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "problem_solving",
  "keywords": [
    "Redis",
    "热key",
    "性能优化",
    "缓存"
  ],
  "tags": [
    "Redis",
    "性能优化",
    "问题排查",
    "高并发"
  ],
  "answer_summary": "防重设计：1）幂等性：唯一流水号、Token 机制、分布式锁；2）防重校验：请求参数 MD5、状态机控制、乐观锁；3）对账机制：T+1 对账、实时对账、差异处理；4）补偿机制：冲正、退款、人工处理。架构设计：1）前置校验：参数校验、黑名单；2）事中控制：幂等处理、分布式事务；3）事后对账：自动对账、异常告警。体现支付系统严谨性。",
  "key_points": [
    "热key成因：数据集中、流量集中、架构问题",
    "排查方法：客户端埋点、Redis命令、机器抓包",
    "本地缓存：Guava Cache、Caffeine二级缓存",
    "key打散：热点key加随机后缀分散到多节点",
    "读写分离：读取从节点（注意数据延迟）"
  ],
  "optional_points": [
    "Redis Cluster的hash slot机制",
    "热点探测系统设计",
    "CDN在热点场景的作用"
  ],
  "expected_answer_signals": [
    "排查思路清晰",
    "解决方案可行",
    "有实践经验"
  ],
  "common_mistakes": [
    "只知道扩容",
    "忽略对业务的影响",
    "方案不够系统"
  ],
  "scoring_rubric": {
    "basic": [
      "知道热key概念"
    ],
    "good": [
      "能排查和解决"
    ],
    "excellent": [
      "方案完整，有深度优化经验"
    ]
  },
  "followups": [
    {
      "question": "本地缓存和Redis如何保持一致？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "一致性设计"
      ]
    },
    {
      "question": "如果热点key在多个节点还是不均匀怎么办？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "深度问题"
      ]
    }
  ],
  "retrieval_text": "Redis热key问题排查",
  "source_type": "人工整理"
}
{
  "id": "hard_008",
  "role": "Java后端开发工程师",
  "question": "如何设计一个微服务架构下的分布式事务解决方案？",
  "category": "分布式系统",
  "subcategory": "微服务",
  "competency": [
    "analysis",
    "design",
    "architecture"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "分布式事务",
    "Seata",
    "Saga",
    "TCC"
  ],
  "tags": [
    "微服务",
    "分布式事务",
    "架构设计",
    "一致性"
  ],
  "answer_summary": "架构设计：1）流量分发：网关路由、权重配置、标签匹配；2）灰度策略：百分比、用户标签、地域、设备；3）配置管理：配置中心、动态下发、版本管理；4）监控告警：灰度监控、异常检测、一键回滚。实施要点：1）小流量验证：1%→5%→20%→100%；2）快速回滚：自动化回滚、预案准备；3）数据对比：AB 测试、指标对比。体现发布风险控制能力。",
  "key_points": [
    "CAP定理：一致性、可用性、分区容错性的权衡",
    "2PC/3PC原理和缺点",
    "TCC模式：Try-Confirm-Cancel、空回滚、幂等、悬挂问题",
    "Saga模式：编排式 vs 协作式、补偿事务",
    "可靠消息：RocketMQ事务消息、本地消息表"
  ],
  "optional_points": [
    "Seata的AT模式原理",
    "分布式id生成方案",
    "服务治理：限流、熔断、降级"
  ],
  "expected_answer_signals": [
    "方案理解",
    "能选型",
    "有实践"
  ],
  "common_mistakes": [
    "只会背概念",
    "不了解各方案代价",
    "无法正确选型"
  ],
  "scoring_rubric": {
    "basic": [
      "知道分布式事务概念"
    ],
    "good": [
      "理解各方案原理"
    ],
    "excellent": [
      "能正确选型，有实践经验"
    ]
  },
  "followups": [
    {
      "question": "TCC模式的空回滚和悬挂是如何产生的？如何解决？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "技术细节"
      ]
    },
    {
      "question": "如果业务无法配合改造，如何实现分布式事务？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "实际挑战"
      ]
    }
  ],
  "retrieval_text": "分布式事务解决方案",
  "source_type": "人工整理"
}
{
  "id": "hard_009",
  "role": "Java后端开发工程师",
  "question": "如何设计一个高效的分布式ID生成器？有哪些实现方案？",
  "category": "分布式系统",
  "subcategory": "基础组件",
  "competency": [
    "analysis",
    "design",
    "architecture"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "分布式ID",
    "雪花算法",
    "UUID",
    "唯一ID"
  ],
  "tags": [
    "分布式系统",
    "ID生成",
    "算法设计",
    "高并发"
  ],
  "answer_summary": "设计要点：1）数据采集：埋点 SDK、日志采集、实时上报；2）数据存储：时序数据库、冷热分离、数据压缩；3）实时计算：Flink/Spark Streaming 聚合、指标计算；4）告警引擎：规则引擎、智能告警、告警收敛；5）可视化：Dashboard、自定义图表、报表导出。优化：1）高性能：采样、聚合、降精度；2）低成本：数据 TTL、分层存储。体现监控体系设计能力。",
  "key_points": [
    "分布式ID要求：唯一性、递增性、高性能、高可用",
    "雪花算法原理：时间戳+机器ID+序列号",
    "号段模式：本地缓存+数据库同步，提升性能",
    "时钟回拨处理：等待、漂移补偿、异常处理",
    "机器ID分配：ZK、etcd、配置文件"
  ],
  "optional_points": [
    "TSF Snowflake优化",
    "组件贡献号段原理",
    "实际生产环境选型"
  ],
  "expected_answer_signals": [
    "方案理解",
    "能对比",
    "有深度"
  ],
  "common_mistakes": [
    "只知道雪花算法",
    "不了解时钟回拨问题",
    "无法对比选型"
  ],
  "scoring_rubric": {
    "basic": [
      "知道雪花算法"
    ],
    "good": [
      "理解各方案优缺点"
    ],
    "excellent": [
      "能针对场景选型，了解深度问题"
    ]
  },
  "followups": [
    {
      "question": "如果遇到时钟回拨，雪花算法如何处理？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "深度理解"
      ]
    },
    {
      "question": "如果需要支持分库分表，如何设计ID？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "扩展设计"
      ]
    }
  ],
  "retrieval_text": "分布式ID生成器设计",
  "source_type": "人工整理"
}
{
  "id": "hard_010",
  "role": "Java后端开发工程师",
  "question": "如何设计一个高可用的多级缓存架构？缓存穿透、击穿、雪崩如何处理？",
  "category": "缓存架构",
  "subcategory": "系统设计",
  "competency": [
    "analysis",
    "design",
    "architecture",
    "performance"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "system_design",
  "keywords": [
    "多级缓存",
    "缓存穿透",
    "缓存击穿",
    "缓存雪崩"
  ],
  "tags": [
    "缓存架构",
    "高可用",
    "系统设计",
    "性能优化"
  ],
  "answer_summary": "架构设计：1）配置存储：ZooKeeper/Etcd/Nacos，保证高可用；2）推送机制：长轮询、Watch 机制、推送 + 拉取；3）本地缓存：一级缓存快速读取、降级兜底；4）一致性：版本控制、CAS、最终一致；5）权限控制：RBAC、审计日志、灰度发布。核心问题：1）推送延迟：长轮询优化、推送优化；2）宕机恢复：本地缓存、自动重连；3）并发更新：乐观锁、版本控制。体现配置中心设计经验。",
  "key_points": [
    "多级缓存：本地缓存+Redis+数据库，各层特点",
    "缓存穿透：布隆过滤器、缓存空值、参数校验",
    "缓存击穿：互斥锁、永不过期+异步更新",
    "缓存雪崩：过期时间随机化、Redis高可用、降级熔断",
    "缓存一致性：延迟双删、订阅binlog"
  ],
  "optional_points": [
    "热点数据的特殊处理",
    "缓存预热方案",
    "CDN在缓存架构中的作用"
  ],
  "expected_answer_signals": [
    "架构清晰",
    "问题理解",
    "方案完整"
  ],
  "common_mistakes": [
    "只会单级缓存",
    "不了解缓存问题成因",
    "方案不够系统"
  ],
  "scoring_rubric": {
    "basic": [
      "知道缓存问题"
    ],
    "good": [
      "能设计架构和处理问题"
    ],
    "excellent": [
      "方案完整，有深度优化经验"
    ]
  },
  "followups": [
    {
      "question": "如何保证缓存和数据库的最终一致性？",
      "trigger_type": "deep_dive",
      "trigger_signals": [
        "一致性设计"
      ]
    },
    {
      "question": "如果Redis集群全部宕机，如何保证系统可用？",
      "trigger_type": "pressure_test",
      "trigger_signals": [
        "容错设计"
      ]
    }
  ],
  "retrieval_text": "高可用多级缓存架构设计",
  "source_type": "人工整理"
}
中等（10题）
{
  "id": "mid_001",
  "role": "Java后端开发工程师",
  "question": "接口RT波动如何分析？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "性能",
    "分析"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "分层排查：1）接入层：Nginx 负载、网络延迟；2）应用层：GC 停顿、线程池、慢查询；3）依赖层：数据库、Redis、MQ 响应时间；4）系统层：CPU、内存、IO。使用链路追踪（Skywalking）+ 监控（Prometheus）+ 日志（ELK）定位。结合真实场景说明排查思路。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何区分偶发问题？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何定位瓶颈？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_002",
  "role": "Java后端开发工程师",
  "question": "MySQL查询变慢如何处理？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "MySQL",
    "优化"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "排查步骤：1）定位慢 SQL：慢查询日志、performance_schema；2）分析执行计划：EXPLAIN 查看索引、扫描行数；3）优化方案：索引优化、SQL 改写、表分区、读写分离；4）验证效果：对比执行时间、执行计划。常见原因：索引失效、全表扫描、锁竞争、表结构不合理。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "先看执行计划吗？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何验证优化？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_003",
  "role": "Java后端开发工程师",
  "question": "缓存命中率下降如何处理？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "缓存",
    "命中"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "排查原因：1）key 设计问题：key 过期时间集中、key 分布不均；2）数据问题：热点数据迁移、数据倾斜；3）架构问题：Redis 节点增减导致 rehash；4）业务问题：新业务上线、活动导致访问模式变化。解决方案：1）优化 key 设计：分散过期时间；2）预热缓存：提前加载热点数据；3）本地缓存：二级缓存扛热点；4）监控告警：实时监控命中率。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何定位原因？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何恢复？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_004",
  "role": "Java后端开发工程师",
  "question": "线程池频繁拒绝任务怎么办？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "线程池",
    "拒绝"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "排查思路：1）确认现象：慢日志、线程 dump、监控指标；2）定位原因：大查询、锁等待、连接池耗尽、慢依赖；3）解决方案：索引优化、SQL 改写、连接池调优、异步化；4）预防措施：慢查询监控、超时设置、熔断降级。结合 EXPLAIN 和慢查询日志分析。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何调参？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "是否扩容？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_005",
  "role": "Java后端开发工程师",
  "question": "服务频繁超时如何排查？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "超时",
    "排查"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "分析步骤：1）确认泄漏：heap dump 对比、GC 日志分析；2）定位对象：MAT/JProfiler 分析对象引用链；3）常见原因：静态集合、未关闭资源、缓存无限制、ThreadLocal 未清理；4）解决方案：及时释放引用、使用弱引用、设置缓存上限、资源关闭。结合工具分析实战经验。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何分析链路？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何优化？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_006",
  "role": "Java后端开发工程师",
  "question": "如何设计接口限流策略？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "限流",
    "设计"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "设计要点：1）降级触发：超时、失败率、系统负载；2）降级策略：返回默认值、缓存数据、简化逻辑、关闭非核心功能；3）实现方式：Sentinel/Hystrix 熔断器、开关配置；4）恢复机制：自动恢复、手动恢复、灰度恢复。结合业务场景说明降级优先级。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何选算法？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何避免误伤？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_007",
  "role": "Java后端开发工程师",
  "question": "日志量过大如何优化？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "日志",
    "优化"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "处理流程：1）确认问题：日志对比、链路追踪、数据源对比；2）定位原因：参数传递、计算逻辑、数据源问题、并发问题；3）解决方案：统一数据源、增加校验、幂等设计、数据修复；4）预防措施：单元测试、集成测试、数据监控。强调问题排查的系统性。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何减少无效日志？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何存储？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_008",
  "role": "Java后端开发工程师",
  "question": "如何排查内存持续增长？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "内存",
    "排查"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "排查步骤：1）确认泄漏：监控内存趋势、GC 频率；2）定位对象：heap dump+MAT 分析大对象和引用链；3）常见原因：静态集合无限增长、缓存无淘汰、ThreadLocal 未清理、资源未关闭；4）解决方案：及时释放引用、设置缓存上限、使用弱引用、资源管理。结合工具分析经验。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何判断泄漏？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "用什么工具？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_009",
  "role": "Java后端开发工程师",
  "question": "如何设计服务降级？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "降级",
    "设计"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "设计要点：1）降级触发：超时、失败率、系统负载、人工开关；2）降级策略：返回默认值、缓存数据、简化逻辑、关闭非核心功能；3）实现方式：Sentinel/Hystrix 熔断器、配置中心开关；4）恢复机制：自动恢复、手动恢复、灰度恢复。结合业务场景说明降级优先级和预案。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "什么场景降级？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何恢复？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "mid_010",
  "role": "Java后端开发工程师",
  "question": "接口数据不一致如何处理？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "中等",
  "question_type": "场景分析",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "一致性",
    "接口"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "处理流程：1）确认问题：日志对比、链路追踪、多数据源对比；2）定位原因：参数传递、计算逻辑、数据源问题、并发修改、版本不一致；3）解决方案：统一数据源、增加校验、幂等设计、数据修复、优化事务；4）预防措施：单元测试、集成测试、数据监控告警。强调排查系统性和数据一致性保障。",
  "key_points": [],
  "optional_points": [
    "结合工具"
  ],
  "expected_answer_signals": [
    "分析",
    "定位"
  ],
  "common_mistakes": [
    "盲目优化"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何定位源头？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何修复？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
困难（10题）
{
  "id": "hard_001",
  "role": "Java后端开发工程师",
  "question": "设计一个高并发秒杀系统",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "秒杀",
    "架构"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "架构设计：1）流量层：CDN 加速、限流防刷、请求合并；2）缓存层：Redis 预扣库存、本地缓存热点；3）队列层：MQ 削峰填谷、异步下单；4）存储层：分库分表、库存分段。核心问题：1）不超卖：分布式锁、数据库乐观锁；2）高性能：缓存 + 队列、少写数据库；3）公平性：队列顺序、防刷机制。体现完整架构思维。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何削峰？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何保证一致性？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_002",
  "role": "Java后端开发工程师",
  "question": "设计一个可靠的分布式锁",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "分布式锁",
    "可靠性"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "设计要点：1）互斥性：SET NX、Redisson、ZK 顺序节点；2）可重入：线程 ID+ 计数器；3）锁超时：TTL 自动释放、看门狗续期；4）死锁防止：等待超时、锁检测；5）可靠性：Redis 主从切换、ZK 集群。方案对比：Redis 性能高但有主从一致性问题，ZK 强一致但性能低。结合业务场景选择。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何避免死锁？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何续期？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_003",
  "role": "Java后端开发工程师",
  "question": "设计高可用架构如何容灾？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "高可用",
    "容灾"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "容灾架构：1）多机房部署：同城双活、异地灾备；2）流量调度：DNS 智能解析、全局负载均衡；3）数据同步：主从复制、双向同步、数据校验；4）故障切换：自动检测、一键切换、预案演练；5）降级预案：核心功能优先、非核心降级。结合 CAP 理论说明取舍，强调演练重要性。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何多机房？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何切换？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_004",
  "role": "Java后端开发工程师",
  "question": "如何设计分布式事务系统？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "事务",
    "分布式"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "方案对比：1）2PC/3PC：强一致，性能差，不推荐；2）TCC：业务实现，性能好，实现复杂；3）Saga：长事务，可补偿，编排式/协作式；4）可靠消息：RocketMQ 事务消息，最终一致；5）Seata AT：自动补偿，无侵入，性能损耗 10-15%。选型建议：金融支付用 TCC/Seata，普通交易用消息队列。体现方案权衡能力。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何选方案？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何降级？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_005",
  "role": "Java后端开发工程师",
  "question": "设计日志平台如何支持搜索？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "日志",
    "搜索"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "架构设计：1）采集层：Filebeat/Flume 采集、Kafka 缓冲；2）存储层：Elasticsearch 索引、冷热分离；3）查询层：ES DSL、SQL 引擎、全文检索；4）优化：索引设计、分片策略、查询优化、缓存热点。搜索优化：1）倒排索引：分词器、mapping 设计；2）查询加速：filter 缓存、路由优化；3）大规模：滚动索引、force merge。体现 ELK 栈实战经验。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何索引？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何优化查询？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_006",
  "role": "Java后端开发工程师",
  "question": "设计推荐系统如何保证实时性？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "推荐",
    "实时"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "实时性保障：1）数据流：Flink/Storm 实时计算、Kafka 流处理；2）特征更新：实时特征存储、增量更新；3）模型更新：在线学习、模型热更新；4）服务架构：边缘计算、就近推荐、缓存预热。延迟优化：1）异步化：非阻塞 IO、响应式编程；2）缓存：多级缓存、预计算；3）降级：简化模型、规则推荐。体现实时系统架构能力。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何更新数据？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何降低延迟？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_007",
  "role": "Java后端开发工程师",
  "question": "设计支付系统如何防重复？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "支付",
    "幂等"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "防重设计：1）幂等性：唯一流水号、Token 机制、分布式锁；2）防重校验：请求参数 MD5、状态机控制、乐观锁；3）对账机制：T+1 对账、实时对账、差异处理；4）补偿机制：冲正、退款、人工处理。架构设计：1）前置校验：参数校验、黑名单；2）事中控制：幂等处理、分布式事务；3）事后对账：自动对账、异常告警。体现支付系统严谨性。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何设计幂等？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何对账？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_008",
  "role": "Java后端开发工程师",
  "question": "设计灰度发布系统",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "灰度",
    "发布"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "架构设计：1）流量分发：网关路由、权重配置、标签匹配；2）灰度策略：百分比、用户标签、地域、设备；3）配置管理：配置中心、动态下发、版本管理；4）监控告警：灰度监控、异常检测、一键回滚。实施要点：1）小流量验证：1%→5%→20%→100%；2）快速回滚：自动化回滚、预案准备；3）数据对比：AB 测试、指标对比。体现发布风险控制能力。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何控流？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何回滚？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_009",
  "role": "Java后端开发工程师",
  "question": "设计搜索系统如何提升性能？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "搜索",
    "性能"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "设计要点：1）数据采集：埋点 SDK、日志采集、实时上报；2）数据存储：时序数据库、冷热分离、数据压缩；3）实时计算：Flink/Spark Streaming 聚合、指标计算；4）告警引擎：规则引擎、智能告警、告警收敛；5）可视化：Dashboard、自定义图表、报表导出。优化：1）高性能：采样、聚合、降精度；2）低成本：数据 TTL、分层存储。体现监控体系设计能力。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何分片？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何缓存？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}
{
  "id": "hard_010",
  "role": "Java后端开发工程师",
  "question": "设计订单系统如何处理异常订单？",
  "category": "面试综合",
  "subcategory": "真实场景",
  "competency": [
    "analysis",
    "communication",
    "design"
  ],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": [
    "订单",
    "异常"
  ],
  "tags": [
    "真实面试场景",
    "能力评估",
    "深度追问",
    "技术判断"
  ],
  "answer_summary": "架构设计：1）配置存储：ZooKeeper/Etcd/Nacos，保证高可用；2）推送机制：长轮询、Watch 机制、推送 + 拉取；3）本地缓存：一级缓存快速读取、降级兜底；4）一致性：版本控制、CAS、最终一致；5）权限控制：RBAC、审计日志、灰度发布。核心问题：1）推送延迟：长轮询优化、推送优化；2）宕机恢复：本地缓存、自动重连；3）并发更新：乐观锁、版本控制。体现配置中心设计经验。",
  "key_points": [],
  "optional_points": [
    "架构对比"
  ],
  "expected_answer_signals": [
    "设计",
    "架构"
  ],
  "common_mistakes": [
    "无扩展性"
  ],
  "scoring_rubric": {
    "basic": [
      "能理解问题"
    ],
    "good": [
      "有逻辑"
    ],
    "excellent": [
      "深入分析+结构清晰"
    ]
  },
  "followups": [
    {
      "question": "如何补偿？",
      "trigger_type": "missing_analysis",
      "trigger_signals": []
    },
    {
      "question": "如何回滚？",
      "trigger_type": "missing_point",
      "trigger_signals": []
    }
  ],
  "retrieval_text": "真实面试问题",
  "source_type": "人工整理"
}