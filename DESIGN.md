# Listen and Learn — 项目大纲与完整细节设计

> **状态**: 设计阶段，待用户确认后进入编码阶段
> **日期**: 2026-06-21

---

## 一、项目概述

### 1.1 项目定位
个人专属的 AI 播客 + 知识库全栈应用。每天通过 AI 采集 6 大领域的新闻，生成中英双语播客音频供聆听，同时维护一个持续积累的中文知识库。用户反馈驱动 Agent 持续优化。

### 1.2 核心功能
| 模块 | 功能 |
|------|------|
| **AI 播客** | 每日生成中/英两份 ~10 分钟双主持人对谈播客，支持音频播放、文案查看、反馈提交 |
| **知识库** | 基于 LLM Wiki 理念的中文知识库，包含文字+图片，支持搜索、浏览、自动更新 |
| **Agent 系统** | 多 Agent 协作的 Harness 架构，含任务拆解、工具调用、监控测评、数据驱动优化 |

### 1.3 关注领域（6 个，每个每日 5 条新闻）
1. AI（人工智能）
2. 互联网
3. 智能制造
4. 具身智能
5. Web3
6. 国际政治形势

### 1.4 AI 供应商严格划分
| 用途 | 供应商 | 模型/接口 | 说明 |
|------|--------|-----------|------|
| **音频生成（仅此一项）** | Boson.ai | `higgs-audio-v3-tts` | 唯一的 TTS 来源 |
| **其余全部 AI 功能** | 智谱AI | `glm-5.1`（glm-5.1 系列） | 联网搜索、文案生成、知识库维护、反馈优化、Agent 编排等，仅文本任务 |

---

## 二、技术栈

### 2.1 后端
| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11 | 用户指定 |
| Web 框架 | FastAPI | 异步、自动文档、适合 Agent 长任务 |
| 数据库 | SQLite | 个人应用，轻量零运维 |
| 任务队列 | asyncio + 后台线程 | 单用户场景无需 Celery |
| AI 文本 | zai-sdk（智谱官方 SDK） | `pip install zai-sdk`，调用 glm-5.1 |
| AI 音频 | requests（调用 Boson REST API） | POST `https://api.boson.ai/v1/audio/speech` |
| HTTP 客户端 | httpx | 抓取新闻网页、下载图片 |
| Markdown 渲染 | markdown（后端渲染为 HTML） | 知识库页面返回 |
| 进程管理 | systemd | 服务器常驻服务 |

### 2.2 安卓客户端
| 组件 | 选型 |
|------|------|
| 语言 | Kotlin |
| UI | Jetpack Compose + Material 3 |
| 架构 | MVVM + Repository |
| 网络 | Retrofit + OkHttp |
| 音频播放 | Media3 (ExoPlayer) |
| 本地存储 | DataStore（后端地址）、Room（播客缓存） |
| Markdown 渲染 | Markwon |
| 图片加载 | Coil |

### 2.3 部署
| 组件 | 说明 |
|------|------|
| 服务器 | 49.232.226.131（SSH root@49.232.226.131 -p22） |
| 服务端口 | 8000（FastAPI uvicorn） |
| 反向代理 | Nginx（HTTPS 可选，先用 HTTP） |
| 进程管理 | systemd service |
| 一键部署 | `deploy.sh` 脚本，本地执行，自动 rsync + SSH 远程安装 |

---

## 三、Agent 架构设计（Harness Agent）

### 3.1 设计宗旨
体现 Harness Agent 理念：**一个 Agent 框架（harness）负责编排、工具注入、日志监控、错误恢复，多个专职 Agent 在框架内协作**。每个 Agent 有明确角色、专属工具集、独立的 prompt 版本管理，所有调用可观测、可测评、可优化。

### 3.2 Agent 角色总览

```
┌─────────────────────────────────────────────────────────┐
│                    Harness 框架层                         │
│  (编排调度 / 工具注册 / 日志监控 / 错误重试 / 测评引擎)    │
└─────────────────────────────────────────────────────────┘
        │
        ├── ① Orchestrator Agent（编排 Agent）
        │       接收用户意图 → 任务拆解 → 分配子任务 → 汇总结果
        │
        ├── ② News Collector Agent（新闻采集 Agent）
        │       按领域联网搜索 → 抓取正文 → 提取图片 → 结构化输出
        │
        ├── ③ Knowledge Base Agent（知识库 Agent）
        │       Ingest 新闻 → 更新 Wiki 页面 → 维护索引/日志 → 搜索
        │
        ├── ④ Podcast Script Writer Agent（播客文案 Agent）
        │       读取新闻+KB → 生成双人对谈文案(中/英) → 嵌入TTS标签
        │
        ├── ⑤ Audio Producer Agent（音频制作 Agent）
        │       解析文案 → 按说话人分段 → 调用 Boson API → 拼接音频
        │
        ├── ⑥ Feedback Optimizer Agent（反馈优化 Agent）
        │       分析用户反馈 → 调整 prompt/参数 → 触发 KB 更新
        │
        └── ⑦ Evaluation Agent（测评 Agent）
                周期性评估各 Agent → 检测 badcase → 生成优化建议
```

