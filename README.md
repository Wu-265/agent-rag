# 🤖 AI Agent 通用智能助手

基于 **ReAct 架构** 的通用智能助手，支持**工具调用、RAG 知识库检索、多轮对话、文件数据分析**。前端使用 Streamlit 构建，大模型与 Embedding 走阿里云通义千问（DashScope）。

## ✨ 功能特性

- 🌤️ **实时天气查询**：根据用户地理位置查询当前城市天气
- 📄 **文件数据分析**：上传 CSV / Excel / TXT / PDF / JSON 等文件，让助手分析数据并给出结论
- 🔍 **RAG 知识库问答**：基于本地方量数据库（ChromaDB）检索知识库，回答产品常见故障、选购指南等问题
- 💬 **多轮对话记忆**：保留最近 N 轮历史消息，实现上下文连贯的对话
- 🗂️ **外部数据联动**：读取外部用户记录（`data/external/records.csv`）生成报告
- 🧩 **工具化扩展**：ReAct 智能体按需调用工具（天气、定位、文件分析、RAG 摘要、报表生成等）

## 🧱 技术栈

| 分类 | 技术 |
| --- | --- |
| 前端 | Streamlit |
| Agent 框架 | LangChain · LangGraph · ReAct |
| 向量数据库 | ChromaDB |
| 大模型 | 通义千问 `qwen-max`（ChatTongyi） |
| Embedding | DashScope `text-embedding-v4` |
| 数据处理 | Pandas · python-docx · jieba |
| 其他 | PyYAML · Requests |

## 📁 项目结构

```
.
├── agent/                  # Agent 核心
│   ├── react_agent.py      # ReAct 智能体（流式/非流式执行）
│   └── tools/              # 工具集：天气、文件、RAG、中间件等
├── app.py                  # Streamlit 入口
├── config/                 # 配置文件（模型、向量库、提示词路径等）
├── model/                  # 模型工厂（Chat / Embedding）
├── prompts/                # 系统提示词与各场景提示词
├── rag/                    # RAG 服务：向量检索、摘要生成
├── tests/                  # 自动化测试脚本与用例
├── utils/                  # 通用工具：配置、文件、日志、路径、提示词加载
└── .gitignore              # 忽略隐私/缓存/数据文件
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- 阿里云 DashScope API Key（`qwen-max` 与 `text-embedding-v4`）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> 项目当前未内置 `requirements.txt`，可参考下列核心依赖安装：
> `langchain` `langchain-community` `langchain-core` `langchain-text-splitters` `langgraph` `chromadb` `streamlit` `dashscope` `pandas` `python-docx` `jieba` `requests` `pyyaml`

### 3. 配置 API Key

模型通过环境变量读取密钥（LangChain 通义集成默认读取 `DASHSCOPE_API_KEY`）：

```bash
# Windows (PowerShell)
$env:DASHSCOPE_API_KEY="你的_Key"

# macOS / Linux
export DASHSCOPE_API_KEY="你的_Key"
```

### 4. 启动

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`，即可开始对话。

## ⚙️ 配置说明

配置集中在 `config/` 目录（YAML）：

- `rag.yml`：对话模型名（`chat_model_name`）与 Embedding 模型名（`embedding_model_name`）
- `chroma.yml`：向量库集合名、持久化目录、分块参数（`chunk_size` / `chunk_overlap`）、检索 Top-K
- `agent.yml`：默认用户 ID、城市、上传文件目录
- `prompts.yml`：各场景提示词文件路径

## 🧪 测试

`tests/` 目录包含自动化测试脚本与用例（多轮会话、工具调用、边界异常、RAG 检索质量等），可通过对应 `run_*.py` 脚本执行。

## 📌 说明

- **知识库数据**（`data/` 目录：产品知识、上传文件、用户记录等）属于私有数据，已通过 `.gitignore` 排除，**不会进入版本库**。如需使用 RAG 问答，请在本地将知识文档放入 `data/` 目录后重建向量库。
- **密钥安全**：`.env`、`*.key` 等敏感文件已被 `.gitignore` 排除，请勿将 API Key 硬编码进代码或提交到仓库。

## 📄 License

本项目为个人学习项目，未指定开源许可证。
