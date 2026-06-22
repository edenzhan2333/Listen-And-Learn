# Listen and Learn 项目面试资料

> 对标岗位：IMA AI Agent 策略产品经理
> 项目定位：AI 播客 + 知识库全栈应用，基于 Harness 多 Agent 架构
> 技术栈：Python + FastAPI + 8 Agent + 智谱 GLM-5.2 + 阿里云 CosyVoice + Android Kotlin
> 代码量：后端 4936 行 Python，客户端 1972 行 Kotlin，已部署运行

---

## 一、项目概述（30秒电梯陈述）

我独立完成了一个 AI 播客全栈项目。系统通过 **8 个 Agent 协作**，每天自动从新闻网站采集 AI 领域资讯，整理进基于 LLM Wiki 理念的知识库，生成中英双语播客文案和音频。核心亮点是设计了 **Harness Agent 框架**——统一编排、工具注册、日志监控、自动测评、反馈驱动的持续优化闭环。后端 4936 行 Python，客户端 1972 行 Kotlin，已部署运行。

**一句话体现 Agent 理解**：不是简单调 API，而是设计了完整的 Agent 生命周期管理——从任务拆解、多 Agent 并行编排、工具调用策略，到质量评测、badcase 检测、反馈驱动的 prompt 迭代。

---

## 二、逐条对应岗位职责

### 职责1：Agent 架构设计、工具调用策略、多 Agent 协作机制

#### 亮点1：Harness Agent 框架 —— 统一的 Agent 基础设施

**设计理念**：一个 Agent 框架（harness）负责编排调度、工具注入、日志监控、错误恢复，多个专职 Agent 在框架内协作。不是松散的 API 调用，而是有统一的基类和注册中心。

**代码证据**：

- `backend/app/harness/base_agent.py:14-134` — `BaseAgent` 抽象基类，提供：
  - `get_prompt()` (L23-35)：从数据库动态加载当前生效的 prompt 版本，支持 prompt 版本管理和热更新
  - `execute_with_logging()` (L84-128)：统一的执行+日志+重试机制，指数退避策略 `time.sleep(2 ** attempt)` (L110)
  - `@abstractmethod run()` (L130-133)：强制子类实现执行逻辑

- `backend/app/harness/tool_registry.py:1-71` — `ToolRegistry` 工具注册中心：
  - 统一注册 `register()`、获取 `get()`、批量获取 `get_many()`
  - `Tool.call()` 方法内置超时控制 `asyncio.wait_for`，避免单个工具卡死整个 Agent
  - 所有 Agent 共享同一个 `registry` 全局实例

#### 亮点2：多 Agent 协作 —— Plan-and-Execute 范式

**设计理念**：Orchestrator Agent 作为中央编排器，将"生成播客"这个复杂任务拆解为 6 个有序步骤，分配给专职 Agent 执行，支持串行依赖和并行执行。

**代码证据**：

`backend/app/agents/orchestrator_agent.py:25-154` — `run_podcast_pipeline()` 方法：

```
Step 1: 新闻采集 (并行)     → NewsCollectorAgent     L43-61
Step 2: 知识库更新 (串行)    → KnowledgeBaseAgent      L70-83  依赖 Step1 的新闻
Step 3: 文案生成 (串行)      → ScriptWriterAgent       L85-106 依赖 Step1+2
Step 4: 音频生成 (中英并行)  → AudioProducerAgent      L108-130 依赖 Step3
Step 5: 保存记录             → 内部方法                L132-137
Step 6: 质量测评             → EvaluationAgent         L139-148
```

**多 Agent 并行的关键代码**（L113-121）：
```python
audio_zh_task = asyncio.create_task(
    audio_agent.run(script=scripts["script_zh"], lang="zh", date_str=date_str)
)
audio_en_task = asyncio.create_task(
    audio_agent.run(script=scripts["script_en"], lang="en", date_str=date_str)
)
audio_zh_result, audio_en_result = await asyncio.gather(
    audio_zh_task, audio_en_task, return_exceptions=True
)
```