### 3.3 各 Agent 详细设计

#### ① Orchestrator Agent（编排 Agent）
- **职责**: 接收顶层意图（生成播客 / 更新知识库 / 处理反馈），拆解为有序子任务，分配给对应 Agent，监控执行状态，处理失败重试，汇总最终结果。
- **模型**: glm-5.1，使用 `tools` (function calling) 进行任务分发
- **核心工具**:
  - `dispatch_to_agent(agent_name, task_input)` — 将子任务分发给指定 Agent
  - `check_agent_status(task_id)` — 查询子任务状态
  - `retry_task(task_id)` — 失败重试
- **任务拆解策略**: 将"生成今日播客"拆为：
  1. `news_collector.collect(domain)` × 6 领域（可并行）
  2. `knowledge_base.ingest(news_items)` — 更新知识库
  3. `script_writer.write(news_items, kb_context)` — 生成中英文案
  4. `audio_producer.produce(script_zh)` + `audio_producer.produce(script_en)` — 生成音频（可并行）
- **输出**: job 状态 + 各阶段结果汇总

#### ② News Collector Agent（新闻采集 Agent）
- **职责**: 针对每个领域，搜索前一天的新闻，精选 5 条，提取标题、摘要、来源 URL、图片，结构化输出。
- **模型**: glm-5.1
- **核心工具**:
  - `web_search(query)` — 智谱 web_search 工具，联网搜索
  - `fetch_article(url)` — httpx 抓取网页正文（抽取正文+图片URL）
  - `download_image(url, save_path)` — 下载图片到本地
  - `summarize_article(content)` — glm-5.1 生成摘要
- **工作流**:
  1. GLM-5.2 根据领域生成搜索关键词（如"AI 人工智能 最新进展 2026-06-20"）
  2. 调用 web_search 获取搜索结果
  3. 对每个结果调用 fetch_article 获取正文
  4. 调用 summarize_article 生成中文摘要
  5. 提取并下载 1 张配图
  6. 输出结构化 news_item: `{domain, title_zh, title_en, summary_zh, source_url, image_path, date}`
- **并发**: 6 个领域并行执行

#### ③ Knowledge Base Agent（知识库 Agent）
- **职责**: 遵循 Karpathy LLM Wiki 理念，将新闻素材增量整合到持久化 Wiki 中，维护交叉引用、索引、日志，提供搜索。
- **模型**: glm-5.1
- **核心工具**:
  - `read_wiki_page(path)` — 读取现有 Wiki 页面
  - `write_wiki_page(path, content)` — 写入/更新 Wiki 页面
  - `update_index()` — 更新 index.md
  - `append_log(entry)` — 追加 log.md
  - `search_wiki(query)` — 搜索 Wiki（基于 index + 全文检索）
  - `lint_wiki()` — 健康检查（孤立页面、矛盾、过期信息）
- **Wiki 结构**: 见第五节
- **语言**: 纯中文

#### ④ Podcast Script Writer Agent（播客文案 Agent）
- **职责**: 基于当日新闻 + 知识库上下文，生成 ~10 分钟双主持人对谈文案，中英各一份（内容相同），并在文案中嵌入 Boson TTS 控制标签。
- **模型**: glm-5.1
- **主持人设定**:
  - 男主持: voice=`marcus`（热情、自信、略带教授风格）
  - 女主持: voice=`chloe`（友好、清晰、引人入胜）
- **文案格式**（关键设计）:
  ```
  [MARCUS]: <|emotion:enthusiasm|>欢迎收听 Listen and Learn！<|prosody:pause|>今天我们来聊聊昨天科技圈的大事。
  [CHLOE]: <|emotion:amusement|><|sfx:laughter|>Haha，我已经迫不及待了！先从 AI 领域开始吧。
  [MARCUS]: <|emotion:contemplation|>好的。昨天最大的新闻是...
  ```
  - 每行以 `[MARCUS]:` 或 `[CHLOE]:` 开头标识说话人
  - 标签直接内嵌在文本中（`<|emotion:xxx|>`、`<|prosody:pause|>`、`<|sfx:laughter|>` 等）
  - 文案 Agent 在生成时即考虑标签的合理使用，让播客生动鲜活
