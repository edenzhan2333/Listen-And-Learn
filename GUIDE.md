# Listen and Learn —— 部署与使用指南

> 本文档将指导你从零开始完成项目部署和日常使用。请按顺序操作。

---

## 目录

1. [整体流程概览](#1-整体流程概览)
2. [第一步：部署后端到服务器](#2-第一步部署后端到服务器)
3. [第二步：构建安卓 APK](#3-第二步构建安卓-apk)
4. [第三步：安装并配置 App](#4-第三步安装并配置-app)
5. [第四步：日常使用指南](#5-第四步日常使用指南)
6. [第五步：Agent 监控与优化](#6-第五步agent-监控与优化)
7. [常见问题排查](#7-常见问题排查)
8. [本地开发调试](#8-本地开发调试)

---

## 1. 整体流程概览

```
┌─────────────────────────────────────────────────────────────┐
│                    完整部署流程                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ① 运行 deploy.sh ──→ 后端部署到 49.232.226.131             │
│     （在本地 Mac 终端执行）         ↓                        │
│                                    后端服务启动              │
│                                    http://49.232.226.131:8000│
│                                                             │
│  ② Android Studio 打开 android/  ──→ 构建 APK               │
│     （用 Android Studio 操作）        ↓                     │
│                                      得到 app-debug.apk     │
│                                                             │
│  ③ 安装 APK 到手机 ──→ 输入后端地址 ──→ 开始使用            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**预计耗时**：
- 后端部署：5-10 分钟
- APK 构建：10-20 分钟（首次需下载 SDK）
- App 配置：1 分钟

**前置条件**：

| 工具 | 是否已具备 | 说明 |
|------|-----------|------|
| Mac 终端 | ✅ 已有 | 用于执行部署脚本 |
| Android Studio | ❓ 需安装 | 用于构建 APK，[下载地址](https://developer.android.com/studio) |
| 一台安卓手机 | ❓ | 用于安装 App |

---

## 2. 第一步：部署后端到服务器

### 2.1 执行一键部署

打开 **Mac 终端**（Terminal），执行以下命令：

```bash
cd /Users/eden/Desktop/listenandlearn
chmod +x deploy.sh
./deploy.sh
```

### 2.2 部署过程说明

脚本会自动完成以下操作，你只需要等待：

```
[INFO] === Listen and Learn 一键部署 ===
[INFO] Step 1: 同步代码到服务器 49.232.226.131:/opt/listenandlearn
    → 将后端代码上传到服务器（约10秒）

[INFO] Step 2: 远程安装 Python 环境和系统依赖
    → yum/dnf 安装 python3、ffmpeg 等
    → 创建虚拟环境
    → pip install 安装所有 Python 依赖
    → 写入 .env（含你的两个 API Key）
    → 创建数据目录
    （约2-3分钟）

[INFO] 创建 systemd 服务
    → 注册为系统服务，开机自启、崩溃自动重启

[INFO] 启动服务
    → systemctl start listenandlearn

[INFO] 健康检查
    → curl http://localhost:8000/api/health

[SUCCESS] 服务已启动并运行中
```

### 2.3 验证部署成功

部署完成后，在浏览器中访问以下地址验证：

| 验证项 | 地址 | 预期结果 |
|--------|------|----------|
| 健康检查 | `http://49.232.226.131:8000/api/health` | `{"status":"ok","version":"1.0.0"}` |
| API 文档 | `http://49.232.226.131:8000/docs` | 看到 Swagger 文档页面 |
| 根路径 | `http://49.232.226.131:8000/` | 返回 JSON 信息 |

如果以上都能正常访问，后端部署成功 ✅

### 2.4 如果部署失败

```bash
# 查看服务器上的服务日志
ssh root@49.232.226.131
# 密码: EdenZhan2333

# 在服务器上执行：
systemctl status listenandlearn      # 查看服务状态
journalctl -u listenandlearn -n 50   # 查看最近50行日志
```

常见问题：
- **端口被占用**：编辑 `/etc/systemd/system/listenandlearn.service` 修改端口
- **依赖安装失败**：在服务器上手动执行 `cd /opt/listenandlearn && ./venv/bin/pip install -r requirements.txt`

---

## 3. 第二步：构建安卓 APK

### 3.1 安装 Android Studio

如果尚未安装，前往 https://developer.android.com/studio 下载并安装。

### 3.2 打开项目

1. 启动 Android Studio
2. 选择 **File → Open**
3. 选择 `/Users/eden/Desktop/listenandlearn/android` 目录
4. 点击 **Open**

### 3.3 等待 Gradle 同步

首次打开时，Android Studio 会：
- 自动下载所需版本的 Gradle
- 自动下载 Android SDK 组件
- 同步项目依赖

**这个过程可能需要 5-15 分钟**，右下角会显示进度。请耐心等待直到底部状态栏显示 "Gradle sync finished"。

如果提示缺少 SDK，点击提示中的链接自动安装即可。

### 3.4 构建 APK

1. 菜单栏点击 **Build → Build Bundle(s) / APK(s) → Build APK(s)**
2. 等待构建完成（首次约 2-5 分钟）
3. 构建成功后，右下角会弹出通知，点击 **locate** 找到 APK 文件

APK 文件位置：
```
android/app/build/outputs/apk/debug/app-debug.apk
```

### 3.5 如果构建报错

| 错误 | 解决方案 |
|------|----------|
| SDK 版本不匹配 | 在 SDK Manager 中安装 compileSdk 34 |
| Gradle 下载失败 | 检查网络，或配置代理后重试 |
| Kotlin 版本错误 | 让 Android Studio 自动修复（点击提示） |

---

## 4. 第三步：安装并配置 App

### 4.1 安装 APK 到手机

**方法一：通过数据线**
1. 用 USB 数据线连接手机和电脑
2. 将 `app-debug.apk` 复制到手机
3. 在手机上点击该文件安装（需允许"未知来源安装"）

**方法二：通过 Android Studio 直接安装**
1. 手机开启 **开发者选项 → USB 调试**
2. USB 连接电脑
3. 在 Android Studio 中点击 ▶️ Run 按钮

### 4.2 首次配置后端地址

打开 App 后，第一件事是配置后端地址：

1. 打开 **Listen and Learn** App
2. 看到"请输入后端服务地址"界面
3. 输入：
   - **服务器 IP 地址**：`49.232.226.131`
   - **端口号**：`8000`
4. 点击 **测试连接**
5. 看到 "连接成功!" 后，地址自动保存，进入主界面 ✅

> 之后如需修改，在 App 内 **设置 → 修改后端地址** 即可。

---

## 5. 第四步：日常使用指南

### 5.1 生成今日播客

1. 打开 App，默认进入 **播客** Tab
2. 点击右下角的 **获取播客** 按钮
3. 界面顶部显示生成进度条和当前步骤：
   ```
   进度: 30% - 正在采集6个领域的新闻...
   进度: 50% - 正在更新知识库...
   进度: 65% - 正在生成播客文案...
   进度: 75% - 正在生成播客音频...
   进度: 95% - 正在评估生成质量...
   ```
4. **生成过程中可以随时退出 App**，后端会继续执行
5. 重新打开 App 时，会自动恢复显示进度
6. 生成完成后（进度 100%），播客出现在列表中

**生成耗时**：约 3-8 分钟（取决于新闻采集和音频合成速度）

### 5.2 收听播客

1. 在播客列表中点击某一天的播客
2. 进入详情页，顶部有 **中文 / English** 切换 Tab
3. 点击播放按钮 ▶️ 开始收听
   - 支持拖动进度条快进/快退
   - 可以在文案区域阅读完整对谈稿
4. 播客下方显示当日 6 大领域的新闻素材

### 5.3 提交反馈（优化 Agent）

听完播客后，可以提交反馈让 Agent 持续改进：

1. 在播客详情页点击右上角 **反馈** 按钮
2. 选择反馈类型：
   - 内容问题（新闻不准确、遗漏重要内容）
   - 播客风格（对谈不够自然、节奏不好）
   - 时长问题（太长或太短）
   - 标签使用（TTS 效果不好、情感不对）
   - 知识库错误
3. 填写反馈内容
4. 点击 **提交**

> 反馈会被 Feedback Optimizer Agent 分析，自动调整对应 Agent 的 prompt，下次生成时生效。

### 5.4 浏览知识库

1. 点击底部 **知识库** Tab
2. **搜索**：在顶部搜索框输入关键词，点击搜索图标
3. **浏览**：点击下方领域卡片（AI、互联网、智能制造等）查看该领域所有页面
4. 点击任意页面查看详情（Markdown 渲染）

知识库特点：
- 纯中文，持续积累
- 每日自动更新（生成播客时同步更新）
- 包含新闻摘要页、实体页（公司/产品/人物）、概念页
- 页面间有交叉引用

### 5.5 修改设置

1. 点击底部 **设置** Tab
2. 可操作：
   - **修改后端地址**：更换服务器时使用
   - **Agent 监控**：查看各 Agent 运行状态（下节详述）
   - 查看版本信息

---

## 6. 第五步：Agent 监控与优化

### 6.1 查看监控总览

在 App 中：**设置 → Agent 监控**

显示内容：
- **Badcase 统计**：总数 / 未解决数
- **各 Agent 统计**：
  - 调用次数
  - 成功率
  - 平均耗时
  - 平均质量分（1-5 分）

### 6.2 详细监控（浏览器）

在电脑浏览器中访问后端 API 获取更详细的信息：

| 功能 | 地址 |
|------|------|
| 监控总览 | `http://49.232.226.131:8000/api/monitor/overview` |
| Agent 日志列表 | `http://49.232.226.131:8000/api/monitor/logs` |
| 某个 Agent 的日志 | `http://49.232.226.131:8000/api/monitor/logs?agent_name=news_collector_agent` |
| 日志详情（含完整输入输出） | `http://49.232.226.131:8000/api/monitor/logs/{日志ID}` |
| Badcase 列表 | `http://49.232.226.131:8000/api/monitor/badcases` |
| 未解决 Badcase | `http://49.232.226.131:8000/api/monitor/badcases?resolved=0` |
| Agent 配置（prompt 版本） | `http://49.232.226.131:8000/api/monitor/configs` |

**最方便的方式**：直接访问 `http://49.232.226.131:8000/docs`，在 Swagger UI 中交互式调用所有 API。

### 6.3 数据驱动优化机制

项目内置的优化闭环：

```
Agent 执行 → 自动记录日志（输入/输出/工具/耗时）
    ↓
Evaluation Agent 对输出打分（1-5分）
    ↓
低分输出（≤2分）标记为 badcase
    ↓
你提交反馈 → Feedback Optimizer 分析
    ↓
自动调整 Agent prompt 版本
    ↓
下次生成时使用新 prompt
    ↓
Evaluation Agent 对比新旧效果
    ↓
效果提升 → 固化；效果下降 → 可回滚
```

### 6.4 如何优化 Agent

发现问题时，有两种优化方式：

**方式一：通过 App 反馈**（推荐）
- 在播客详情页提交反馈，系统自动处理

**方式二：直接修改 Agent prompt**
1. 访问 `http://49.232.226.131:8000/api/monitor/configs` 查看当前配置
2. 通过 API 更新 prompt：
   ```
   PUT http://49.232.226.131:8000/api/monitor/configs/{配置ID}
   Body: {"prompt_text": "新的prompt内容"}
   ```
3. 新版本会自动激活，旧版本保留可回滚

---

## 7. 常见问题排查

### Q1: 后端服务无法访问

```bash
# SSH 登录服务器检查
ssh root@49.232.226.131
# 密码: EdenZhan2333

systemctl status listenandlearn    # 服务是否在运行
journalctl -u listenandlearn -n 50 # 查看错误日志

# 重启服务
systemctl restart listenandlearn

# 检查端口是否监听
ss -tlnp | grep 8000
```

### Q2: App 连接后端失败

1. 确认手机和服务器网络通畅
2. 检查输入的地址是否正确：`49.232.226.131`，端口 `8000`
3. 用手机浏览器访问 `http://49.232.226.131:8000/api/health` 测试
4. 注意：地址前缀 `http://` 是自动加的，只需输入 IP 和端口

### Q3: 播客生成失败

1. 在 App 中查看进度页的错误提示
2. 检查 Agent 日志：
   ```
   http://49.232.226.131:8000/api/monitor/logs?status=failed
   ```
3. 常见原因：
   - 智谱 API 额度用完 → 检查智谱控制台
   - Boson API 额度用完 → 检查 Boson 控制台
   - 新闻搜索超时 → 重新点击"获取播客"重试

### Q4: 音频播放没声音

- 检查手机音量
- 检查播客状态是否为 `ready`（列表中显示播放图标）
- 如果显示"音频生成中"，说明还在后台生成，等待即可

### Q5: 知识库搜索没结果

- 知识库需要先生成过播客才有内容
- 尝试更简单的关键词（如 "AI" 而不是 "人工智能最新发展"）

### Q6: 服务器磁盘空间不足

播客音频文件会占用空间，系统每天凌晨 3 点自动清理超过 180 天的文件。如需手动清理：

```bash
ssh root@49.232.226.131
cd /opt/listenandlearn
du -sh data/*              # 查看各目录占用
# 手动清理30天前的文件：
find data/podcasts -maxdepth 1 -type d -name "202*" -mtime +30 -exec rm -rf {} \;
```

---

## 8. 本地开发调试

### 8.1 后端本地运行

```bash
cd /Users/eden/Desktop/listenandlearn/backend

# 激活虚拟环境（已创建）
source venv/bin/activate

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 访问 http://localhost:8000/docs 查看 API
```

本地 `.env` 已配置好（使用 `./data` 作为数据目录），API Key 已填入。

### 8.2 查看本地数据库

```bash
cd /Users/eden/Desktop/listenandlearn/backend
sqlite3 data/listenandlearn.db

# 常用查询
.tables                                          # 查看所有表
SELECT * FROM podcasts ORDER BY date DESC LIMIT 5;
SELECT agent_name, status, quality_score FROM agent_logs ORDER BY id DESC LIMIT 20;
SELECT * FROM bad_cases WHERE resolved=0;
.quit
```

### 8.3 查看知识库文件

```bash
# 知识库 markdown 文件
ls -la /Users/eden/Desktop/listenandlearn/backend/data/knowledge_base/
cat /Users/eden/Desktop/listenandlearn/backend/data/knowledge_base/index.md
cat /Users/eden/Desktop/listenandlearn/backend/data/knowledge_base/log.md

# 播客文件
ls -la /Users/eden/Desktop/listenandlearn/backend/data/podcasts/
```

### 8.4 服务器管理常用命令

```bash
# SSH 登录
ssh root@49.232.226.131
# 密码: EdenZhan2333

# 服务管理
systemctl status listenandlearn     # 查看状态
systemctl restart listenandlearn    # 重启
systemctl stop listenandlearn       # 停止
systemctl start listenandlearn      # 启动
journalctl -u listenandlearn -f     # 实时查看日志

# 查看资源占用
htop
df -h
du -sh /opt/listenandlearn/data/*

# 更新代码后重新部署
exit  # 回到本地
cd /Users/eden/Desktop/listenandlearn
./deploy.sh
```

---

## 快速操作速查表

| 我想... | 操作 |
|--------|------|
| 部署后端 | 终端执行 `cd /Users/eden/Desktop/listenandlearn && ./deploy.sh` |
| 构建 APK | Android Studio 打开 `android/` → Build APK |
| 验证后端 | 浏览器访问 `http://49.232.226.131:8000/api/health` |
| 生成播客 | App → 播客 Tab → 获取播客 |
| 收听播客 | App → 播客列表 → 点击日期 → 播放 |
| 提交反馈 | App → 播客详情 → 反馈 |
| 搜索知识库 | App → 知识库 Tab → 输入关键词搜索 |
| 查看 Agent 日志 | 浏览器访问 `http://49.232.226.131:8000/docs` |
| 查看服务器日志 | `ssh root@49.232.226.131` → `journalctl -u listenandlearn -f` |
| 重启后端服务 | `ssh root@49.232.226.131` → `systemctl restart listenandlearn` |
| 重新部署后端 | 终端执行 `./deploy.sh` |

---

## 现在就开始

**第一步**（现在就做）—— 打开终端部署后端：

```bash
cd /Users/eden/Desktop/listenandlearn && ./deploy.sh
```

**第二步**（后端部署完成后）—— 下载安装 Android Studio 并构建 APK

**第三步**（APK 安装后）—— 打开 App，输入 `49.232.226.131:8000`，开始使用