**任务依赖与错误处理**：
- L64-68：新闻采集为空时直接终止流程，不继续后续步骤
- L93-94：文案生成后校验内容非空，避免空文案传入音频生成
- 每步都有 try-catch，失败不影响已完成的步骤，结果记录到 `results["steps"]`

#### 亮点3：工具调用策略 —— 分层工具体系

**设计理念**：每个 Agent 有专属工具集，工具调用策略由 Agent 自身的 prompt 和逻辑决定，不是硬编码的 if-else。

**8 个 Agent 的工具分工**：

| Agent | 工具 | 代码位置 |
|-------|------|----------|
| NewsCollectorAgent | `_fetch_news_links` / `_fetch_article_detail` / `_summarize_and_select` | `news_collector_agent.py:91-353` |
| KnowledgeBaseAgent | `wiki.write_page` / `wiki.update_index` / `wiki.append_log` / `_extract_entities`(GLM) | `knowledge_base_agent.py:67-270` |
| ScriptWriterAgent | `zhipu.chat`(中文生成) / `zhipu.chat`(翻译) / `zhipu.chat`(核对) | `script_writer_agent.py:120-223` |
| AudioProducerAgent | `_parse_script` / `tts_client.synthesize_segment` / `concat_audio_mp3` | `audio_producer_agent.py:33-241` |
| KBSearchAgent | `_generate_search_keywords`(GLM+本地兜底) / `wiki.search` / `wiki.read_page` / `_generate_answer`(GLM) | `kb_search_agent.py:26-200` |
| FeedbackOptimizerAgent | `_analyze_feedback`(GLM) / `_generate_optimization`(GLM) / `_apply_optimization` | `feedback_optimizer_agent.py:24-176` |
| EvaluationAgent | `evaluator.evaluate_log`(GLM打分) / `_summarize_evaluation` | `evaluation_agent.py:26-111` |

**AI 供应商严格分区**（体现工具调用策略设计）：
- `backend/app/config.py:9-18`：CosyVoice 只用于音频生成，智谱 GLM-5.2 用于其余全部 AI 功能
- `backend/app/agents/audio_producer_agent.py` — AudioProducerAgent 不调用任何 LLM，纯工具调用（解析+TTS+拼接）
- `backend/app/tools/boson_client.py:58-80`：根据文本内容动态决定是否启用 SSML，SSML 失败自动降级为纯文本重试

---

### 职责2：定义 Agent 能力理想态与评估标准，badcase 分析和数据驱动优化

#### 亮点4：完整的 Agent 评测体系 —— 从理想态定义到自动打分

**设计理念**：每个 Agent 都有明确的评估标准（理想态），评测引擎自动对每次调用打分（1-5分），低分输出标记为 badcase，形成"执行→评测→badcase→优化→再评测"的闭环。

**代码证据**：

`backend/app/harness/evaluator.py:12-21` — 8 个 Agent 的评估标准定义：

```python
EVALUATION_CRITERIA = {
    "news_collector_agent": "覆盖度、准确性、去重率、图片质量、来源可靠性",
    "script_writer_agent": "内容连贯性、时长符合度、标签使用合理性、中英一致性",
    "audio_producer_agent": "生成成功率、音色匹配度、拼接流畅度",
    "kb_search_agent": "回答准确性、来源引用完整度、理解用户意图、表达清晰度",
    ...
}
```

`backend/app/harness/evaluator.py:26-82` — `evaluate_log()` 方法：
- L37-58：构建评测 prompt，把 Agent 的输入/输出/状态/错误+评估标准传给 GLM
- L60-67：解析评分结果，更新日志的 `quality_score` 和 `quality_comment`
- L70-77：低分输出自动记录 badcase（含类别、描述、严重程度、优化建议）

#### 亮点5：数据驱动的持续优化闭环

**优化闭环设计**：