- **生成策略**:
  1. 先用 GLM-5.1 基于新闻素材生成中文文案（含标签）
  2. 再用 GLM-5.1 将中文文案翻译为英文（保持内容一致、保留标签结构）
  3. **英文核对环节**: 翻译完成后，用 GLM-5.1 将英文文案与原始新闻素材（含英文原文标题、来源URL）进行核对，修正专有名词（公司名、产品名、功能名、技术术语等）的翻译，确保不硬翻译。例如 "OpenAI" 不应翻译为"开放AI"，"ChatGPT" 应保留原名。核对后的英文文案作为最终版本。
- **时长控制**: ~10 分钟 ≈ 约 2500-3000 字中文 / ~1800-2200 词英文

#### ⑤ Audio Producer Agent（音频制作 Agent）
- **职责**: 解析文案，按说话人分段，对每段调用 Boson API 生成音频，拼接为完整播客。
- **不使用 GLM**: 此 Agent 的"智能"部分仅是文案解析与分段拼接的逻辑，不调用智谱 API。音频生成只调用 Boson API。
- **核心工具**:
  - `parse_script(script)` — 解析文案为 `[{speaker, voice, text_with_tags}, ...]`
  - `boson_tts(text, voice)` — 调用 Boson API 生成单段 MP3
  - `concat_audio(segments)` — 拼接音频段（pydub 或 ffmpeg）
- **工作流**:
  1. 解析文案，提取每段的说话人和带标签文本
  2. 对每段调用 `POST https://api.boson.ai/v1/audio/speech`，传入对应的 voice 和带标签的 input
  3. 将各段 MP3 拼接为完整播客音频
  4. 保存音频文件，记录路径
- **并发**: 中文版和英文版可并行生成

#### ⑥ Feedback Optimizer Agent（反馈优化 Agent）
- **职责**: 接收用户对播客文案/新闻的反馈，分析反馈类型，执行优化动作。
- **模型**: glm-5.1
- **核心工具**:
  - `analyze_feedback(feedback)` — 分类反馈（内容准确性/播客风格/时长/标签使用/知识库错误）
  - `update_agent_prompt(agent_name, new_prompt)` — 更新 Agent 的 prompt 版本
  - `trigger_kb_correction(item)` — 触发知识库修正
  - `log_optimization(action)` — 记录优化动作
- **优化闭环**: 反馈 → 分析 → 优化 prompt/参数 → 记录 → 下次生成时生效 → 评估效果

#### ⑦ Evaluation Agent（测评 Agent）
- **职责**: 数据驱动的 Agent 优化机制。周期性评估各 Agent 的输出质量，检测 badcase，生成优化建议，跟踪优化效果。
- **模型**: glm-5.1
- **核心工具**:
  - `evaluate_agent_output(agent_name, input, output)` — 用 GLM-5.2 对 Agent 输出打分（1-5 分 + 评语）
  - `detect_badcase(agent_log)` — 基于规则+AI 检测 badcase
  - `generate_optimization_suggestion(badcases)` — 汇总 badcase 生成优化建议
  - `track_metrics(agent_name)` — 跟踪成功率、平均耗时、质量分数趋势
- **测评维度**:
  - 新闻采集: 覆盖度、准确性、去重率、图片质量
  - 知识库: 页面一致性、交叉引用完整度、信息时效性
  - 文案: 内容连贯性、时长符合度、标签使用合理性、中英一致性
  - 音频: 生成成功率、音色匹配度、拼接流畅度
- **触发时机**: 每次播客生成完成后自动评估 + 用户可手动触发
- **数据驱动优化**: badcase 积累 → Evaluation Agent 分析 → 生成 prompt 优化建议 → Feedback Optimizer 应用 → A/B 对比 → 固化有效改进

### 3.4 Harness 框架核心能力
| 能力 | 实现 |
|------|------|
| **工具注册** | 统一的 ToolRegistry，每个 Agent 声明可用工具，框架注入 |
| **日志记录** | 每次 Agent 调用自动记录: agent_name, task_id, input, output, tools_used, duration, status, error |
| **错误重试** | 可配置重试次数和退避策略 |
| **超时控制** | 每个工具调用有超时限制 |
| **并发调度** | asyncio 实现子任务并行 |
| **状态追踪** | job/step 级状态机 (pending→running→success/failed) |
| **可观测** | 所有日志存 SQLite，通过 API 和客户端可查 |

---

## 四、Agent 监控与测评系统

### 4.1 监控数据模型
所有 Agent 调用通过 Harness 框架的中间层自动记录，无需 Agent 自身关心日志。

**agent_logs 表**:
| 字段 | 说明 |
|------|------|
| id | 主键 |
| agent_name | Agent 名称 |
| task_id | 所属任务 ID |
| step | 步骤描述 |
| input | 输入内容 (JSON) |
| output | 输出内容 (JSON) |
| tools_used | 使用的工具列表 |
| duration_ms | 耗时(毫秒) |
| status | success / failed / timeout |
| error | 错误信息 |
| quality_score | 测评分数 (1-5) |
| quality_comment | 测评评语 |
| created_at | 时间戳 |

