# Listen and Learn

> AI 播客 + 知识库全栈应用 | 8 Agent 协作 | Harness 多 Agent 框架
>
> 后端 4936 行 Python | 客户端 1972 行 Kotlin | 已部署运行

每天自动采集 AI 领域新闻，通过 8 个 Agent 协作生成中英双语播客，同时维护一个基于 LLM Wiki 理念的持续积累知识库。核心设计了 Harness Agent 框架，统一编排调度、工具注入、日志监控、自动测评、反馈驱动的持续优化闭环。

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM | 智谱 GLM-5.2（文本生成 / Agent 编排） |
| TTS | 阿里云 CosyVoice（cosyvoice-v3-plus，longanyang/longanhuan） |
| 后端 | Python + FastAPI + SQLite + FTS5 |
| 客户端 | Android Kotlin + Jetpack Compose + Retrofit + ExoPlayer |
| 部署 | CentOS + systemd + 一键部署脚本 |

## 架构总览

```
用户点击"获取播客"
        ↓
OrchestratorAgent (Plan-and-Execute 6步流水线)
    ├─ Step1: NewsCollectorAgent      采集 aibase.com 最新AI新闻
    ├─ Step2: KnowledgeBaseAgent      摄入知识库 (LLM Wiki)
    ├─ Step3: ScriptWriterAgent       生成中英双语文案 (SSML标签)
    ├─ Step4: AudioProducerAgent×2    中英音频并行生成 (CosyVoice TTS)
    ├─ Step5: 保存播客记录
    └─ Step6: EvaluationAgent         质量测评+badcase检测
        ↓
知识库智能搜索 (KBSearchAgent) ← 用户自然语言提问
反馈优化 (FeedbackOptimizerAgent) ← 用户反馈驱动prompt迭代
```

## 模块设计与代码位置

### 1. Harness Agent 框架

统一的 Agent 基础设施，负责编排调度、工具注入、日志监控、错误恢复。

| 模块 | 文件:行号 | 说明 |
|------|-----------|------|
| BaseAgent 基类 | `backend/app/harness/base_agent.py:14-134` | 抽象基类，提供 prompt 版本管理(L23-35)、执行+日志+重试(L84-128) |
| ToolRegistry 工具注册中心 | `backend/app/harness/tool_registry.py:1-71` | 统一注册/获取/批量获取，`Tool.call()` 内置超时控制 |
| AgentLogger 日志记录 | `backend/app/harness/logger.py:1-162` | 每次调用记录输入/输出/工具/耗时/状态，badcase 记录(L51-66) |
| Evaluator 测评引擎 | `backend/app/harness/evaluator.py:1-142` | 8个Agent评估标准(L12-21)，GLM打分+badcase检测(L26-82) |
| Prompt 管理 | `backend/app/harness/prompts.py` | 8个Agent的默认system prompt |

### 2. 八大 Agent

| Agent | 职责 | 文件:行号 |
|-------|------|-----------|
| **OrchestratorAgent** | 中央编排，6步流水线，中英音频并行 | `backend/app/agents/orchestrator_agent.py:25-154` |
| **NewsCollectorAgent** | 爬取 aibase.com，按"X天前"识别最新日，GLM总结选优 | `backend/app/agents/news_collector_agent.py:28-353` |
| **KnowledgeBaseAgent** | LLM Wiki 理念，摄入新闻→实体页/摘要页/概览页 | `backend/app/agents/knowledge_base_agent.py:30-270` |
| **ScriptWriterAgent** | 中文生成→英文翻译→专有名词核对，SSML标签嵌入 | `backend/app/agents/script_writer_agent.py:28-307` |
| **AudioProducerAgent** | 解析文案分段→超长切分→TTS合成→音频拼接 | `backend/app/agents/audio_producer_agent.py:33-241` |
| **KBSearchAgent** | 自然语言搜索：GLM生成关键词→FTS5搜索→读取→综合回答 | `backend/app/agents/kb_search_agent.py:26-158` |
| **FeedbackOptimizerAgent** | 分析反馈根因→生成优化建议→应用prompt迭代 | `backend/app/agents/feedback_optimizer_agent.py:24-176` |
| **EvaluationAgent** | 汇总各Agent日志→GLM逐条打分→生成整体优化建议 | `backend/app/agents/evaluation_agent.py:26-111` |