```
Agent 执行 → Harness 自动记录日志（输入/输出/工具/耗时/状态）
    ↓
Evaluation Agent 对输出打分（GLM 1-5分 + 评语）
    ↓
低分输出（≤2分）自动标记 badcase + 生成优化建议
    ↓
用户提交反馈 → FeedbackOptimizerAgent 分析根因
    ↓
自动生成 prompt/参数优化建议 → 更新 agent_configs 表
    ↓
下次生成时使用新 prompt → Evaluation Agent 跟踪效果
```

**代码证据**：

- `backend/app/agents/feedback_optimizer_agent.py:24-65` — 完整的反馈处理流程：
  - L67-100：`_analyze_feedback()` — GLM 分析反馈涉及哪个 Agent、问题类别、严重程度、根因
  - L102-144：`_generate_optimization()` — 生成具体优化建议（是否调 prompt/调参数/修正知识库）
  - L146-175：`_apply_optimization()` — 应用优化，记录到日志

- `backend/app/api/monitor.py:43-73` — 评测展示 API：
  - `GET /evaluations` (L43-73)：返回最近评测详情（评分/理由/输入输出预览/badcase数）
  - `GET /evaluations/summary` (L76-118)：各 Agent 汇总（平均分/通过率/成功率/评测标准）

- `backend/app/harness/base_agent.py:23-35` — prompt 版本管理：
  - `get_prompt()` 从 `agent_configs` 表读取 `active=1` 的最新版本
  - `backend/app/api/monitor.py:191-229` — `PUT /configs/{id}` 创建新版本并激活，旧版本保留可回滚

#### 亮点6：badcase 管理机制

**代码证据**：

- `backend/app/harness/logger.py:51-66` — `log_badcase()` 方法，记录 badcase 到 `bad_cases` 表
- `backend/app/database.py:63-72` — `bad_cases` 表结构：关联 agent_log_id、category、description、severity、suggestion、resolved
- `backend/app/api/monitor.py:121-139` — `GET /badcases` 查询 badcase（SQL 显式列名+表前缀避免歧义），`POST /badcases/{id}/resolve` (L142-151) 标记已处理
- 客户端 `android/.../settings/SettingsScreen.kt` — 监控页面 Tab 展示评测详情和 badcase

---

### 职责3：深入理解用户意图与任务场景，设计任务拆解、规划与执行策略

#### 亮点7：用户意图理解 —— 从"生成播客"到 6 步任务编排

**设计理念**：用户只点一个按钮"获取播客"，Orchestrator Agent 理解这个意图后自动拆解为 6 个原子步骤，标注依赖关系，编排执行。

**任务拆解策略**（`orchestrator_agent.py:25-154`）：

```
用户意图："获取播客"
    ↓ Orchestrator 拆解
Step 1: news_collector.run()        — 采集新闻（无依赖）
Step 2: knowledge_base.run(news)     — 更新知识库（依赖 Step1）
Step 3: script_writer.run(news)      — 生成文案（依赖 Step1）
Step 4: audio_producer.run(script)×2 — 生成音频（依赖 Step3，中英并行）
Step 5: save_podcast_record()        — 保存记录（依赖 Step4）
Step 6: evaluation.run(results)      — 质量测评（依赖全部）
```

**进度追踪与状态管理**（L168-176）：
```python
def _update_job_progress(self, progress, detail, status="running", error=None):
    with get_db() as conn:
        conn.execute(
            "UPDATE generation_jobs SET progress=?, detail=?, status=?, error=? WHERE id=?",
            (progress, detail, status, error, self.task_id)
        )
```
- 每步更新进度百分比和当前步骤描述
- 客户端轮询 `GET /api/podcast/jobs/{id}` 实时显示进度
- 生成中可退出 App，重新进入恢复进度

#### 亮点8：知识库智能搜索 Agent —— 理解自然语言查询意图

**设计理念**：用户不需要记住关键词，用自然语言提问即可。KBSearchAgent 先用 GLM 理解查询意图生成搜索关键词，再搜索+读取+综合回答。

**代码证据**：

`backend/app/agents/kb_search_agent.py:26-92`：