**bad_cases 表**:
| 字段 | 说明 |
|------|------|
| id | 主键 |
| agent_log_id | 关联日志 |
| category | badcase 类别 |
| description | 问题描述 |
| severity | low / medium / high |
| suggestion | 优化建议 |
| resolved | 是否已处理 |
| created_at | 时间戳 |

**agent_configs 表** (prompt 版本管理):
| 字段 | 说明 |
|------|------|
| id | 主键 |
| agent_name | Agent 名称 |
| prompt_version | 版本号 |
| prompt_text | 完整 prompt |
| parameters | 模型参数 (temperature 等) |
| active | 是否当前生效 |
| created_at | 时间戳 |

**agent_metrics 表** (趋势追踪):
| 字段 | 说明 |
|------|------|
| id | 主键 |
| agent_name | Agent 名称 |
| metric_name | 指标名 (success_rate / avg_duration / avg_score) |
| metric_value | 指标值 |
| date | 日期 |
| created_at | 时间戳 |

### 4.2 监控 API
```
GET  /api/monitor/overview          # 总览（各Agent成功率/耗时/分数）
GET  /api/monitor/agents            # Agent 列表
GET  /api/monitor/logs              # 日志列表（支持按agent/status/日期筛选）
GET  /api/monitor/logs/{id}         # 日志详情（完整输入输出）
GET  /api/monitor/badcases          # Badcase 列表
POST /api/monitor/badcases/{id}/resolve  # 标记已处理
GET  /api/monitor/metrics           # 指标趋势
GET  /api/monitor/evaluations       # 测评结果
POST /api/monitor/evaluate          # 手动触发测评
GET  /api/monitor/configs           # Agent prompt 配置
PUT  /api/monitor/configs/{id}      # 更新 prompt 配置
```

### 4.3 客户端监控页面
安卓客户端设置中提供"Agent 监控"入口，可查看:
- 各 Agent 调用统计（成功率、平均耗时、质量分数趋势图）
- 最近日志列表（点击查看完整输入输出）
- Badcase 列表（含优化建议）
- Agent prompt 版本管理

---

## 五、知识库设计（LLM Wiki 理念）

### 5.1 设计理念
严格遵循 Karpathy LLM Wiki 的三层架构：
- **Raw Sources（原始素材）**: 不可变，新闻原文+图片，Agent 只读
- **The Wiki（知识库）**: LLM 生成并维护的 markdown 文件集合，交叉引用、持续积累
- **The Schema（规范）**: 指导 Agent 如何维护 Wiki 的配置文档

核心原则：**知识编译一次后持续更新，而非每次查询重新推导**。用户负责提问和方向，Agent 负责所有维护工作（摘要、交叉引用、索引、日志）。

### 5.2 目录结构
```
data/knowledge_base/
├── SCHEMA.md                    # 规范文档（Wiki 结构约定、工作流程）
├── index.md                     # 内容目录（所有页面索引+摘要）
├── log.md                       # 时间线日志（append-only）
├── domains/                     # 按领域组织
│   ├── ai/                      # AI 领域
│   │   ├── overview.md          # 领域概览页
│   │   ├── entities/            # 实体页（公司、产品、人物、技术）
│   │   │   ├── openai.md
│   │   │   ├── gemini.md
│   │   │   └── ...
│   │   ├── concepts/            # 概念页（技术概念解释）
│   │   │   ├── large-language-model.md
│   │   │   └── ...
│   │   └── sources/             # 新闻摘要页（每条新闻一页）
│   │       ├── 2026-06-20-gpt6-release.md
│   │       └── ...
│   ├── internet/
│   ├── smart-manufacturing/
│   ├── embodied-intelligence/
│   ├── web3/
│   └── international-politics/
├── cross-domain/                # 跨领域综合页
│   ├── weekly-synthesis.md      # 周度综合分析
│   └── comparisons.md           # 跨领域对比
└── assets/                      # 图片资源
    ├── ai/
    ├── internet/
    └── ...
```

### 5.3 页面格式规范
每个 Wiki 页面包含 YAML frontmatter + markdown 正文：
```markdown
---
title: GPT-6 正式发布
domain: ai
category: source
date: 2026-06-20
source_url: https://...
tags: [openai, 大模型, 发布]
related: [openai.md, large-language-model.md]
---

# GPT-6 正式发布

## 摘要
（Agent 生成的中文摘要）

## 关键信息
- ...

## 关联
- 相关实体：[[openai]]
- 相关概念：[[large-language-model]]

## 原始来源
- [原文链接](url)
```

