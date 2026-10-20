"""
文件分析工具：让 Agent 能分析上传文件中的真实内容与数据，所有结果均由程序实际计算得出。

- 文件工作区：记录当前上传文件，供 Streamlit 前端与分析工具共享；
- analyze_file：读取 CSV / Excel / TXT / PDF / JSON，返回**程序实际计算**得到的统计结果，
  所有数字均来自 pandas / jieba 的真实计算，杜绝模型凭空编造。
"""
import io
import json
import os
import re
from collections import Counter

import pandas as pd
from langchain_core.tools import tool

from utils.path_tool import get_abs_path
from utils.logger_handler import logger

try:
    import jieba

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# 文本分析常用中文停用词
STOPWORDS = set(
    """的 了 和 是 在 我 有 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 我们 你们 他们 它 他 她 与 及 或 等 而 之 为 被 把 但 而 于 中 下 里 外 对 从 以 再 又 还 只 才 都 更 最 较 个 这 那 些 们 地 得 呢 吗 吧 啊 呀 哦 嗯 年 月 日 分 秒 时间 如果 然后 因为 所以 但是 虽然 比如 例如 可以 需要 进行 使用 通过 以及 相关 一个 两个 三个 我们 你们 他们 其中 其他 这些 那些 这样 那样 什么 怎么 为什么 如何 是否 这个 那个 请 您 使用 产品 功能 可以 需要 进行 表示 提供 包括 支持 分为 主要 常见 情况 问题 解决 建议 注意 说明 内容 信息 数据 文件 文档 可能 应该 必须 根据 关于 对于 以下 如下 上述 如下""".split()
)


class FileWorkspace:
    """文件工作区：记录当前上传文件（供前端与分析工具共享）。"""

    def __init__(self):
        self.current_file = None  # 当前上传文件的绝对路径
        self.current_name = None  # 当前上传文件的名字

    def set_current_file(self, path: str):
        self.current_file = os.path.abspath(path)
        self.current_name = os.path.basename(path)


workspace = FileWorkspace()


# ---------------------------------------------------------------------------
# 文件读取
# ---------------------------------------------------------------------------

def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _decode_text(data: bytes) -> tuple[str, str]:
    """按常见编码顺序解码文本，返回 (文本, 使用的编码)。"""
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "latin-1"):
        try:
            return data.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(replace)"


def _resolve_file(file_path: str) -> str | None:
    """解析工具入参：优先使用传入路径，否则使用当前上传文件。"""
    if file_path and file_path.strip():
        p = os.path.abspath(file_path.strip())
        if os.path.exists(p):
            return p
        # 支持传入相对 data/uploads 的文件名
        alt = get_abs_path(os.path.join("data", "uploads", file_path.strip()))
        if os.path.exists(alt):
            return alt
        return None
    if workspace.current_file and os.path.exists(workspace.current_file):
        return workspace.current_file
    return None


def _detect_garbage(path: str, sample_size: int = 100 * 1024) -> tuple[bool, str]:
    """
        检测文件是否存在大量乱码/不可打印字符，返回 (是否有问题, 问题描述)。

        原理：
        1. 只读取文件前 100KB（大文件不用全读，采样足够判断）
        2. 用项目已有的 _decode_text 按常见编码尝试解码
        3. 统计解码后文本中"不可打印字符"和"替换字符(�)"的比例
        4. 超过 30% 认为文件可能损坏/乱码/编码错误
        """
    try:
        with open(path, "rb") as f:
            raw = f.read(sample_size)
    except Exception as e:
        return True, f"文件读取失败：{e}"

    if not raw:
        return True, "文件为空（0字节），请检查上传是否完整"

    text, used_enc = _decode_text(raw)
    # ===== 新增：如果 fallback 到了 latin-1，说明正常编码都失败了，直接判定为有问题 =====
    if "latin-1" in used_enc:
        return (
            True,
            f"文件无法用 UTF-8/GBK 等常见编码正常解码（最终使用了 {used_enc} 兜底解码）。"
            f"该文件可能是二进制文件、已损坏，或并非真实的文本/表格文件。"
            f"请检查文件来源与格式后重新上传。"
        )
    # 统计不可打印字符（控制字符，排除换行/制表符等正常空白）
    control_chars = sum(
        1 for ch in text
        if ord(ch) < 32 and ch not in ("\n", "\r", "\t")
    )
    # 统计替换字符 �（Unicode U+FFFD，解码失败的标志）
    replacement_chars = text.count("\ufffd")
    # 统计常见乱码模式（连续的非中文非英文非数字的奇怪字符）
    total = len(text) if text else 1
    bad_ratio = (control_chars + replacement_chars) / total

    if bad_ratio > 0.3:
        return (
            True,
            f"文件前 {len(raw)} 字节中，不可打印/乱码字符占比 {bad_ratio:.1%}（使用 {used_enc} 解码）。"
            f"该文件可能已损坏、编码不兼容，或并非真实的文本/表格文件。"
            f"建议检查文件来源与编码后重新上传。"
        )

    if replacement_chars > 0:
        return (
            False,
            f"注意：文件中检测到 {replacement_chars} 个解码替换字符（�），"
            f"可能存在少量编码问题，分析结果仅供参考。"
        )

    return False, ""