```python
async def run(self, query, **kwargs):
    # Step 1: GLM 理解查询意图，生成搜索关键词
    search_keywords = self._generate_search_keywords(query)  # L106-124

    # Step 2: 多关键词搜索 + 去重
    for kw in search_keywords:
        results = self.wiki.search(kw, limit=10)

    # Step 3: 读取 Top5 页面内容
    for r in unique_results[:5]:
        content = self.wiki.read_page(path)

    # Step 4: GLM 综合多源信息生成回答 + 标注来源
    answer = self._generate_answer(query, page_contents)  # L126-157
```

- L106-161 `_generate_search_keywords()`：GLM 将用户问题转化为 3 个搜索关键词，空响应时本地拆分兜底（提取2-6字中文词/英文单词）
- L163-201 `_generate_answer()`：GLM 综合多个页面内容生成回答，空响应时返回来源摘要

---

### 职责4：跟踪 Agent 前沿进展，推动技术应用

#### 亮点9：LLM Wiki 理念落地 —— 持续积累的知识库

**设计理念**：参考 Karpathy 的 LLM Wiki 理念，知识不是每次查询时重新检索（RAG），而是 Agent 增量构建并维护的持久化 Wiki，知识编译一次后持续更新。

**三层架构**（`backend/app/tools/wiki_manager.py`）：
- **Raw Sources**：新闻原文（不可变）
- **The Wiki**：Agent 生成维护的 markdown 文件集合
- **The Schema**：`SCHEMA.md` 规范文档，指导 Agent 如何维护

**代码证据**：

- `backend/app/tools/wiki_manager.py:22-41` — `ensure_structure()` 创建目录结构
- `backend/app/agents/knowledge_base_agent.py:67-103` — `_ingest_one()` 摄入单条新闻：
  - 写新闻摘要页 `domains/ai/sources/{date}-{title}.md`
  - GLM 提取实体 → 更新实体页 `domains/ai/entities/{name}.md`
  - 更新领域概览页 `domains/ai/overview.md`
- `backend/app/tools/wiki_manager.py:84-105` — `update_index()` 重建索引，`append_log()` (L79) 追加日志

#### 亮点10：SSML 标签嵌入文案 —— TTS 精细化控制

**设计理念**：播客文案 Agent 在生成对谈稿时直接嵌入 SSML 标签控制情感/韵律/停顿，音频 Agent 解析后传给 TTS，实现"文案即指令"。

**代码证据**：

- `backend/app/agents/script_writer_agent.py:126-152` — prompt 要求生成带 SSML 标签的文案，明确限制只能用 `<speak>`/`<break>`/`</speak>` 三种标签，严禁 `<|emotion:xxx|>` 等非标准标签
- `backend/app/agents/audio_producer_agent.py:136-210` — `_parse_script()` 解析文案为分段，支持 4 种说话人格式
- `backend/app/tools/boson_client.py:102-103` — 动态启用 SSML：`if "<speak>" in text: kwargs["enable_ssml"] = True`

#### 亮点11：SSE 实时日志流 —— Agent 执行可观测性

**代码证据**：

- `backend/app/api/podcast.py:258-289` — `GET /logs/stream` SSE 端点，通过 `journalctl -f` 实时推送服务日志
- `android/.../ui/podcast/LogStreamScreen.kt` — 客户端 SSE 消费，实时显示日志，按 ERROR/WARN/SUCCESS 着色

#### 亮点12：GLM-5.2 think 模式治理 —— 思考过程与输出分离

**设计理念**：GLM-5.2 开启 think 模式后，模型在 `reasoning_content` 字段推敲情感/韵律/结构，`content` 字段只输出最终成品。但需严格隔离两者，防止思考过程污染文案。

**问题与解决**：
- 关闭 think 模式 → GLM 失去独立思考空间，把 `<|emotion:xxx|>` 标签塞入正文，导致 TTS 报 `SSML text is illegal`
- 开启 think 模式 + 严格隔离 → 模型在 `reasoning_content` 规划，`content` 输出干净文案

**四层防御机制**：