### 3. 工具层

| 工具 | 文件:行号 | 说明 |
|------|-----------|------|
| ZhipuClient (GLM-5.2) | `backend/app/tools/zhipu_client.py:17-90` | 文本生成唯一入口，think模式隔离reasoning_content(L73-84) |
| CosyVoiceTTSClient | `backend/app/tools/boson_client.py:51-158` | 音频生成唯一入口，3次重试+兜底清洗(L26-48) |
| WikiManager | `backend/app/tools/wiki_manager.py:15-145` | LLM Wiki 文件管理+FTS5全文搜索(带输入转义L107-123) |
| AudioUtils | `backend/app/tools/audio_utils.py` | MP3拼接/时长获取/临时文件清理 |

### 4. API 层

| API | 文件:行号 | 说明 |
|-----|-----------|------|
| `POST /api/podcast/generate` | `backend/app/api/podcast.py:17-90` | 触发播客生成，异步流水线 |
| `GET /api/podcast/jobs/{id}` | `backend/app/api/podcast.py:104-113` | 轮询任务进度 |
| `GET /api/podcast/{id}/download` | `backend/app/api/podcast.py:200-227` | 音频下载 |
| `GET /api/podcast/logs/stream` | `backend/app/api/podcast.py:258-289` | SSE 实时日志流 |
| `GET /api/kb/smart-search` | `backend/app/api/knowledge_base.py:127-141` | 智能搜索 |
| `POST /api/kb/feedback` | `backend/app/api/knowledge_base.py:230-244` | 知识库反馈 |
| `GET /api/monitor/evaluations` | `backend/app/api/monitor.py:43-73` | 评测详情 |
| `GET /api/monitor/evaluations/summary` | `backend/app/api/monitor.py:76-118` | 各Agent评测汇总 |
| `GET /api/monitor/badcases` | `backend/app/api/monitor.py:121-139` | Badcase列表 |
| `PUT /api/monitor/configs/{id}` | `backend/app/api/monitor.py:191-229` | prompt版本更新 |

### 5. 数据库

| 表 | 文件:行号 | 说明 |
|----|-----------|------|
| podcasts | `backend/app/database.py:10-21` | 播客记录 |
| news_items | `backend/app/database.py:23-34` | 新闻条目 |
| generation_jobs | `backend/app/database.py:36-45` | 生成任务（进度追踪） |
| agent_logs | `backend/app/database.py:47-61` | Agent调用日志（含质量评分） |
| bad_cases | `backend/app/database.py:63-72` | Badcase记录 |
| feedback | `backend/app/database.py:74-81` | 用户反馈 |
| agent_configs | `backend/app/database.py:83-91` | prompt版本管理 |
| knowledge_pages + FTS5 | `backend/app/database.py:102-116` | 知识库页面+全文搜索虚拟表 |

### 6. 客户端 (Android)

| 页面 | 说明 |
|------|------|
| PodcastScreen | 播客列表+生成触发+进度恢复 |
| PodcastDetailScreen | 文案展示+音频播放+下载 |
| KnowledgeScreen | 知识库浏览+关键词/智能搜索+反馈 |
| SettingsScreen | 监控Tab（统计/评测/badcase） |
| LogStreamScreen | SSE实时日志查看 |

## 项目亮点

### 1. Plan-and-Execute 多 Agent 并行编排

Orchestrator 将"生成播客"拆解为6步，中英音频生成通过 `asyncio.gather` 并行执行。
- 代码：`backend/app/agents/orchestrator_agent.py:113-121`

