# AI 闯关学习小程序 - 后端

基于 FastAPI + LangChain + DeepSeek 的后端服务。

## 技术栈

- **框架**: FastAPI 0.115.0
- **LLM 编排**: LangChain 1.3.18 + LangGraph 1.2.11
- **联网检索**: langchain-tavily 0.2.18（TavilySearch / TavilyExtract）
- **模型**: DeepSeek (通过 OpenAI 兼容 API)
- **数据校验**: Pydantic v2
- **日志**: Structlog
- **测试**: Pytest
- **用户系统**: MySQL 8 + aiomysql + PyJWT + 微信 code2Session

## 项目结构

```
backend/
├── app/
│   ├── api/v1/routes/     # API 路由
│   ├── clients/            # 微信等外部服务客户端
│   ├── core/              # 核心配置（设置、日志、异常）
│   ├── models/            # 领域模型
│   ├── repositories/      # MySQL 数据访问
│   ├── prompts/           # Prompt 模板
│   ├── llm/               # LangChain 集成（出题智能体 + Tavily 工具薄封装）
│   ├── services/          # 业务服务层（含联网检索编排 retrieval_service）
│   ├── utils/             # 工具函数
│   └── main.py            # 应用入口
├── tests/                 # 测试文件
├── requirements.txt       # Python 依赖
└── .env.example          # 环境变量示例
```

## 环境要求

- Python 3.11+
- pip 或 poetry

## 安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 到 `.env` 并配置：

```bash
cp .env.example .env
```

关键配置项：
```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-chat
# 出题联网检索（可选）。未配置 TAVILY_API_KEY 或 SEARCH_ENABLED=false 时
# 自动降级为纯模型出题，响应会带 search_used=false 标记。
TAVILY_API_KEY=your_tavily_api_key_here
SEARCH_ENABLED=true
AGENT_RECURSION_LIMIT=8
AGENT_TIMEOUT_SECONDS=60
TAVILY_MAX_RESULTS=6
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=ai_learn
WECHAT_APP_ID=your_wechat_app_id
WECHAT_APP_SECRET=your_wechat_app_secret
JWT_SECRET_KEY=replace_with_a_high_entropy_secret
AVATAR_UPLOAD_DIR=uploads/avatars
AVATAR_MAX_SIZE_MB=5
```

初始化用户系统表：

```bash
mysql -u root -p < sql/001_initialize_user_system.sql
```

## 运行

```bash
# 开发模式
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_health.py

# 带覆盖率报告
pytest --cov=app tests/
```

## API 接口

### 健康检查
- `GET /api/v1/health` - 服务健康状态

### 题库生成
- `POST /api/v1/quiz/generate` - 生成问答题库
  ```json
  {
    "user_input": "我想学习 RAG 和传统搜索的区别",
    "question_count": 5,
    "difficulty": "mixed"
  }
  ```
  响应在 `quiz_id/title/summary/questions` 之外新增生成时的检索元数据：
  - `search_used`：本次题目是否经过联网资料核实
  - `sources`：实际采用的资料来源列表（`[{title, url}]`，最多 8 条）

  出题智能体可自主调用 Tavily 搜索（关键词）与 Tavily 提取（网页整页），
  依据主题自主选择搜索深度、时间范围、域名范围与检索词语言；用户输入中
  包含网页 URL 时会优先提取整页内容作为学习材料。

  两种失败路径语义不同：
  - **检索成功但无可读资料**（含网页提取全部失败）→ HTTP 422，
    提示换个说法/补充背景或确认链接有效，不返回题目；
  - **搜索服务故障 / 未配置 Key / 循环超限 / AI 自主跳过检索** → 正常返回
    纯模型题库，但 `search_used=false`，前端展示「未经联网核实」提示。

### 报告生成
- `POST /api/v1/report/generate` - 生成学习报告
  ```json
  {
    "quiz_id": "quiz_xxx",
    "topic": "RAG 入门",
    "questions": [...],
    "answer_records": [...]
  }
  ```