| 层级 | 文件:行号 | 机制 |
|------|-----------|------|
| 1. API 层 | `zhipu_client.py:55-90` | 开启 think 模式，`content` 为空时只记日志、返回空串，绝不返回 `reasoning_content` |
| 2. Prompt 层 | `script_writer_agent.py:145-146` | 明确只能用三种 SSML 标签，严禁 `<\|emotion:xxx\|>`；L152 要求只输出一版最终文案 |
| 3. 清洗层 | `script_writer_agent.py:225-296` | `_clean_script()` 检测多版本分隔词清空旧版本；`_strip_non_ssml_tags()` 移除 `<\|...\|>` 和 `</think> 标签 |
| 4. TTS 兜底 | `boson_client.py:26-48` | `_sanitize_tts_text()` 白名单过滤，调用 TTS 前移除所有非标准标签 |

**多版本重复输出检测**（`script_writer_agent.py:233-254`）：
```python
version_separator = re.compile(
    r'^(让我重新|重新写|再优化|重新优化|修改后|另一个版本|第二个版本|版本[2-9二三四五]|'
    r'重写一遍|调整后|改进版|修改一下|再来一版|最终版|以下是最终|这是修改后)',
    re.IGNORECASE
)
# 遇到版本分隔词 → 清空已积累的行，只保留最后一个版本
```

#### 亮点13：SQL 安全治理 —— 全面排查修复

**修复的 SQL 问题**：

| 文件:行号 | 问题 | 修复 |
|-----------|------|------|
| `wiki_manager.py:130-143` | JOIN `knowledge_pages_fts` + `knowledge_pages` 两表有 `title`/`path` 等重复列，`SELECT *` 导致 ambiguous column | SELECT 列加 `knowledge_pages.` 表前缀 |
| `wiki_manager.py:107-123` | FTS5 `MATCH ?` 直接接收用户输入，含 `"`/`*`/`AND` 等特殊字符触发 SQL 语法错误 | 新增 `_sanitize_fts_query()`，分词后双引号包裹转义 |
| `knowledge_base.py:233-237` | `feedback.podcast_id` 有外键约束，知识库反馈插入 `podcast_id=0` 不存在 → FOREIGN KEY failed | 改为 `VALUES (NULL, ...)` |
| `monitor.py:127-130` | `SELECT bc.*` JOIN `agent_logs` 有 `id`/`created_at` 等重复列隐患 | 改为显式列名 + `bc.` 前缀 |

---

## 三、逐条对应岗位要求

### 要求1：能使用 AI 工具独立完成复杂 vibe coding 任务，有落地产品

**证据**：
- **全栈独立完成**：后端 4936 行 Python + 客户端 1972 行 Kotlin + 部署脚本
- **已部署运行**：`deploy.sh` 一键部署到 CentOS 服务器，systemd 常驻服务
- **使用 AI 工具开发**：整个项目通过 AI 辅助编码（CodeBuddy），从架构设计到代码生成到 debug
- **落地产品**：安卓 APK 已构建安装，真实调用智谱+阿里云 API 生成播客

### 要求2：深入理解 LLM/Agent/RAG 技术原理，熟悉 Agent 核心设计范式

**ReAct 范式体现**：
- `backend/app/agents/news_collector_agent.py:91-353` — NewsCollectorAgent 的 Reason-Act 循环：抓取列表→阅读正文→总结选优
- `backend/app/agents/kb_search_agent.py:26-200` — KBSearchAgent：理解意图→搜索→读取→综合回答，空响应本地兜底

**Plan-and-Execute 范式体现**：
- `backend/app/agents/orchestrator_agent.py:25-154` — Orchestrator 先规划 6 步任务，再逐步执行

**Multi-Agent 范式体现**：
- 8 个专职 Agent 协作，Orchestrator 统一编排
- 中英音频生成并行 `asyncio.gather`（L119-121）
- 反馈触发 FeedbackOptimizer 异步处理 `asyncio.create_task`（`podcast.py:250`）