### 5.4 三大操作
| 操作 | 说明 |
|------|------|
| **Ingest（摄入）** | 新新闻入库时，Agent 读取原文→写摘要页→更新实体/概念页→更新 index.md→追加 log.md。单条新闻可能触及 5-10 个页面。 |
| **Query（查询）** | 用户搜索时，Agent 先读 index.md 定位相关页→读取页面→综合回答（带引用）。有价值的查询结果可归档为新页面。 |
| **Lint（检查）** | 定期健康检查：矛盾检测、过期信息、孤立页面、缺失交叉引用、数据缺口。 |

### 5.5 索引与日志
- **index.md**: 按领域分类的页面目录，每页含链接+一行摘要+元数据。每次 Ingest 自动更新。
- **log.md**: append-only 时间线，格式 `## [2026-06-20] ingest | GPT-6 正式发布`，可被简单 grep 解析。

### 5.6 更新与保留机制
- 新闻素材每日更新
- Wiki 页面持续增量更新（新信息覆盖/补充旧信息，矛盾处标注）
- 超过 6 个月的原始新闻素材归档压缩，Wiki 摘要页保留
- 定期 Lint 保持知识库健康

### 5.7 搜索实现
- 基础: 全文搜索 index.md + 页面内容（SQLite FTS5）
- 增强: Agent 辅助搜索（GLM-5.2 理解查询意图 → 定位页面 → 综合回答）

---

## 六、播客生成流水线

### 6.1 触发方式
用户在客户端点击"获取今日播客" → 后端创建生成任务 → 异步执行 → 客户端轮询进度。

### 6.2 生成流程
```
用户点击"获取播客"
    │
    ▼
Orchestrator 创建 job (status=running)
    │
    ├─[并行] ② News Collector × 6 领域 ──→ 30 条新闻+图片
    │         progress: 10% → 30%
    │
    ├─[串行] ③ Knowledge Base.ingest(30条新闻)
    │         progress: 30% → 50%
    │
    ├─[串行] ④ Script Writer.generate(新闻, KB上下文)
    │         ├─ 生成中文文案 (含TTS标签)
    │         └─ 翻译为英文文案 (内容一致)
    │         progress: 50% → 65%
    │
    ├─[并行] ⑤ Audio Producer × 2 (中文+英文)
    │         ├─ 解析文案 → 分段
    │         ├─ 逐段调用 Boson API (marcus/chloe)
    │         └─ 拼接音频
    │         progress: 65% → 90%
    │
    ├─[串行] ⑦ Evaluation.evaluate(全流程)
    │         progress: 90% → 100%
    │
    ▼
job 完成 (status=success)
```

### 6.3 进度追踪
- `generation_jobs` 表记录 job 状态和进度百分比
- 每个阶段更新 progress 和 detail（如"正在采集 AI 领域新闻..."）
- 客户端可退出，重新进入时通过 `GET /api/podcast/jobs` 恢复进度显示

### 6.4 播客文案与音频存储
```
data/podcasts/
├── 2026-06-20/
│   ├── script_zh.md          # 中文文案
│   ├── script_en.md          # 英文文案
│   ├── audio_zh.mp3          # 中文音频
│   ├── audio_en.mp3          # 英文音频
│   └── meta.json             # 元数据（时长、分段信息）
```

### 6.5 保留策略
- 最多保留 180 天（约半年）的播客文件
- 超期文件由定时任务自动清理
- 数据库记录保留（可查历史记录），仅清理音频/文案文件

### 6.6 反馈与优化
- 用户在播放页可对文案/内容提交文字反馈
- 反馈进入 ⑥ Feedback Optimizer Agent
- Agent 分析后调整对应 Agent 的 prompt/参数
- 调整记录可追溯，效果通过 ⑦ Evaluation Agent 跟踪

---

## 七、后端 API 设计

### 7.1 基础
- Base URL: `http://{server_ip}:8000`
- 所有响应: JSON
- 音频文件: 通过 API 流式返回（避免暴露文件路径）

### 7.2 接口列表

#### 健康检查 & 配置
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 连接测试（客户端首次配置用），返回 `{status: "ok", version: "..."}` |

#### 播客
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/podcast/generate` | 触发今日播客生成，返回 `{job_id}` |
| GET | `/api/podcast/jobs` | 获取生成任务列表（含进度） |
| GET | `/api/podcast/jobs/{job_id}` | 获取单个任务状态 |
| GET | `/api/podcasts` | 获取播客列表（分页，按日期倒序） |
| GET | `/api/podcasts/{id}` | 获取播客详情（文案+音频URL+元数据） |
| GET | `/api/podcasts/{id}/audio?lang=zh` | 流式返回音频文件 |
| GET | `/api/podcasts/{id}/script?lang=zh` | 获取文案内容 |
| POST | `/api/podcasts/{id}/feedback` | 提交反馈 `{type, content}` |

#### 知识库
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/kb/search?q={query}` | 搜索知识库 |
| GET | `/api/kb/domains` | 获取领域列表 |
| GET | `/api/kb/pages?domain={domain}` | 获取页面列表 |
| GET | `/api/kb/pages/{path}` | 获取页面内容（markdown转HTML+图片URL） |
| GET | `/api/kb/images/{filename}` | 获取图片 |
| POST | `/api/kb/update` | 触发知识库更新任务 |

