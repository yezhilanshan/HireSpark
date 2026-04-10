前端工程师面试题库

{
  "id": "fe_simple_001",
  "role": "前端工程师",
  "question": "React 的单向数据流是什么意思？父子组件、状态和渲染机制之间是什么关系？",
  "category": "前端/框架基础",
  "subcategory": "React基础",
  "competency": ["react", "component_design"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["React", "单向数据流", "状态", "渲染"],
  "tags": ["真实面经", "前端工程师", "React", "组件"],
  "answer_summary": "需要说明 React 中数据通常由父组件向子组件单向传递，状态变化会触发重新渲染，父子组件的更新关系和 props、state、渲染边界密切相关。",
  "key_points": ["状态通常上提到更靠上的组件管理", "父组件状态变化会影响依赖它的子组件", "props 是只读输入，state 是组件内部状态", "渲染是状态变化后的结果表达", "优化重点是减少不必要的子树更新"],
  "optional_points": ["可补充 React.memo、状态拆分等优化方式", "可说明 context 对数据流的影响"],
  "expected_answer_signals": ["props", "state", "重新渲染"],
  "common_mistakes": ["把单向数据流理解成组件之间不能通信", "只讲概念，不解释渲染触发关系"],
  "scoring_rubric": {
    "basic": ["能说明 React 数据是单向传递的"],
    "good": ["能说明父子组件与状态更新的关系"],
    "excellent": ["能进一步讲清渲染边界和优化思路"]
  },
  "followups": [
    {"question": "父组件触发子组件重新渲染时，有哪些常见优化空间？", "trigger_type": "missing_point", "trigger_signals": ["React.memo", "渲染"]},
    {"question": "如果状态放在父组件导致更新范围过大，你会怎么拆？", "trigger_type": "missing_detail", "trigger_signals": ["状态", "优化"]}
  ],
  "retrieval_text": "React 基础题，考察单向数据流、父子组件、state、props 和渲染机制之间的关系。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_simple_002",
  "role": "前端工程师",
  "question": "MobX 是如何在 React 工作流里工作的？它解决了什么问题，又可能带来哪些性能影响？",
  "category": "前端/状态管理",
  "subcategory": "React状态管理",
  "competency": ["react", "state_management"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["MobX", "Observable", "React", "状态管理"],
  "tags": ["真实面经", "前端工程师", "MobX", "状态管理"],
  "answer_summary": "需要说明 MobX 通过可观察状态和依赖追踪驱动组件更新，适合复杂共享状态和工作流建模；同时也要讲清粒度不当、依赖不清晰时可能造成的更新范围和性能问题。",
  "key_points": ["MobX 核心是可观察状态和响应式依赖追踪", "observer 组件会在依赖状态变化后重新渲染", "适合复杂共享状态和工作流编排", "若状态设计粒度过粗会扩大更新范围", "需要理解响应式链路才能正确排查问题"],
  "optional_points": ["可补充与 Zustand、Redux 的对比", "可说明在 Monorepo 或编辑器工作流中的使用场景"],
  "expected_answer_signals": ["Observable", "依赖追踪", "响应式更新"],
  "common_mistakes": ["只说 MobX 好用，但讲不清工作机制", "把性能问题简单归因于框架本身"],
  "scoring_rubric": {
    "basic": ["能说明 MobX 用来做共享状态管理"],
    "good": ["能解释可观察状态如何驱动 React 更新"],
    "excellent": ["能结合性能问题和实际工作流说明取舍"]
  },
  "followups": [
    {"question": "MobX 和 Zustand 在技术选型上你会怎么权衡？", "trigger_type": "missing_analysis", "trigger_signals": ["MobX", "Zustand"]},
    {"question": "如果组件没有按预期更新，你会从哪几步排查 MobX 响应链路？", "trigger_type": "missing_detail", "trigger_signals": ["响应式", "排查"]}
  ],
  "retrieval_text": "前端状态管理题，考察 MobX 在 React 工作流中的机制、价值和性能影响。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_simple_003",
  "role": "前端工程师",
  "question": "sessionStorage、localStorage、Cookie 分别适合存什么？JWT 为什么很多场景会放在 Cookie 里？",
  "category": "前端/网络与存储",
  "subcategory": "浏览器存储",
  "competency": ["browser", "web_security"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["sessionStorage", "localStorage", "Cookie", "JWT"],
  "tags": ["真实面经", "前端工程师", "浏览器存储", "认证"],
  "answer_summary": "需要说明三种存储方式的生命周期、作用域和安全差异，并解释 JWT 放在 Cookie 中常常是为了配合自动携带和 HttpOnly 等安全策略。",
  "key_points": ["sessionStorage 生命周期一般是单标签页会话级", "localStorage 持久化更长但需要手动携带", "Cookie 会随请求自动发送", "JWT 放在 Cookie 常结合 HttpOnly 和 SameSite 做安全控制", "存储方案要同时考虑安全性和使用便利性"],
  "optional_points": ["可补充 XSS 和 CSRF 风险差异", "可说明前后端分离下的携带方式"],
  "expected_answer_signals": ["生命周期", "自动携带", "安全性"],
  "common_mistakes": ["只记住谁能持久化，不讲安全差异", "把 Cookie 一概说成更安全"],
  "scoring_rubric": {
    "basic": ["能说清三种存储方式的生命周期差异"],
    "good": ["能解释 JWT 放 Cookie 的工程原因"],
    "excellent": ["能结合 XSS、CSRF 和自动携带机制说明取舍"]
  },
  "followups": [
    {"question": "如果 JWT 放在 localStorage，请求时一般如何携带？", "trigger_type": "missing_detail", "trigger_signals": ["JWT", "localStorage"]},
    {"question": "Cookie + HttpOnly 能防什么，不能防什么？", "trigger_type": "missing_analysis", "trigger_signals": ["HttpOnly", "安全"]}
  ],
  "retrieval_text": "浏览器存储与认证题，考察 sessionStorage、localStorage、Cookie 和 JWT 的使用场景与安全取舍。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_simple_004",
  "role": "前端工程师",
  "question": "强缓存和协商缓存分别是什么？它们对应的浏览器行为、字段和状态码有哪些？",
  "category": "前端/网络与浏览器",
  "subcategory": "缓存机制",
  "competency": ["browser", "network"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["强缓存", "协商缓存", "304", "Cache-Control", "ETag"],
  "tags": ["真实面经", "前端工程师", "缓存", "浏览器"],
  "answer_summary": "需要区分强缓存和协商缓存的命中逻辑、相关 HTTP 头和浏览器请求行为，并说明它们对性能和资源更新时效性的影响。",
  "key_points": ["强缓存命中时通常不会向服务器发起实际资源请求", "常见字段包括 Expires 和 Cache-Control", "协商缓存需要服务器参与确认资源是否变化", "常见字段包括 ETag、Last-Modified、If-None-Match、If-Modified-Since", "协商缓存命中常返回 304"],
  "optional_points": ["可补充 no-cache、no-store 的区别", "可说明多级缓存场景中的 CDN 影响"],
  "expected_answer_signals": ["Cache-Control", "ETag", "304"],
  "common_mistakes": ["只会背字段，不知道浏览器行为差别", "把 no-cache 和 no-store 混淆"],
  "scoring_rubric": {
    "basic": ["能区分强缓存和协商缓存"],
    "good": ["能说出关键头字段和状态码"],
    "excellent": ["能结合性能和资源更新策略做说明"]
  },
  "followups": [
    {"question": "强缓存命中和协商缓存命中时，Network 面板会有什么差异？", "trigger_type": "missing_detail", "trigger_signals": ["浏览器行为", "304"]},
    {"question": "为什么很多静态资源会偏向强缓存而 HTML 更常走协商缓存？", "trigger_type": "missing_analysis", "trigger_signals": ["资源更新", "缓存"]}
  ],
  "retrieval_text": "浏览器缓存题，考察强缓存、协商缓存、字段、状态码与浏览器行为。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_simple_005",
  "role": "前端工程师",
  "question": "SSE 和 WebSocket 有什么区别？为什么有些流式输出场景会优先选 SSE？",
  "category": "前端/网络与浏览器",
  "subcategory": "实时通信",
  "competency": ["network", "frontend_architecture"],
  "difficulty": "简单",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["SSE", "WebSocket", "流式输出", "单向通信"],
  "tags": ["真实面经", "前端工程师", "实时通信", "流式交互"],
  "answer_summary": "需要说明 SSE 是基于 HTTP 的服务端到客户端单向流，而 WebSocket 是全双工通道；像 LLM 流式输出这种以服务端持续推送为主的场景，SSE 往往实现更简单、协议更贴近需求。",
  "key_points": ["SSE 基于 HTTP，默认单向推送", "WebSocket 支持双向全双工通信", "SSE 更适合服务端持续输出文本流", "WebSocket 更适合频繁双向交互", "选型要看协议复杂度、基础设施支持和业务模式"],
  "optional_points": ["可补充断线恢复、代理兼容性和负载均衡影响", "可说明消息顺序和流控差异"],
  "expected_answer_signals": ["单向推送", "全双工", "流式输出"],
  "common_mistakes": ["把 SSE 说成只是弱化版 WebSocket", "忽略基础设施和场景差异"],
  "scoring_rubric": {
    "basic": ["能区分 SSE 和 WebSocket 的通信方式"],
    "good": ["能解释为什么流式输出场景常选 SSE"],
    "excellent": ["能结合重连、代理兼容和工程复杂度做比较"]
  },
  "followups": [
    {"question": "如果 SSE 连接断了，你会如何恢复流式输出？", "trigger_type": "missing_detail", "trigger_signals": ["SSE", "断开"]},
    {"question": "如果用户点击停止，前后端各自应该怎样处理中止？", "trigger_type": "missing_analysis", "trigger_signals": ["停止", "流式"]}
  ],
  "retrieval_text": "实时通信选型题，考察 SSE、WebSocket 的区别以及流式输出场景的选型理由。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_simple_006",
  "role": "前端工程师",
  "question": "LCP 是什么？前端页面性能通常会关注哪些指标，你会如何做性能优化？",
  "category": "前端/性能优化",
  "subcategory": "Web Vitals",
  "competency": ["performance", "frontend_architecture"],
  "difficulty": "简单",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "screening",
  "keywords": ["LCP", "性能指标", "性能优化", "Web Vitals"],
  "tags": ["真实面经", "前端工程师", "性能优化", "Web Vitals"],
  "answer_summary": "需要说明 LCP、FCP、CLS、INP/TBT 等常见指标的含义，并能从资源加载、渲染阻塞、代码拆分、图片优化和缓存策略等方面给出优化思路。",
  "key_points": ["LCP 关注最大可见内容渲染完成时间", "性能指标要结合加载、交互和稳定性来看", "优化手段包括资源压缩、懒加载、预加载、代码拆分", "首屏性能常与关键资源路径有关", "指标要通过真实监控与实验室分析结合判断"],
  "optional_points": ["可补充首屏白屏问题分析", "可说明如何埋点采集 Web Vitals"],
  "expected_answer_signals": ["LCP", "渲染阻塞", "代码拆分"],
  "common_mistakes": ["只会背指标名字，不知道怎么优化", "只看实验室分数，不看真实用户数据"],
  "scoring_rubric": {
    "basic": ["能说清 LCP 的含义和几个核心指标"],
    "good": ["能给出对应的性能优化思路"],
    "excellent": ["能结合真实监控、首屏链路和业务场景展开"]
  },
  "followups": [
    {"question": "如果页面上线后出现 3 秒白屏，你会如何分层排查？", "trigger_type": "missing_analysis", "trigger_signals": ["白屏", "性能"]},
    {"question": "LCP 过高时，你会优先检查哪些资源和渲染链路？", "trigger_type": "missing_detail", "trigger_signals": ["LCP", "优化"]}
  ],
  "retrieval_text": "前端性能题，考察 LCP、Web Vitals 和常见性能优化手段。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_001",
  "role": "前端工程师",
  "question": "Vue3 的响应式机制和编译渲染流程分别是怎样的？为什么有些项目会选 Vue3 而不是 React？",
  "category": "前端/框架基础",
  "subcategory": "Vue基础",
  "competency": ["vue", "frontend_architecture"],
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Vue3", "响应式", "编译渲染", "React 对比"],
  "tags": ["真实面经", "前端工程师", "Vue", "技术选型"],
  "answer_summary": "回答应说明 Vue3 基于 Proxy 的响应式追踪和 template -> render function -> patch 的渲染流程，再从团队背景、开发体验、模板系统和生态成本等角度解释技术选型。",
  "key_points": ["Vue3 响应式核心是 Proxy + effect 依赖收集", "模板会被编译成 render function", "渲染流程通常经历生成 vnode、diff 和 patch", "Vue3 在模板开发、上手成本和一体化体验上常有优势", "选型还要结合团队经验和项目类型"],
  "optional_points": ["可补充编译时优化、静态提升和 patch flag", "可说明 React 与 Vue 在心智模型上的差异"],
  "expected_answer_signals": ["Proxy", "effect", "render function"],
  "common_mistakes": ["只会说 Vue 响应式更方便，不会讲机制", "技术选型只从个人偏好出发"],
  "scoring_rubric": {
    "basic": ["能说明 Vue3 响应式和渲染的大致流程"],
    "good": ["能对比 Vue3 和 React 的主要差异"],
    "excellent": ["能从机制、团队和项目约束三个层面说明选型"]
  },
  "followups": [
    {"question": "Vue3 为什么从 defineProperty 转向 Proxy？", "trigger_type": "missing_detail", "trigger_signals": ["Proxy", "响应式"]},
    {"question": "如果让你为某个新项目选 React 还是 Vue3，你会看哪些因素？", "trigger_type": "missing_analysis", "trigger_signals": ["选型", "Vue3"]}
  ],
  "retrieval_text": "Vue3 基础与选型题，考察响应式、编译渲染流程以及 Vue3 和 React 的技术取舍。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_002",
  "role": "前端工程师",
  "question": "Vite 和 Webpack 的构建流程、核心区别是什么？你会如何解释为什么项目要选 Vite 或 Webpack？",
  "category": "前端/工程化",
  "subcategory": "构建工具",
  "competency": ["build_tooling", "frontend_architecture"],
  "difficulty": "中等",
  "question_type": "工程化",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["Vite", "Webpack", "构建流程", "工程化"],
  "tags": ["真实面经", "前端工程师", "工程化", "构建工具"],
  "answer_summary": "需要说明 Webpack 的 bundle-first 思路和 Vite 的 dev 阶段原生 ESM 按需加载机制，再结合启动速度、生态兼容性、插件体系和生产构建说明选型理由。",
  "key_points": ["Webpack 开发期通常也会走打包流程", "Vite 开发期更多依赖原生 ESM 和按需编译", "两者生产构建都会做 bundle 优化", "Vite 启动和热更新通常更快", "Webpack 在复杂生态和深度定制上仍有优势"],
  "optional_points": ["可补充 HMR 差异和插件模型", "可说明 monorepo 场景下的取舍"],
  "expected_answer_signals": ["ESM", "bundle", "HMR"],
  "common_mistakes": ["只说 Vite 快，不解释为什么", "忽略生产构建和开发阶段的区别"],
  "scoring_rubric": {
    "basic": ["能说明 Vite 和 Webpack 的核心差别"],
    "good": ["能解释它们在开发和构建阶段的不同流程"],
    "excellent": ["能结合项目复杂度和生态兼容给出选型建议"]
  },
  "followups": [
    {"question": "为什么 Vite 在开发环境通常比 Webpack 冷启动更快？", "trigger_type": "missing_detail", "trigger_signals": ["Vite", "启动"]},
    {"question": "如果一个项目历史包袱很重，你还会优先迁到 Vite 吗？", "trigger_type": "missing_analysis", "trigger_signals": ["迁移", "Webpack"]}
  ],
  "retrieval_text": "前端工程化题，考察 Vite 和 Webpack 的构建流程、差异和技术选型理由。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_003",
  "role": "前端工程师",
  "question": "浏览器中进程和线程是怎么划分的？JS 事件循环是如何工作的？",
  "category": "前端/浏览器原理",
  "subcategory": "运行时机制",
  "competency": ["browser", "javascript"],
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["进程", "线程", "事件循环", "浏览器"],
  "tags": ["真实面经", "前端工程师", "浏览器原理", "JavaScript"],
  "answer_summary": "需要说明浏览器多进程架构、渲染进程中的主线程、网络线程等角色，并讲清宏任务、微任务和渲染时机在事件循环中的关系。",
  "key_points": ["浏览器通常采用多进程架构隔离页面和服务", "一个 tab 通常对应一个或多个相关进程", "JS 主要运行在渲染进程主线程", "事件循环负责调度宏任务、微任务和渲染", "理解事件循环有助于分析异步输出和性能问题"],
  "optional_points": ["可补充 WebWorker 与主线程关系", "可说明渲染时机与 requestAnimationFrame 的联系"],
  "expected_answer_signals": ["宏任务", "微任务", "渲染进程"],
  "common_mistakes": ["把线程和任务队列概念混淆", "只会背 event loop 定义，不会落到浏览器场景"],
  "scoring_rubric": {
    "basic": ["能说清浏览器进程线程和事件循环的基本概念"],
    "good": ["能解释宏任务、微任务和渲染的执行关系"],
    "excellent": ["能结合具体异步输出案例或性能问题分析"]
  },
  "followups": [
    {"question": "Promise.then、setTimeout 和 requestAnimationFrame 在事件循环里分别处于什么位置？", "trigger_type": "missing_detail", "trigger_signals": ["Promise", "setTimeout"]},
    {"question": "两个进程之间如何通信，在浏览器里有哪些实际例子？", "trigger_type": "missing_point", "trigger_signals": ["进程通信"]}
  ],
  "retrieval_text": "浏览器原理题，考察进程线程划分、JS 执行环境和事件循环机制。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_004",
  "role": "前端工程师",
  "question": "闭包是什么？它的应用场景、潜在问题，以及用闭包实现私有变量时需要注意什么？",
  "category": "前端/JavaScript基础",
  "subcategory": "作用域与闭包",
  "competency": ["javascript", "coding"],
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["闭包", "作用域链", "私有变量", "内存泄漏"],
  "tags": ["真实面经", "前端工程师", "JavaScript", "闭包"],
  "answer_summary": "需要说明闭包是函数与其词法环境的组合，常用于私有变量、函数工厂和回调场景；同时要讲清闭包可能导致的对象长期持有和内存泄漏问题。",
  "key_points": ["闭包与词法作用域和作用域链相关", "可用来封装私有变量和形成状态", "常见场景包括模块封装、回调、函数工厂", "若错误持有大对象可能造成内存泄漏", "排查时要关注引用链和生命周期"],
  "optional_points": ["可补充 new、构造函数与闭包配合使用的差异", "可说明现代 class 私有字段与闭包封装的对比"],
  "expected_answer_signals": ["词法作用域", "私有变量", "内存泄漏"],
  "common_mistakes": ["把闭包简单理解成函数嵌套函数", "讲不清为什么会造成内存泄漏"],
  "scoring_rubric": {
    "basic": ["能说明闭包和词法作用域的关系"],
    "good": ["能说出应用场景和潜在风险"],
    "excellent": ["能结合私有变量实现和内存排查做完整说明"]
  },
  "followups": [
    {"question": "如果使用闭包造成了内存泄漏，你会如何排查和解决？", "trigger_type": "missing_detail", "trigger_signals": ["内存泄漏", "排查"]},
    {"question": "用构造函数和闭包实现私有变量时，`new` 的行为会影响什么？", "trigger_type": "missing_analysis", "trigger_signals": ["new", "构造函数"]}
  ],
  "retrieval_text": "JavaScript 基础题，考察闭包、作用域链、私有变量实现和内存泄漏问题。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_005",
  "role": "前端工程师",
  "question": "输入 URL 之后会发生什么？CDN、Nginx、HTTPS、defer/async 和常见状态码在这条链路里分别扮演什么角色？",
  "category": "前端/网络与浏览器",
  "subcategory": "请求链路",
  "competency": ["network", "browser", "deployment"],
  "difficulty": "中等",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["输入URL", "CDN", "Nginx", "HTTPS", "defer", "async"],
  "tags": ["真实面经", "前端工程师", "网络链路", "部署"],
  "answer_summary": "需要按 DNS、TCP/HTTPS、请求转发、资源加载、解析执行、渲染呈现这条链路讲清楚，并把 CDN、Nginx、脚本加载属性和状态码放到正确的位置上。",
  "key_points": ["输入 URL 后会经历解析、DNS、建连、请求、响应和渲染", "HTTPS 握手用于安全协商和密钥交换", "CDN 主要做静态资源分发和就近访问", "Nginx 常承担反向代理和静态资源服务", "defer 和 async 影响脚本下载与执行时机"],
  "optional_points": ["可补充缓存命中和 Service Worker", "可说明 404、503、301、302 等状态码的语义"],
  "expected_answer_signals": ["DNS", "TCP/HTTPS", "资源加载"],
  "common_mistakes": ["链路顺序混乱", "把 defer 和 async 说成只影响下载不影响执行"],
  "scoring_rubric": {
    "basic": ["能说清输入 URL 后的大致流程"],
    "good": ["能把 CDN、HTTPS、脚本加载放到正确环节"],
    "excellent": ["能结合缓存、代理和渲染过程做完整分析"]
  },
  "followups": [
    {"question": "defer 和 async 的下载与执行顺序有什么差异？", "trigger_type": "missing_detail", "trigger_signals": ["defer", "async"]},
    {"question": "如果线上出现 503，你会优先从哪些层面排查？", "trigger_type": "missing_analysis", "trigger_signals": ["503", "排查"]}
  ],
  "retrieval_text": "网络链路题，考察输入 URL 后发生什么，以及 CDN、Nginx、HTTPS、defer/async、状态码的作用。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_006",
  "role": "前端工程师",
  "question": "CSS 布局中如何实现左右两栏、居中布局？display:none、visibility:hidden、opacity:0 以及 v-if、v-show 有什么区别？",
  "category": "前端/CSS与布局",
  "subcategory": "布局与显示",
  "competency": ["css", "vue"],
  "difficulty": "中等",
  "question_type": "技术基础",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["CSS布局", "居中", "display none", "visibility hidden", "v-if", "v-show"],
  "tags": ["真实面经", "前端工程师", "CSS", "Vue"],
  "answer_summary": "需要能给出 flex、grid、定位等布局方案，并解释不同隐藏方式和 v-if/v-show 在 DOM、布局、交互和性能上的差异。",
  "key_points": ["左右布局可用 flex、grid 或定位方案实现", "居中常见方法包括 flex、grid、transform", "display:none 会移除布局占位", "visibility:hidden 保留占位但不可见", "opacity:0 仍可能响应事件，v-if/v-show 区别在于是否真实销毁节点"],
  "optional_points": ["可补充 BFC、盒模型和 transform/translate 区别", "可说明动画与隐藏方式的组合使用"],
  "expected_answer_signals": ["flex", "占位", "DOM 销毁"],
  "common_mistakes": ["只会说现象，不会解释渲染和布局影响", "把 v-if 和 v-show 完全等同于 display 切换"],
  "scoring_rubric": {
    "basic": ["能给出常见布局方案并说清几种隐藏方式差异"],
    "good": ["能说明 v-if/v-show 在性能和渲染上的区别"],
    "excellent": ["能结合交互、动画和工程场景给出合理选择"]
  },
  "followups": [
    {"question": "如果一个元素不可见但还要保留交互或动画，应该怎么选？", "trigger_type": "missing_analysis", "trigger_signals": ["opacity", "visibility"]},
    {"question": "左右定宽+自适应布局除了 flex 还有哪些可行写法？", "trigger_type": "missing_detail", "trigger_signals": ["布局", "自适应"]}
  ],
  "retrieval_text": "CSS 布局基础题，考察两栏布局、居中、隐藏方式和 v-if/v-show 的区别。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_mid_007",
  "role": "前端工程师",
  "question": "防抖和节流分别是什么？你会如何手写一个防抖函数，并解释适用场景？",
  "category": "前端/JavaScript基础",
  "subcategory": "高频手写",
  "competency": ["javascript", "coding"],
  "difficulty": "中等",
  "question_type": "编程实现",
  "round_type": "technical",
  "question_intent": "coding",
  "keywords": ["防抖", "节流", "debounce", "throttle"],
  "tags": ["真实面经", "前端工程师", "手撕代码", "JavaScript"],
  "answer_summary": "需要说明防抖和节流的语义差异，能手写基本版本，并指出定时器清理、this 绑定、参数透传、立即执行等细节。",
  "key_points": ["防抖关注最后一次触发", "节流关注单位时间内最多执行一次", "实现时要处理 timer、this、参数和返回值", "要结合输入框、滚动、按钮点击等场景说明使用方式", "高级版本还要考虑 leading/trailing"],
  "optional_points": ["可补充 requestAnimationFrame 节流", "可说明 React 中配合 hooks 的写法"],
  "expected_answer_signals": ["timer", "this", "参数透传"],
  "common_mistakes": ["只会背概念，代码写不完整", "不知道防抖和节流各适合什么场景"],
  "scoring_rubric": {
    "basic": ["能区分防抖和节流，并写出基本防抖"],
    "good": ["能处理 this、参数和清理逻辑"],
    "excellent": ["能扩展到立即执行、取消和不同应用场景"]
  },
  "followups": [
    {"question": "如果要支持立即执行和取消功能，你会怎么改？", "trigger_type": "missing_detail", "trigger_signals": ["immediate", "cancel"]},
    {"question": "搜索建议和窗口 resize 各更适合防抖还是节流？为什么？", "trigger_type": "missing_analysis", "trigger_signals": ["场景", "防抖", "节流"]}
  ],
  "retrieval_text": "JavaScript 手写题，考察防抖、节流的区别、实现细节和使用场景。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_hard_001",
  "role": "前端工程师",
  "question": "在 LLM 流式对话场景里，如果用户刷新页面或切换会话后再回来，怎么保证 SSE 输出可以继续、不中断体验？",
  "category": "前端/AI应用工程",
  "subcategory": "流式交互",
  "competency": ["frontend_architecture", "network", "llm_application"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["SSE", "流式输出", "断线恢复", "会话恢复"],
  "tags": ["真实面经", "前端工程师", "AI应用", "流式交互"],
  "answer_summary": "回答应围绕消息持久化、服务端任务状态、断线续传、游标/offset、重建连接和前端渲染恢复展开，重点是不能把刷新页面简单当成一次新的请求。",
  "key_points": ["流式会话需要有稳定的 message/task id", "前端要持久化当前会话和已接收片段", "服务端要能查询生成任务当前状态", "重连后需要基于 offset 或已完成片段恢复", "体验上要避免重复 token 和状态错乱"],
  "optional_points": ["可补充 Last-Event-ID、消息序列号或数据库落盘方案", "可说明 SSE 与 fetch stream 的恢复差异"],
  "expected_answer_signals": ["task id", "断线恢复", "去重"],
  "common_mistakes": ["只说重新发一遍请求", "忽略服务端状态管理和重复片段问题"],
  "scoring_rubric": {
    "basic": ["能意识到刷新后需要恢复而不是重开一轮"],
    "good": ["能给出前后端协同的恢复机制"],
    "excellent": ["能考虑去重、状态一致性和用户体验细节"]
  },
  "followups": [
    {"question": "SSE 本身不是双向协议，你会如何让服务端知道客户端想要恢复到哪一段？", "trigger_type": "missing_detail", "trigger_signals": ["恢复", "offset"]},
    {"question": "如果前端只是取消 fetch，但后端生成任务还在跑，你会怎么处理？", "trigger_type": "missing_analysis", "trigger_signals": ["停止", "后端任务"]}
  ],
  "retrieval_text": "AI 前端系统设计题，考察 SSE 流式对话在刷新、切会话和断线场景下的恢复方案。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_hard_002",
  "role": "前端工程师",
  "question": "为什么会有给 AI 用的 sandbox？它解决了什么问题，在前端 AI coding 或 playground 场景里有什么价值？",
  "category": "前端/AI应用工程",
  "subcategory": "沙箱与隔离",
  "competency": ["frontend_architecture", "security", "llm_application"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["sandbox", "AI coding", "隔离", "playground"],
  "tags": ["真实面经", "前端工程师", "AI应用", "安全隔离"],
  "answer_summary": "回答应说明 sandbox 的核心价值在于权限隔离、资源控制、环境可重现和降低不可信代码执行风险，尤其是在 AI 生成代码、工具调用和在线运行时非常关键。",
  "key_points": ["sandbox 主要解决不可信代码执行风险", "需要隔离文件系统、网络、进程和敏感权限", "还能提供资源限制和可重置环境", "AI coding 场景里便于安全执行生成代码和工具调用", "设计上还要考虑用户体验、调试能力和性能成本"],
  "optional_points": ["可补充 iframe、WebContainer、容器化等实现思路", "可说明前端和后端沙箱边界不同"],
  "expected_answer_signals": ["权限隔离", "资源控制", "可重现环境"],
  "common_mistakes": ["只把 sandbox 理解成安全问题", "不提资源控制和环境一致性"],
  "scoring_rubric": {
    "basic": ["能说明 sandbox 是为了隔离不可信代码"],
    "good": ["能说明它在 AI coding 或 playground 中的具体价值"],
    "excellent": ["能结合安全、资源、调试和产品体验做完整分析"]
  },
  "followups": [
    {"question": "如果只是前端沙箱，哪些风险仍然无法完全避免？", "trigger_type": "missing_detail", "trigger_signals": ["前端沙箱", "风险"]},
    {"question": "沙箱和普通预览环境相比，最大的设计差异是什么？", "trigger_type": "missing_analysis", "trigger_signals": ["预览环境", "隔离"]}
  ],
  "retrieval_text": "AI coding 前端系统题，考察 sandbox 的作用、隔离边界和在 playground/Agent 场景中的价值。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
{
  "id": "fe_hard_003",
  "role": "前端工程师",
  "question": "国际化系统如果要支持同一条帖子对不同地区用户展示不同语言，你会怎么设计翻译时机、缓存和实时性？",
  "category": "前端/应用架构",
  "subcategory": "国际化与内容系统",
  "competency": ["frontend_architecture", "i18n", "system_design"],
  "difficulty": "困难",
  "question_type": "系统设计",
  "round_type": "technical",
  "question_intent": "deep_dive",
  "keywords": ["国际化", "翻译缓存", "实时性", "论坛系统"],
  "tags": ["真实面经", "前端工程师", "国际化", "系统设计"],
  "answer_summary": "回答应区分静态文案国际化和用户内容翻译，重点说明翻译是写时生成还是读时生成、如何做多语言缓存、怎样在保证实时性的同时避免重复翻译。",
  "key_points": ["静态文案 i18n 和用户内容翻译是两类问题", "翻译时机可以是发布时、首次访问时或异步回填", "需要按原文 hash、语言对和版本做缓存", "实时性要求高时要设计回源与异步更新策略", "还要考虑翻译质量、审核和编辑后的失效处理"],
  "optional_points": ["可补充多语言内容存储模型", "可说明热门内容预翻译和长尾内容懒翻译策略"],
  "expected_answer_signals": ["翻译时机", "缓存键", "实时性"],
  "common_mistakes": ["只说接个翻译接口就行", "忽视缓存失效和内容更新问题"],
  "scoring_rubric": {
    "basic": ["能区分静态国际化和动态内容翻译"],
    "good": ["能设计翻译时机和缓存方案"],
    "excellent": ["能同时兼顾实时性、成本和内容一致性"]
  },
  "followups": [
    {"question": "如果同样的文本出现很多次，后端是否每次都要翻译？你会如何去重？", "trigger_type": "missing_detail", "trigger_signals": ["缓存", "去重"]},
    {"question": "如果帖子被编辑后，已有翻译缓存应该怎么处理？", "trigger_type": "missing_analysis", "trigger_signals": ["失效", "更新"]}
  ],
  "retrieval_text": "前端系统设计题，考察国际化、动态内容翻译、缓存策略和实时性之间的权衡。",
  "source": "basic_knowledge/mianjing2.md",
  "source_type": "面经整理"
}