### 2. 数据驱动的持续优化闭环

```
执行→日志记录→GLM打分→badcase检测→反馈分析→prompt迭代→再验证
```
- 评测引擎：`backend/app/harness/evaluator.py:26-82`
- 反馈优化：`backend/app/agents/feedback_optimizer_agent.py:24-65`
- prompt版本管理：`backend/app/harness/base_agent.py:23-35`

### 3. LLM Wiki 理念知识库

非传统 RAG，Agent 增量构建持久化 Wiki，知识编译一次后持续更新。FTS5 全文搜索带输入转义防注入。
- 知识库Agent：`backend/app/agents/knowledge_base_agent.py:67-103`
- Wiki管理：`backend/app/tools/wiki_manager.py:15-145`
- FTS5转义：`backend/app/tools/wiki_manager.py:107-123`

### 4. GLM-5.2 think 模式四层防御

| 层级 | 文件:行号 | 机制 |
|------|-----------|------|
| API层 | `backend/app/tools/zhipu_client.py:73-84` | 严格隔离 reasoning_content，绝不当作正文返回 |
| Prompt层 | `backend/app/agents/script_writer_agent.py:145-152` | 限制SSML标签种类+要求单版本输出 |
| 清洗层 | `backend/app/agents/script_writer_agent.py:225-296` | 多版本检测清空+非标准标签移除 |
| TTS兜底 | `backend/app/tools/boson_client.py:26-48` | 白名单过滤，移除所有非标准标签 |

### 5. SSML 标签嵌入文案

文案Agent生成对谈稿时直接嵌入 `<speak>`/`<break>` 标签控制韵律停顿，音频Agent解析后传给TTS，实现"文案即指令"。
- 生成：`backend/app/agents/script_writer_agent.py:126-152`
- 解析：`backend/app/agents/audio_producer_agent.py:136-210`
- 动态启用：`backend/app/tools/boson_client.py:102-103`

### 6. AI 供应商严格分区

CosyVoice 只做音频生成，GLM-5.2 做其余所有文本任务。AudioProducerAgent 不调用任何LLM。
- 配置：`backend/app/config.py:9-18`

### 7. SSE 实时日志流

客户端实时查看后端生成进度，按 ERROR/WARN/SUCCESS 着色。
- 后端：`backend/app/api/podcast.py:258-289`

### 8. SQL 安全治理

全面排查修复 ambiguous column、外键约束、FTS5注入等问题。
- FTS5转义：`backend/app/tools/wiki_manager.py:107-123`
- JOIN表前缀：`backend/app/tools/wiki_manager.py:130-143`
- 外键NULL处理：`backend/app/api/knowledge_base.py:233-237`

## 快速开始

### 后端部署

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ZAI_API_KEY 和 DASHSCOPE_API_KEY

# 3. 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 服务器一键部署

```bash
bash deploy.sh    # 首次部署
bash update.sh    # 更新代码
```

### 客户端

用 Android Studio 打开 `android/` 目录，配置后端地址后编译安装。

## 项目结构

```
listenandlearn/
├── backend/
│   ├── app/
│   │   ├── agents/          # 8个Agent
│   │   ├── harness/         # Agent框架（基类/工具注册/日志/测评/prompt）
│   │   ├── tools/           # 工具层（GLM客户端/TTS客户端/Wiki管理）
│   │   ├── api/             # FastAPI路由
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 业务服务
│   │   ├── config.py        # 配置
│   │   ├── database.py      # 数据库初始化
│   │   └── main.py          # 入口
│   └── requirements.txt
├── android/                 # Android客户端
├── deploy.sh                # 一键部署脚本
├── update.sh                # 更新脚本
├── DESIGN.md                # 设计文档
├── GUIDE.md                 # 使用指南
└── INTERVIEW.md             # 面试资料
```