**RAG 理解**：
- 知识库采用 LLM Wiki 理念（非传统 RAG），知识编译一次后持续更新
- `backend/app/tools/wiki_manager.py:125-144` — SQLite FTS5 全文搜索（带输入转义）+ GLM 辅助搜索
- `backend/app/agents/kb_search_agent.py` — 智能搜索 Agent：关键词扩展+多源综合

### 要求3：有 Agent 或工作流产品实际落地经验，从策略设计到效果验证闭环

**完整闭环**：
```
策略设计（8个Agent + Harness框架）
    ↓
代码实现（4936行后端 + 1972行客户端）
    ↓
部署上线（一键部署 + systemd + 实时日志）
    ↓
效果验证（评测Agent打分 + badcase检测 + 客户端展示）
    ↓
持续优化（反馈→分析→prompt迭代→再验证）
```

### 要求4：数据意识和洞察力，从数据和 badcase 定位根因

**证据**：
- **数据采集**：`agent_logs` 表记录每次 Agent 调用的完整输入/输出/工具/耗时/状态
- **badcase 检测**：`evaluator.py:70-77` 自动检测低分输出并记录 badcase
- **根因分析**：`feedback_optimizer_agent.py:67-100` GLM 分析反馈根因，定位到具体 Agent 和环节
- **指标追踪**：`monitor.py:76-118` 各 Agent 的平均分/通过率/成功率趋势
- **客户端展示**：`SettingsScreen.kt` 评测详情 Tab，评分颜色区分（绿≥4/橙≥3/红<3）

### 要求5：学习能力及自驱力，适应快节奏

**证据**：
- 快速学习并集成多个新技术：智谱 GLM SDK、阿里云 CosyVoice TTS、SSML 标签、LLM Wiki 理念
- 从零搭建全栈项目：FastAPI + SQLite + systemd + Jetpack Compose + Retrofit + ExoPlayer
- 迭代式开发：从需求变更（多领域→只AI、Boson→CosyVoice、glm-5.1→5.2）快速适配

---

## 四、面试回复话术（可直接用）

> 你好！我最近做了一个 AI 播客全栈项目，比较能体现我对 Agent 的理解。
>
> 项目是每天自动采集 AI 领域新闻，通过 8 个 Agent 协作生成中英双语播客，同时维护一个持续积累的知识库。核心设计了一个 Harness Agent 框架——统一负责编排调度、工具注入、日志监控和错误重试，8 个专职 Agent 在框架内协作。
>
> 在 Agent 架构上，我用的是 Plan-and-Execute 范式：Orchestrator Agent 把"生成播客"拆解为 6 个步骤——新闻采集、知识库更新、文案生成、音频合成、保存记录、质量测评。其中音频生成是中英文并行的，用 asyncio.gather 实现。每个 Agent 有专属工具集，通过 ToolRegistry 统一注册和管理。
>
> 在评估和优化上，我设计了完整的闭环：每次 Agent 调用都自动记录输入输出和耗时，Evaluation Agent 用 GLM 对输出打分（1-5分），低分的自动标记为 badcase 并生成优化建议。用户在客户端可以提交反馈，FeedbackOptimizerAgent 会分析根因，生成 prompt 优化建议，更新到数据库的版本管理表中，下次生成时生效。这些评测结果和 badcase 都在客户端有专门页面展示，包括评分、理由、通过率、评判标准。
>
> 还做了一个知识库智能搜索 Agent，用户用自然语言提问，Agent 先用 GLM 理解意图生成搜索关键词，再搜索知识库、读取相关页面、综合多源信息生成回答并标注来源。
>
> 在工程实践上，我解决了 GLM-5.2 think 模式的输出污染问题——通过四层防御机制（API 层严格隔离 reasoning_content、Prompt 层约束标签、清洗层检测多版本+移除非标准标签、TTS 层白名单兜底），确保文案干净。还全面排查修复了 SQL 的 ambiguous column、外键约束、FTS5 注入等问题。
>
> 整个项目后端 4936 行 Python，客户端 1972 行 Kotlin，已部署上线运行。技术上严格区分了两类 AI——CosyVoice 只做音频生成，智谱 GLM-5.2 做其余所有文本类任务。

