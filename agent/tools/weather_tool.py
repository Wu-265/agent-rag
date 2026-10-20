"""
真实天气工具：基于离线中国城市经纬度库 + Open-Meteo 实时气象接口。

- 地理编码：优先使用本地 data/china_cities.json（覆盖 356 个中国城市，精确匹配，避免同名城市错配）
  ，未命中时回退到 Open-Meteo 地理编码并按人口排序消歧；
- 天气数据：Open-Meteo Forecast API（免费、无需密钥），返回实时天气与未来 3 天预报；
- 带 TTL 缓存，避免高频重复请求。
"""
import json
import math
import time

import requests
from langchain_core.tools import tool

from utils.path_tool import get_abs_path
from utils.logger_handler import logger

# WMO 天气代码 -> 中文描述
WMO_CODE_ZH = {
    0: "晴",
    1: "大致晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "冻雾",
    51: "毛毛雨（轻度）",
    53: "毛毛雨（中度）",
    55: "毛毛雨（密集）",
    56: "冻毛毛雨（轻度）",
    57: "冻毛毛雨（密集）",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨（轻度）",
    67: "冻雨（重度）",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "阵雨（轻度）",
    81: "阵雨（中度）",
    82: "阵雨（剧烈）",
    85: "阵雪（轻度）",
    86: "阵雪（重度）",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}

_city_db = None
_city_cache = {}  # city -> (fetch_time, result_str)
CACHE_TTL_SECONDS = 30 * 60  # 30 分钟

GEOCODE_FALLBACK_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _load_city_db() -> dict:
    """懒加载本地中国城市经纬度库 {城市名: {"lat": "..", "lng": ".."}}"""
    global _city_db
    if _city_db is None:
        db_path = get_abs_path("data/china_cities.json")
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                _city_db = json.load(f)
        except Exception as e:
            logger.error(f"[weather] 加载城市经纬度库失败：{db_path}，原因：{e}")
            _city_db = {}
    return _city_db


def _normalize_city(city: str) -> str:
    """去掉「市」等后缀，若去掉后能在库中精确命中则使用裸名。"""
    city = city.strip().replace(" ", "")
    if city.endswith("市") and city[:-1] in _load_city_db():
        return city[:-1]
    return city


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两坐标点间的球面距离（千米）。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_city(lat: float, lng: float) -> str | None:
    """根据经纬度在本地城市库中查找最近的城市名（用于 IP 定位反查）。"""
    db = _load_city_db()
    best_name, best_dist = None, float("inf")
    for name, rec in db.items():
        try:
            c_lat, c_lng = float(rec["lat"]), float(rec["lng"])
        except (TypeError, ValueError, KeyError):
            continue
        d = _haversine_km(lat, lng, c_lat, c_lng)
        if d < best_dist:
            best_dist, best_name = d, name
    # 距离超过 200km 认为不可靠
    return best_name if best_dist <= 200 else None


def _geocode(city: str) -> tuple[float, float] | None:
    """返回 (纬度, 经度)；本地库未命中时回退 Open-Meteo 地理编码（按人口排序消歧）。"""
    db = _load_city_db()
    key = _normalize_city(city)
    rec = db.get(key)
    if rec:
        try:
            return float(rec["lat"]), float(rec["lng"])
        except (TypeError, ValueError, KeyError):
            pass
    # 回退：Open-Meteo 地理编码，限定中国并按人口取最大
    try:
        r = requests.get(
            GEOCODE_FALLBACK_URL,
            params={"name": city, "count": 10, "language": "zh", "format": "json"},
            timeout=10,
        )
        results = [x for x in (r.json().get("results") or []) if x.get("country_code") == "CN"]
        if results:
            best = max(results, key=lambda x: x.get("population") or 0)
            return best["latitude"], best["longitude"]
    except Exception as e:
        logger.warning(f"[weather] Open-Meteo 地理编码失败：{city}，原因：{e}")
    return None


def _wmo_zh(code) -> str:
    try:
        return WMO_CODE_ZH.get(int(code), f"未知代码({code})")
    except (TypeError, ValueError):
        return "未知"


def _fetch_weather_text(lat: float, lng: float, city: str) -> str:
    """调用 Open-Meteo 获取真实天气并格式化为文本。"""
    params = {
        "latitude": lat,
        "longitude": lng,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": 3,
    }
    r = requests.get(FORECAST_URL, params=params, timeout=15)
    r.raise_for_status()
    j = r.json()

    cur = j.get("current", {})
    daily = j.get("daily", {})
    lines = [
        f"【{city} 实时天气】观测时间：{cur.get('time', '未知')}",
        f"当前天气：{_wmo_zh(cur.get('weather_code'))}",
        f"温度：{cur.get('temperature_2m', 'N/A')}℃（体感 {cur.get('apparent_temperature', 'N/A')}℃）",
        f"相对湿度：{cur.get('relative_humidity_2m', 'N/A')}%",
        f"降水量：{cur.get('precipitation', 'N/A')}mm",
        f"风速：{cur.get('wind_speed_10m', 'N/A')}km/h",
        "未来3天预报：",
    ]
    times = daily.get("time", [])
    codes = daily.get("weather_code", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    prob = daily.get("precipitation_probability_max", [])
    for i in range(len(times)):
        lines.append(
            f"  {times[i]}：{_wmo_zh(codes[i] if i < len(codes) else 0)}，"
            f"{tmin[i] if i < len(tmin) else 'N/A'}~{tmax[i] if i < len(tmax) else 'N/A'}℃，"
            f"降水概率{prob[i] if i < len(prob) else 'N/A'}%"
        )
    lines.append("数据来源：Open-Meteo 实时气象接口（真实数据）")
    return "\n".join(lines)


@tool(description="获取指定城市的实时天气与未来3天预报，返回真实气象数据字符串（含观测时间、温度、湿度、降水、风速等）。入参city为中文城市名，如“郑州”")
def get_weather(city: str) -> str:
    """真实天气工具：city -> 实时天气 + 3 天预报。"""
    now = time.time()
    cached = _city_cache.get(city.strip())
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    geo = _geocode(city)
    if geo is None:
        msg = f"未能识别城市「{city}」的坐标，请提供标准的中国城市名（如“郑州”“北京”），或提供“城市名,纬度,经度”"
        return msg

    lat, lng = geo
    try:
        text = _fetch_weather_text(lat, lng, city)
    except Exception as e:
        logger.error(f"[weather] 获取{city}天气失败：{e}")
        return f"获取「{city}」天气数据失败，请检查网络后重试（错误：{e}）"

    _city_cache[city.strip()] = (now, text)
    return text


if __name__ == "__main__":
    print(get_weather.invoke({"city": "许昌"}))