#### 监控
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/monitor/overview` | 监控总览 |
| GET | `/api/monitor/logs` | Agent 日志列表 |
| GET | `/api/monitor/logs/{id}` | 日志详情 |
| GET | `/api/monitor/badcases` | Badcase 列表 |
| POST | `/api/monitor/badcases/{id}/resolve` | 标记已处理 |
| GET | `/api/monitor/metrics` | 指标趋势 |
| GET | `/api/monitor/configs` | Agent 配置 |
| PUT | `/api/monitor/configs/{id}` | 更新配置 |
| POST | `/api/monitor/evaluate` | 手动触发测评 |

---

## 八、数据库 Schema（SQLite）

```sql
-- 播客
CREATE TABLE podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- 2026-06-20
    script_zh_path TEXT,
    script_en_path TEXT,
    audio_zh_path TEXT,
    audio_en_path TEXT,
    duration_zh INTEGER,             -- 秒
    duration_en INTEGER,
    status TEXT DEFAULT 'pending',   -- pending/generating/ready/failed
    created_at TEXT DEFAULT (datetime('now'))
);

-- 新闻素材
CREATE TABLE news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_date TEXT NOT NULL,      -- 关联播客日期
    domain TEXT NOT NULL,            -- ai/internet/...
    title_zh TEXT NOT NULL,
    title_en TEXT,
    summary_zh TEXT NOT NULL,
    source_url TEXT,
    image_path TEXT,
    wiki_page_path TEXT,             -- 对应Wiki页面路径
    collected_at TEXT DEFAULT (datetime('now'))
);

-- 生成任务
CREATE TABLE generation_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,              -- podcast/kb_update
    status TEXT DEFAULT 'pending',   -- pending/running/success/failed
    progress INTEGER DEFAULT 0,      -- 0-100
    detail TEXT,                     -- 当前步骤描述
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Agent 日志
CREATE TABLE agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    task_id TEXT,                    -- 关联 generation_jobs.id
    step TEXT,
    input TEXT,                      -- JSON
    output TEXT,                     -- JSON
    tools_used TEXT,                 -- JSON array
    duration_ms INTEGER,
    status TEXT,                     -- success/failed/timeout
    error TEXT,
    quality_score INTEGER,           -- 1-5
    quality_comment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Badcase
CREATE TABLE bad_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_log_id INTEGER REFERENCES agent_logs(id),
    category TEXT,
    description TEXT,
    severity TEXT,                   -- low/medium/high
    suggestion TEXT,
    resolved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 反馈
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_id INTEGER REFERENCES podcasts(id),
    type TEXT,                       -- content/style/duration/tag/kb_error
    content TEXT,
    status TEXT DEFAULT 'pending',   -- pending/processed
    created_at TEXT DEFAULT (datetime('now'))
);

-- Agent 配置（prompt 版本管理）
CREATE TABLE agent_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    parameters TEXT,                 -- JSON
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Agent 指标
CREATE TABLE agent_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    metric_name TEXT NOT NULL,       -- success_rate/avg_duration/avg_score
    metric_value REAL,
    date TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 知识库页面索引（便于搜索）
CREATE TABLE knowledge_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    domain TEXT,
    category TEXT,                   -- overview/entity/concept/source/cross-domain
    summary TEXT,
    tags TEXT,                       -- JSON array
    content TEXT,                    -- 全文（用于FTS）
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 全文搜索虚拟表
CREATE VIRTUAL TABLE knowledge_pages_fts USING fts5(
    title, summary, content, content='knowledge_pages'
);
```

---

## 九、安卓客户端设计

### 9.1 页面结构
```
App 启动
  │
  ├─ 首次使用（无后端地址）→ SetupScreen（输入地址+测试连接）
  │
  └─ 已配置 → MainScreen
       │
       ├─ BottomNav: 播客 | 知识库 | 设置
       │
       ├─ [播客 Tab]
       │    ├─ PodcastListScreen: 日期列表 + 语言切换(ZH/EN) + "获取今日播客"按钮
       │    ├─ GenerationProgressScreen: 生成进度（可退出，重进恢复）
       │    └─ PodcastPlayerScreen: 音频播放器 + 文案显示 + 反馈入口
       │
       ├─ [知识库 Tab]
       │    ├─ KnowledgeSearchScreen: 搜索栏 + 领域分类
       │    ├─ KnowledgePageListScreen: 某领域下的页面列表
       │    └─ KnowledgePageDetailScreen: Markdown 渲染 + 图片显示
       │
       └─ [设置 Tab]
            ├─ 后端地址配置（修改+测试连接）
            ├─ Agent 监控（日志/Badcase/指标）
            └─ 关于