def _load_tabular(path: str) -> pd.DataFrame | None:
    """读取表格文件（CSV/Excel/类CSV的txt）。失败返回 None。"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            return pd.read_excel(path)
        if ext == ".csv":
            data, _ = _decode_text(_read_bytes(path))
            try:
                return pd.read_csv(io.StringIO(data))
            except Exception:
                return pd.read_csv(io.StringIO(data), sep=None, engine="python")
        if ext in (".txt", ".md"):
            data, _ = _decode_text(_read_bytes(path))
            try:
                df = pd.read_csv(io.StringIO(data), sep=None, engine="python")
            except Exception:
                return None
            # 仅当解析出多列且至少两列有较高非空率时才认为是表格，否则按文本处理
            if len(df.columns) >= 2:
                good_cols = sum(1 for c in df.columns if df[c].notna().mean() > 0.6)
                if good_cols >= 2:
                    return df
            return None
    except Exception as e:
        logger.warning(f"[file_tools] 表格解析失败 {path}：{e}")
        return None
    return None


def _read_text_content(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from utils.file_handler import pdf_loader
            docs = pdf_loader(path)
            return "\n".join(d.page_content for d in docs)
        except Exception as e:
            logger.warning(f"[file_tools] PDF 解析失败 {path}：{e}")
            return ""
    data, _ = _decode_text(_read_bytes(path))
    return data


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 统计分析
# ---------------------------------------------------------------------------

def _fmt(v, ndigits: int = 2) -> str:
    try:
        if isinstance(v, float):
            return f"{v:.{ndigits}f}"
        return str(v)
    except Exception:
        return str(v)


def _tabular_analysis(df: pd.DataFrame, name: str) -> str:
    lines = [f"【文件 {name}】表格数据统计（由程序实际计算）："]
    lines.append(f"规模：{df.shape[0]} 行 × {df.shape[1]} 列")
    lines.append(f"列名：{', '.join(str(c) for c in df.columns)}")

    dup = int(df.duplicated().sum())
    lines.append(f"重复行数：{dup}")

    # 各列缺失值
    missing = df.isna().sum()
    miss_info = [f"{c}:{int(missing[c])}" for c in df.columns if int(missing[c]) > 0]
    lines.append(f"缺失值：{'；'.join(miss_info) if miss_info else '无'}")

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        lines.append("数值列统计（count/均值/标准差/最小/25%/中位/75%/最大）：")
        desc = df[num_cols].describe(percentiles=[0.25, 0.5, 0.75]).T
        for c in num_cols:
            if c in desc.index:
                row = desc.loc[c]
                lines.append(
                    f"  {c}：n={int(row['count'])}，均值={_fmt(row['mean'])}，"
                    f"标准差={_fmt(row['std'])}，最小={_fmt(row['min'])}，"
                    f"25%={_fmt(row['25%'])}，中位={_fmt(row['50%'])}，75%={_fmt(row['75%'])}，"
                    f"最大={_fmt(row['max'])}"
                )
        # 数值列相关性
        if len(num_cols) >= 2:
            corr = df[num_cols].corr()
            pairs = []
            for i in range(len(num_cols)):
                for j in range(i + 1, len(num_cols)):
                    v = corr.iloc[i, j]
                    if pd.notna(v):
                        pairs.append((num_cols[i], num_cols[j], float(v)))
            pairs.sort(key=lambda t: abs(t[2]), reverse=True)
            top = pairs[:5]
            if top:
                lines.append("数值列相关性（绝对值前5）：")
                for a, b, v in top:
                    lines.append(f"  {a} ~ {b}：r={_fmt(v)}")

    cat_cols = df.select_dtypes(include="object").columns.tolist()
    for c in cat_cols:
        vc = df[c].value_counts()
        top = vc.head(5)
        lines.append(f"分类列「{c}」取值Top5：")
        for val, cnt in top.items():
            lines.append(f"  {val}：{int(cnt)} 条")
        if len(vc) > 5:
            lines.append(f"  （其余 {len(vc) - 5} 种取值）")

    lines.append("注：以上数字为程序读取文件后实际计算所得，可直接引用，无需编造。")
    result =  "\n".join(lines)

    # ===== 新增：输出长度截断 =====
    MAX_OUTPUT = 3000
    if len(result) > MAX_OUTPUT:
        result = result[
                     :MAX_OUTPUT] + f"\n\n（注：分析结果过长，已截断至 {MAX_OUTPUT} 字。如需了解更多细节，请针对具体列提问。）"
    return result
def _text_analysis(text: str, name: str) -> str:
    content = text
    clean = re.sub(r"\s+", " ", content).strip()
    total_chars = len(clean)
    total_chars_no_space = len(re.sub(r"[\s，。、；：？！,.!?;:'\"“”‘’（）()【】\[\]《》<>-]", "", clean))
    lines = content.splitlines()
    paras = [p for p in content.split("\n\n") if p.strip()]

    out = [f"【文件 {name}】文本内容统计（由程序实际计算）："]
    out.append(f"总字符数：{total_chars}（去除空白与标点约 {total_chars_no_space}）")
    out.append(f"总行数：{len(lines)}，段落数：{len(paras)}")
    out.append(f"文本预览（前200字）：{clean[:200]}")

    if HAS_JIEBA and total_chars_no_space > 20:
        words = [
            w.strip()
            for w in jieba.lcut(clean)
            if w.strip() and w not in STOPWORDS and len(w) > 1 and re.search(r"[\u4e00-\u9fa5A-Za-z]", w)
        ]
        top = Counter(words).most_common(20)
        if top:
            out.append("高频关键词Top20：")
            for w, c in top:
                out.append(f"  {w}：{c} 次")
    result =  "\n".join(out)
    # ===== 新增：输出长度截断 =====
    MAX_OUTPUT = 3000
    if len(result) > MAX_OUTPUT:
        result = result[:MAX_OUTPUT] + f"\n\n（注：分析结果过长，已截断至 {MAX_OUTPUT} 字。）"
    return result

@tool(
    description="分析当前上传文件（或指定file_path）中的真实内容与数据。支持CSV/Excel/TXT/PDF/JSON，返回程序实际计算得到的统计结果（行数列数、数值统计、缺失值、分类分布、关键词等），数字均来自真实计算，严禁编造。")
def analyze_file(file_path: str = "") -> str:
    """分析上传文件，返回基于真实计算的结构化统计结果。"""
    path = _resolve_file(file_path)
    if path is None:
        return (
            "尚未检测到可分析的文件。请先在界面左侧上传 CSV/Excel/TXT/PDF/JSON 文件，"
            "或传入有效的 file_path 参数。"
        )

    has_garbage, garbage_msg = _detect_garbage(path)
    if has_garbage:
        return f"⚠️ 文件检测未通过：{garbage_msg}\n\n为避免基于乱码数据产生错误分析，已暂停本次分析。请检查文件后重新上传。"

    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()

    # 表格类
    if ext in (".csv", ".xlsx", ".xls"):
        df = _load_tabular(path)
        if df is not None:
            return _tabular_analysis(df, name)
        return f"文件 {name} 无法按表格解析，请确认格式是否为 CSV/Excel。"

    # 表格类（txt/md 先尝试解析为表格）
    if ext in (".txt", ".md"):
        df = _load_tabular(path)
        if df is not None:
            return _tabular_analysis(df, name)

    # JSON
    if ext == ".json":
        try:
            obj = _load_json(path)
        except Exception as e:
            return f"文件 {name} JSON 解析失败：{e}"
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            df = pd.json_normalize(obj)
            return _tabular_analysis(df, name)
        return f"文件 {name} 为 JSON，内容：{json.dumps(obj, ensure_ascii=False)[:800]}"

    # 文本类（txt/md/pdf）
    text = _read_text_content(path)
    if not text.strip():
        return f"文件 {name} 未提取到有效文本内容。"
    return _text_analysis(text, name)

# import pandas as pd
# def count_rows(csv_path: str) -> int:
#     try:
#         df = pd.read_csv(csv_path)
#         return df.shape[0]
#     except Exception as e:
#         return -1
#
# def count_missing_per_column(csv_path: str) -> dict:
#     try:
#         df = pd.read_csv(csv_path)
#         series = df.isna().sum()
#         return series.to_dict()
#     except Exception as e:
#         return -1
#
# def numeric_column_means(csv_path: str) -> dict:
#     try:
#         df = pd.read_csv(csv_path)
#         line = df.select_dtypes(include="number").columns
#         average = df[line].mean()
#         return average.to_dict()
#     except Exception as e:
#         return -1
#
# def pair_lists(keys: list, values: list) -> dict:
#     if len(keys) != len(values):
#         return {}
#     series = zip(keys, values)
#     return dict(series)
#
# def simple_text_analysis(text: str) -> str:
#     text1 = text.replace(" ","")
#     text2 = text.split(" ")
#     return str(len(text1))+str(len(text2))