---

## 五、可能被追问的问题及回答要点

### Q1：为什么用 8 个 Agent 而不是一个大 Agent？

**回答要点**：
- 单一职责：每个 Agent 专注一个任务，prompt 更精准，效果更可控
- 可独立评测：每个 Agent 的输入输出可单独打分和优化
- 可并行：中英音频生成可以并行，缩短整体耗时
- 可替换：换 TTS 供应商只影响 AudioProducerAgent，不影响其他

### Q2：Agent 的 prompt 怎么管理的？

**回答要点**：
- `agent_configs` 表存储所有 prompt 版本，`active=1` 的为当前生效版本
- `BaseAgent.get_prompt()` (`base_agent.py:23-35`) 动态加载当前版本
- `PUT /api/monitor/configs/{id}` (`monitor.py:191-229`) 创建新版本并自动激活，旧版本保留可回滚
- FeedbackOptimizerAgent 分析反馈后生成 prompt 调整建议

### Q3：badcase 怎么发现的？怎么优化的？

**回答要点**：
- 自动发现：Evaluation Agent 对每次输出打分，≤2 分自动记录 badcase
- 手动发现：用户在客户端提交反馈（内容/风格/时长/标签/知识库错误）
- 优化流程：FeedbackOptimizerAgent 分析根因→生成优化建议→更新 prompt 版本→下次生效→Evaluation Agent 跟踪效果
- 举例：GLM 生成非标准 emotion 标签导致 TTS 失败 → 四层防御机制修复

### Q4：知识库为什么不用 RAG 而用 LLM Wiki？

**回答要点**：
- RAG 每次查询重新检索，知识不积累
- LLM Wiki 理念：Agent 增量构建持久化 Wiki，知识编译一次后持续更新
- 每条新闻摄入时自动更新实体页、概念页、索引，交叉引用已预构建
- 搜索时先读索引定位，再读页面，GLM 综合回答
- 适合个人知识库场景：数据量中等（几百个页面），不需要向量检索

### Q5：多 Agent 之间怎么传递数据？

**回答要点**：
- 通过 Orchestrator 的 `results` 字典传递：`results["news_items"]` → 下一个 Agent 的输入
- 持久化数据通过 SQLite 和文件系统：新闻存 `news_items` 表，知识库存 markdown 文件
- 每步有依赖校验：新闻为空不继续，文案为空不继续（`orchestrator_agent.py:64-68, 93-94`）
- 文案长度校验+自动重试（`script_writer_agent.py:43-48`）

### Q6：Agent 执行失败怎么办？

**回答要点**：
- `BaseAgent.execute_with_logging()` 内置指数退避重试（`base_agent.py:84-128`）
- Orchestrator 每步 try-catch，失败不阻塞已完成步骤
- CosyVoice TTS 客户端内置 3 次重试 + 限流退避 + SSML 失败降级纯文本（`boson_client.py:58-80`）
- 超长文本自动切分避免 TTS 413 错误（`audio_producer_agent.py:55-75`，切分前剥离 `<speak>` 标签，切分后重新包裹，MAX_TEXT_LEN=200）
- TTS 文本兜底清洗移除非标准标签（`boson_client.py:26-48`）
- 失败记录到 `agent_logs` 表的 `status=failed` 和 `error` 字段
- 客户端可查看失败日志，提交反馈触发优化

### Q7：GLM-5.2 的 think 模式怎么治理的？

**回答要点**：
- 开启 think 模式让模型在 `reasoning_content` 独立思考，`content` 只输出成品
- `zhipu_client.py:73-84`：`content` 为空时只记日志返回空串，绝不返回 `reasoning_content`（之前 bug 根因）
- `script_writer_agent.py:283-296`：`_strip_non_ssml_tags()` 移除 `<|emotion:xxx|>` 和 `models` 标签
- `script_writer_agent.py:233-254`：检测多版本分隔词，清空旧版本只保留最终版
- `boson_client.py:26-48`：TTS 调用前白名单兜底清洗