```

### 9.2 关键交互
- **首次配置**: 打开 App → SetupScreen → 输入 `IP:端口` → 点击"测试连接" → 调用 `GET /api/health` → 成功则保存到 DataStore，进入主界面；失败则提示重试
- **获取播客**: 点击"获取今日播客" → `POST /api/podcast/generate` → 跳转进度页 → 每 3 秒轮询 `GET /api/podcast/jobs/{id}` → 完成后可播放
- **进度恢复**: 重新进入 App 时检查 `GET /api/podcast/jobs` 是否有 running 状态任务 → 有则显示进度
- **音频播放**: Media3 ExoPlayer 播放 `GET /api/podcasts/{id}/audio?lang=zh` 流式音频，支持后台播放
- **文案查看**: 播放页可展开文案，Markwon 渲染（含 TTS 标签的可读化显示）
- **反馈提交**: 播放页反馈按钮 → 输入文字 → `POST /api/podcasts/{id}/feedback`
- **知识库搜索**: 输入关键词 → `GET /api/kb/search?q=...` → 结果列表 → 点击进入详情页

### 9.3 数据持久化
- DataStore: `backend_url`（后端地址）、`language_preference`（播客语言偏好）
- Room: 播客列表缓存（离线查看标题/状态）

---

## 十、一键部署设计

### 10.1 部署脚本 `deploy.sh`
在本地（macOS）执行，完成全流程部署：

```bash
# 执行流程:
# 1. 检查本地代码完整性
# 2. rsync 代码到服务器 /opt/listenandlearn/
# 3. SSH 远程执行:
#    a. 安装 Python 3.11 + 系统依赖 (ffmpeg等)
#    b. 创建虚拟环境 venv
#    c. pip install -r requirements.txt
#    d. 写入 .env (API keys + 配置)
#    e. 初始化数据库
#    f. 创建 systemd service
#    g. 启动服务 + 设置开机自启
#    h. 健康检查
# 4. 输出部署结果
```

### 10.2 环境变量（.env）
```env
# Boson.ai
BOSON_API_KEY=bai-vdbnLy_MuhqFPQ3SOjvtUjw2i55ceL6c4dd9OCGUuUIWVgFZ
BOSON_API_URL=https://api.boson.ai/v1/audio/speech

# 智谱AI
ZAI_API_KEY=82e775bb5a104459826a64822b03483e.UoHJo9vVhYsdWtQ7
ZAI_MODEL=glm-5.1

# 服务配置
HOST=0.0.0.0
PORT=8000
DATA_DIR=/opt/listenandlearn/data
```

### 10.3 systemd service
```ini
[Unit]
Description=Listen and Learn Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/listenandlearn
EnvironmentFile=/opt/listenandlearn/.env
ExecStart=/opt/listenandlearn/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 10.4 目录结构（服务器）
```
/opt/listenandlearn/
├── app/                    # 后端代码
├── data/                   # 数据目录
│   ├── listenandlearn.db   # SQLite
│   ├── knowledge_base/     # LLM Wiki
│   ├── podcasts/           # 播客文件
│   └── news/               # 新闻素材原始文件
├── venv/                   # 虚拟环境
├── .env                    # 环境变量
├── requirements.txt
└── deploy.sh
```

---

## 十一、项目文件结构

