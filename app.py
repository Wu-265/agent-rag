import os
import time

import streamlit as st
from agent.react_agent import ReactAgent
from agent.tools.file_tools import workspace
from utils.path_tool import get_abs_path
from utils.config_handler import agent_conf
from utils.logger_handler import logger

# 页面配置（必须在所有 st 调用之前）
st.set_page_config(
    page_title="AI Agent 通用智能助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- 会话状态 ----------
if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

# Agent 版本号：每当 agent 工具集/能力变更时 +1，用于让运行中的服务器自动重建 agent
AGENT_VERSION = 3

# 标题
st.title("🤖 AI Agent 通用智能助手")
st.caption("基于 ReAct 架构 · 支持工具调用 · RAG 知识库检索 · 多轮对话 · 文件数据分析")
st.divider()

# 欢迎语与示例问题（仅在没有对话历史时显示）
if not st.session_state["message"]:
    st.markdown("#### 👋 你好，我可以帮你做这些：")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🌤️ **查询实时天气**\n\n试试问：今天天气怎么样？")
    with col2:
        st.info("📄 **分析上传文件**\n\n试试问：分析这个文件的数据")
    with col3:
        st.info("🔍 **知识库问答**\n\n试试问：产品常见故障有哪些？")
    st.write("")  # 用空行代替分隔线，更清爽

# 工具栏
if st.session_state["message"]:
    col_tool1, _ = st.columns([1, 5])
    with col_tool1:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state["message"] = []
            st.rerun()


# ---------- 侧边栏 ----------
with st.sidebar:
    # ===== 项目标识 =====
    st.markdown("## 🤖 AI Agent")
    st.caption("通用智能助手 · v1.0")
    st.divider()

    # ===== 技术栈标签 =====
    st.markdown("**技术栈**")
    st.markdown(
        "`LangChain` `ReAct` `ChromaDB` `通义千问` `Streamlit` `DashScope Embedding`",
        help="项目使用的核心技术与框架"
    )
    st.divider()

    # ===== 文件上传 =====
    st.markdown("### 📄 文件上传与分析")
    uploaded = st.file_uploader(
        "上传文件（CSV / Excel / TXT / PDF / JSON）",
        type=["csv", "xlsx", "xls", "txt", "pdf", "json", "md"],
        key="file_uploader",
    )
    st.caption("上传后可直接向助手提问，例如：\n“分析这个文件的数据”\n“根据这个文件能得出什么结论”")

    current_file = st.session_state.get("current_file")
    if current_file and os.path.exists(current_file):
        st.success(f"当前文件：{os.path.basename(current_file)}")

    # ===== 系统状态 =====
    st.divider()
    st.markdown("**系统状态**")

    # 显示当前使用的模型（从配置读取）
    try:
        from utils.config_handler import rag_conf

        model_name = rag_conf.get("chat_model_name", "未知")
        st.markdown(f"- 🧠 模型：`{model_name}`")
    except Exception:
        st.markdown("- 🧠 模型：`已连接`")

    # 显示对话轮数
    msg_count = len(st.session_state.get("message", []))
    st.markdown(f"- 💬 对话轮数：{msg_count // 2} 轮")

    # 显示当前文件状态
    if current_file and os.path.exists(current_file):
        file_size = os.path.getsize(current_file)
        if file_size > 1024 * 1024:
            size_str = f"{file_size / 1024 / 1024:.1f} MB"
        else:
            size_str = f"{file_size / 1024:.1f} KB"
        st.markdown(f"- 📎 已加载文件：{size_str}")
    else:
        st.markdown("- 📎 未加载文件")

    if uploaded is not None:
        # ===== 文件大小上限检查 =====
        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
        if uploaded.size > MAX_FILE_SIZE:
            st.error(f"文件过大：{uploaded.size / 1024 / 1024:.1f}MB，超过上限 20MB。请压缩文件或拆分后重新上传。")
            st.stop()  # 停止后续执行，不保存文件

        # 保存上传文件到 data/uploads
        upload_dir = get_abs_path(agent_conf["upload_dir"])
        os.makedirs(upload_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(upload_dir, f"{ts}_{uploaded.name}")
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state["current_file"] = save_path
        workspace.set_current_file(save_path)
        st.success(f"已上传并保存：{uploaded.name}（{uploaded.size} 字节）")
        st.info("现在可以在下方提问，让客服分析文件内容了。")

# ---------- 渲染历史消息 ----------
for message in st.session_state["message"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ---------- 输入 ----------
prompt = st.chat_input("输入你的问题，或上传文件后让我分析数据...")

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    response_messages = []
    file_path = st.session_state.get("current_file")

    with st.spinner("智能客服思考中......."):
        try:
            # 传入历史消息（不含刚追加的当前问题），实现多轮记忆
            res_stream = st.session_state["agent"].execute_stream(
                prompt, file_path=file_path, history=st.session_state["message"][:-1]
            )

            def capture(generator, cache_list):
                for chunk in generator:
                    cache_list.append(chunk)
                    for char in chunk:
                        time.sleep(0.001)
                        yield char

            st.chat_message("assistant").write_stream(capture(res_stream, response_messages))
        except Exception as e:
            logger.error(f"[app.py] Agent 执行失败：{e}", exc_info=True)
            # 给用户看友好提示，而不是红色堆栈
            st.error(f"抱歉，智能客服处理时出现异常：{str(e)[:200]}")
            st.info("请稍后重试，或检查网络连接与 API 配置。")
    if response_messages:
        st.session_state["message"].append(
            {"role": "assistant", "content": response_messages[-1]}
        )
    st.rerun()

# 页脚
st.write("")
st.markdown(
    """
    <div style="text-align: center; color: #888; font-size: 14px;">
        <p>🤖 AI Agent 通用智能助手 · v1.0</p>
        <p>基于 ReAct 架构 · LangChain · ChromaDB · 通义千问 · Streamlit</p>
    </div>
    """,
    unsafe_allow_html=True,
)
