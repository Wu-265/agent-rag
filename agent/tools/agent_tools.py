from datetime import datetime

import requests
from langchain_core.tools import tool

from agent.tools.weather_tool import get_weather, nearest_city
from agent.tools.file_tools import analyze_file
from rag.rag_service import RagSummarizerService
from utils.config_handler import agent_conf
from utils.logger_handler import logger

rag = RagSummarizerService()

external_data = {}


@tool(description="从向量知识库中检索参考资料来回答用户问题。检索时注意：1.检索时应从用户问题中提取核心关键词和具体细节（如产品名、故障现象、距离/数量/百分比等数值）作为检索词，以提高检索准确性。2.将用户问题的口语化表述改写为知识库文档中可能使用的简洁术语或短语（例如用户问‘有几个防跌落传感器’，应检索‘防跌落传感器数量’或‘防跌落传感器’这类库内可能出现的词），以提高检索召回率。3.优先使用精准名词而非整句")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)


@tool(description="获取用户所在城市的真实城市名，以纯字符串形式返回。优先读取配置中的user_city，否则通过IP定位并反查最近城市。")
def get_user_location() -> str:
    """真实用户城市：配置优先，否则 IP 定位反查最近城市。"""
    # 1. 配置优先（最可靠）
    user_city = (agent_conf.get("user_city") or "").strip()
    if user_city:
        return user_city

    # 2. IP 定位（ip-api，无需密钥）
    try:
        r = requests.get("http://ip-api.com/json/?lang=zh-CN", timeout=12)
        j = r.json()
        if j.get("status") == "success" and "lat" in j and "lon" in j:
            city = nearest_city(float(j["lat"]), float(j["lon"]))
            if city:
                return city
    except Exception as e:
        logger.warning(f"[get_user_location] IP定位失败：{e}")

    return "（无法自动获取用户城市，请在 config/agent.yml 中配置 user_city，或直接询问用户所在城市）"


@tool(description="获取当前用户ID，以纯字符串形式返回。读取配置中的default_user_id。")
def get_user_id() -> str:
    """真实用户ID：读取配置，而非随机。"""
    uid = (agent_conf.get("default_user_id") or "").strip()
    if uid:
        return uid
    return "（未配置 default_user_id，请在 config/agent.yml 中设置）"


@tool(description="获取系统当前真实月份，以纯字符串形式返回，格式为YYYY-MM。")
def get_current_month() -> str:
    """真实当前月份。"""
    return datetime.now().strftime("%Y-%m")

@tool(description="把摄氏度转换为华氏度，输入摄氏温度数值，返回华氏温度")
def celsius_to_fahrenheit(celsius: float) -> float:
    """把摄氏度转为华氏度"""
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius}°C = {fahrenheit:.1f}°F"

@tool(description="获取今日日期，返回固定值")
def get_month() -> str:
    return "今日日期为2026-9-11"

def generate_external_data():
    """
    {
        "user_id": {
            "month" : {"特征":xxx, "效率":xxx, "耗材":xxx, "对比":xxx}
        }
    }
    """
    if not external_data:
        from utils.path_tool import get_abs_path
        import os

        external_data_path = get_abs_path(agent_conf["external_data_path"])

        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            next(f)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                arr = line.split(",")

                user_id: str = arr[0].replace('"', "")
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                comparison: str = arr[4].replace('"', "")
                time: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "耗材": consumables,
                    "对比": comparison,
                }


@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回；若该月无记录，则回退返回该用户最近可用的月份记录并明确标注，均返回真实数据")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    user_records = external_data.get(user_id)
    if not user_records:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}的使用记录数据")
        return ""

    if month in user_records:
        return str(user_records[month])

    # 无当月记录：回退到该用户最近可用的月份（真实数据，明确标注）
    months = sorted(user_records.keys())
    if months:
        fallback_month = months[-1]
        logger.warning(f"[fetch_external_data]用户{user_id}在{month}无记录，回退到最近可用月份{fallback_month}")
        return f"（注：用户{user_id}在{month}暂无记录，以下为该用户最近可用月份 {fallback_month} 的真实记录）\n{user_records[fallback_month]}"

    return ""


@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_已调用"