```
listenandlearn/
├── DESIGN.md                      # 本设计文档
├── README.md                      # 项目说明
├── deploy.sh                      # 一键部署脚本
│
├── backend/                       # 后端代码
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI 入口
│   │   ├── config.py              # 配置加载（环境变量）
│   │   ├── database.py            # SQLite 初始化
│   │   │
│   │   ├── harness/               # Harness Agent 框架
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py      # Agent 基类
│   │   │   ├── tool_registry.py   # 工具注册中心
│   │   │   ├── orchestrator.py    # 编排器
│   │   │   ├── logger.py          # Agent 日志记录
│   │   │   └── evaluator.py       # 测评引擎
│   │   │
│   │   ├── agents/                # 各 Agent 实现
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator_agent.py
│   │   │   ├── news_collector_agent.py
│   │   │   ├── knowledge_base_agent.py
│   │   │   ├── script_writer_agent.py
│   │   │   ├── audio_producer_agent.py
│   │   │   ├── feedback_optimizer_agent.py
│   │   │   └── evaluation_agent.py
│   │   │
│   │   ├── tools/                 # Agent 工具
│   │   │   ├── __init__.py
│   │   │   ├── zhipu_client.py    # 智谱AI封装
│   │   │   ├── boson_client.py    # Boson TTS封装
│   │   │   ├── web_fetcher.py     # 网页抓取
│   │   │   ├── image_downloader.py
│   │   │   ├── wiki_manager.py    # Wiki 文件管理
│   │   │   └── audio_utils.py     # 音频拼接
│   │   │
│   │   ├── api/                   # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── podcast.py
│   │   │   ├── knowledge_base.py
│   │   │   └── monitor.py
│   │   │
│   │   ├── models/                # 数据模型
│   │   │   ├── __init__.py
│   │   │   └── schemas.py         # Pydantic models
│   │   │
│   │   └── services/              # 业务服务
│   │       ├── __init__.py
│   │       ├── podcast_service.py
│   │       ├── knowledge_service.py
│   │       └── cleanup_service.py # 过期文件清理
│   │
│   └── tests/                     # 测试
│
├── android/                       # 安卓客户端
│   ├── app/
│   │   ├── build.gradle.kts
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── java/com/listenandlearn/
│   │       │   ├── MainActivity.kt
│   │       │   ├── ui/
│   │       │   │   ├── setup/      # 首次配置
│   │       │   │   ├── podcast/    # 播客相关
│   │       │   │   ├── knowledge/  # 知识库
│   │       │   │   ├── settings/   # 设置+监控
│   │       │   │   └── theme/      # 主题
│   │       │   ├── data/           # Repository + API
│   │       │   └── player/         # 音频播放服务
│   │       └── res/                # 资源
│   ├── build.gradle.kts
│   └── settings.gradle.kts
│
└── data/                          # 运行时数据（部署后生成）
    ├── listenandlearn.db
    ├── knowledge_base/
    ├── podcasts/
    └── news/
```

---

## 十二、关键设计决策说明

### 12.1 为什么 Audio Producer Agent 不调用智谱 API
按需求严格区分：智谱 AI 仅用于文本生成类任务。音频制作 Agent 的工作是"解析文案 + 调用 Boson API + 拼接音频"，其中的文案解析和拼接是确定性逻辑（正则解析 + ffmpeg），不需要 AI 参与。TTS 标签已由 Script Writer Agent 在文案中嵌入。

### 12.2 播客文案中的 TTS 标签设计
文案 Agent（GLM-5.2）在生成对谈稿时，直接在文本中嵌入 `<|emotion:xxx|>`、`<|prosody:pause|>`、`<|sfx:laughter|>` 等标签。Audio Producer Agent 按说话人分段后，将带标签的文本直接传给 Boson API 的 `input` 字段，Boson 模型会识别这些标签并生成对应情感/韵律/音效的语音。

### 12.3 中英文播客内容一致性
先生成中文文案 → 再用 GLM-5.2 翻译为英文（保持内容结构、说话人轮次、TTS 标签位置一致）。确保两份播客内容完全相同。

### 12.4 知识库纯中文
新闻采集时，英文新闻由 GLM-5.2 翻译为中文摘要后存入知识库。Wiki 所有页面（实体页、概念页、摘要页）均为中文。图片直接从新闻源下载存储。

### 12.5 单用户无账户系统
后端不需要鉴权中间件，所有 API 直接可用。客户端首次配置后端地址即可使用，无登录注册流程。

### 12.6 Agent 测评机制（数据驱动优化）
```
Agent 执行 → Harness 自动记录日志
    → Evaluation Agent 对输出打分
    → 低分输出标记为 badcase
    → badcase 积累到阈值
    → Evaluation Agent 分析根因 + 生成优化建议
    → Feedback Optimizer 更新 prompt 版本
    → 新 prompt 生效 → 跟踪后续指标
    → 指标提升则固化，下降则回滚
```
所有过程可观测、可追溯，在客户端监控页面查看。

---

## 十三、确认清单

请逐项确认以下内容，确认无误后我将开始编码：

- [ ] **1. Agent 架构**: 7 个 Agent（编排/采集/知识库/文案/音频/反馈/测评）的职责划分是否符合预期
- [ ] **2. 知识库**: LLM Wiki 三层架构 + 6 领域目录结构 + 纯中文
- [ ] **3. 播客文案**: 双主持(marcus+chloe) + TTS标签内嵌格式 + 中英双版本
- [ ] **4. 生成流程**: 用户点击触发 → 异步后台 → 进度可追踪 → 可退出恢复
- [ ] **5. API 设计**: 健康检查/播客/知识库/监控 四组接口
- [ ] **6. 数据库**: 8 张表覆盖播客/新闻/任务/日志/badcase/反馈/配置/指标
- [ ] **7. 安卓客户端**: 首次配置 → 播客/知识库/设置三Tab + Agent监控
- [ ] **8. 部署**: deploy.sh 一键 rsync+SSH 部署到 49.232.226.131
- [ ] **9. AI 严格分区**: 智谱(glm-5.1)仅文本 / Boson 仅音频
- [ ] **10. 保留策略**: 播客文件最多 180 天 + 知识库持续更新

如有调整意见，请直接说明，我将修改设计后再进入编码。