### 用户系统

- `POST /api/v1/user/login` - 以 `Taro.login()` 返回的 `code` 换取 JWT
- `GET /api/v1/user/profile` - 获取当前用户档案和累计学习统计
- `PUT /api/v1/user/profile` - 更新昵称或头像 URL
- `POST /api/v1/user/avatar` - 上传头像图片（multipart 字段 `file`，支持 JPG/PNG/WebP，
  默认最大 5 MB），校验通过后存储并返回更新后的档案
- `GET /api/v1/user/quizzes?page=1&page_size=10` - 分页读取已完成闯关历史
- `GET /api/v1/user/quizzes/unfinished?limit=20` - 读取已生成但未完成的闯关
- `GET /api/v1/user/quizzes/{quiz_id}` - 读取本人拥有的完整题目、答案和报告
- `GET /api/v1/user/quizzes/{quiz_id}/resume` - 读取本人题库用于继续作答
- `GET /api/v1/user/weak-points` - 聚合最近报告中的高频薄弱知识点

用户接口要求 `Authorization: Bearer <token>`。出题和报告接口采用可选鉴权：无 token
时仍保留原有匿名体验，但不会写入用户数据。

### 头像存储

头像图片保存在 `AVATAR_UPLOAD_DIR`（默认 `uploads/avatars/<user_id>/`，已加入
`.gitignore`），启动时通过 `/static/avatars` 静态目录对外提供访问，数据库中保存
`{API_BASE_URL}/static/avatars/...` 完整 URL，需保证小程序端可以访问 `API_BASE_URL`。

### 专项训练

- `POST /api/v1/quiz/drill` - 针对薄弱知识点定向出题（需登录）
  ```json
  {
    "focus": "向量数据库",
    "question_count": 5
  }
  ```
  `focus` 省略时自动选取用户最近报告中最高频的薄弱点；无薄弱点记录时返回 404。
  生成的题库标题会带上「专项训练 ·」前缀并持久化，可在首页继续闯关。

## 核心模块说明

### LLM 层 (`app/llm/`)
- `langchain_factory.py` - 创建 ChatOpenAI 实例
- `output_schemas.py` - 结构化输出 Schema (Pydantic)
- `quiz_agent.py` - 出题智能体（LangChain `create_agent` + Tavily 双工具，循环/时长受限）
- `quiz_tools.py` - TavilySearch/TavilyExtract 薄封装（错误分类留痕、来源抽取）
- `quiz_chain.py` - 纯模型出题链路（现作为降级路径）
- `report_chain.py` - 报告链路

### Prompt 层 (`app/prompts/`)
- `quiz_prompt.py` - `quiz_prompt_v3` 智能体系统提示词 + 降级模板
- `report_prompt.py` - 报告 Prompt 模板

### 服务层 (`app/services/`)
- `retrieval_service.py` - 联网检索编排与三态兜底聚合（ok / no_results / unavailable）
- `quiz_service.py` - 出题业务逻辑（智能体优先、降级兜底、校验、转换）
- `report_service.py` - 报告业务逻辑
- `weak_point_service.py` - 薄弱点聚合（供专项训练与推荐使用）

## 开发注意事项

1. 所有 LLM 调用必须通过 LangChain 结构化输出
2. Prompt 模板版本化管理（quiz_prompt_v3 智能体提示词，降级路径沿用 v2 模板加保守引导）
3. 输出必须经过服务层校验
4. 日志使用 structlog，结构化输出
5. 出题联网检索依赖 `langchain-tavily` 官方工具：`country`（国别）与
   `max_results` 仅能在实例化时设置（官方在调用时显式禁止），地域相关性
   通过 agent 动态填 `include_domains/exclude_domains` 与检索词语言实现；
   结果条数为固定的 `TAVILY_MAX_RESULTS`

## TDD 开发

运行测试确保代码质量：
```bash
pytest -v
```
