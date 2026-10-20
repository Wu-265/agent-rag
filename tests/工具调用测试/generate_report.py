"""
工具调用测试报告生成器
读取测试结果 JSON，生成可视化 HTML 报告（含 ECharts 图表）
"""
import json
import os
from datetime import datetime


def find_latest_result_file(tests_dir: str) -> str:
    """找到用例数最多的测试结果文件（优先全量测试结果，而不是 only-failed 的子集）"""
    result_files = [f for f in os.listdir(tests_dir)
                    if f.startswith("tool_calling_test_results") and f.endswith(".json")]
    if not result_files:
        raise FileNotFoundError("未找到测试结果文件")

    # 读取每个文件的用例数，选用例数最多的（全量测试结果）
    def get_case_count(filename):
        try:
            with open(os.path.join(tests_dir, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("total_cases", 0)
        except:
            return 0

    result_files.sort(key=get_case_count, reverse=True)
    selected = result_files[0]
    print(f"   自动选用例数最多的结果文件: {selected} ({get_case_count(selected)} 条用例)")
    return os.path.join(tests_dir, selected)



def load_json(file_path: str) -> dict:
    """加载 JSON 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_by_tool(results: list) -> dict:
    """按工具统计：每个工具的用例数、通过数、失败数"""
    tool_stats = {}
    for r in results:
        expected_tool = r.get("expected_tool") or "不调用工具"
        if expected_tool not in tool_stats:
            tool_stats[expected_tool] = {"total": 0, "passed": 0, "failed": 0}
        tool_stats[expected_tool]["total"] += 1
        if r["passed"]:
            tool_stats[expected_tool]["passed"] += 1
        else:
            tool_stats[expected_tool]["failed"] += 1
    return tool_stats


def analyze_by_category(test_cases: list, results: list) -> dict:
    """按类别统计：RAG检索、工具调用、边界测试的通过率"""
    cat_stats = {}
    for case, result in zip(test_cases, results):
        cat = case.get("category", "未分类")
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "passed": 0, "failed": 0}
        cat_stats[cat]["total"] += 1
        if result["passed"]:
            cat_stats[cat]["passed"] += 1
        else:
            cat_stats[cat]["failed"] += 1
    return cat_stats


def generate_html(data: dict, tool_stats: dict, cat_stats: dict, test_cases: list) -> str:
    """生成完整的 HTML 报告"""

    # === 准备图表数据 ===
    tool_names = list(tool_stats.keys())
    tool_pass_rates = [round(tool_stats[t]["passed"] / tool_stats[t]["total"] * 100, 1) for t in tool_names]

    cat_names = list(cat_stats.keys())
    cat_pass_rates = [round(cat_stats[c]["passed"] / cat_stats[c]["total"] * 100, 1) for c in cat_names]
    cat_totals = [cat_stats[c]["total"] for c in cat_names]

    # === 生成用例详情表格 ===
    table_rows = ""
    for case, result in zip(test_cases, data["results"]):
        status_class = "pass" if result["passed"] else "fail"
        status_text = "✅ 通过" if result["passed"] else "❌ 失败"
        actual_tools = ", ".join(result["actual_tools"]) if result["actual_tools"] else "无"
        expected_tool = case["expected_tool"] or "不调用工具"
        table_rows += f"""
        <tr class="{status_class}">
            <td>{case['id']}</td>
            <td>{case['query']}</td>
            <td>{expected_tool}</td>
            <td>{actual_tools}</td>
            <td>{status_text}</td>
        </tr>"""

    # === 失败案例区域（如果有失败的）===
    failed_cases = [(case, result) for case, result in zip(test_cases, data["results"]) if not result["passed"]]
    failed_section = ""
    if failed_cases:
        failed_items = ""
        for case, result in failed_cases:
            failed_items += f"""
            <div class="fail-item">
                <h4>{case['id']}: {case['query']}</h4>
                <p><strong>失败原因：</strong>{result['fail_reason']}</p>
            </div>"""
        failed_section = f"""
        <div class="section">
            <h2>❌ 失败案例分析</h2>
            {failed_items}
        </div>"""

    # === 工具调用链路示例（找调用工具最多的用例）===
    max_tools_case = max(data["results"], key=lambda r: len(r["actual_tools"]))
    chain_tools = " → ".join(max_tools_case["actual_tools"])

    # === 完整 HTML ===
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>工具调用测试报告</title>
    <!-- 引入 ECharts 图表库 -->
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .card .label {{ font-size: 14px; color: #888; margin-bottom: 8px; }}
        .card .value {{ font-size: 28px; font-weight: bold; }}
        .card .value.green {{ color: #52c41a; }}
        .card .value.blue {{ color: #1890ff; }}
        .card .value.orange {{ color: #fa8c16; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 20px; }}
        .section h2 {{ font-size: 20px; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}
        .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .chart {{ height: 350px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #f0f0f0; }}
        th {{ background: #fafafa; font-weight: 600; color: #555; }}
        tr.pass {{ background: #f6ffed; }}
        tr.fail {{ background: #fff2f0; }}
        .fail-item {{ background: #fff2f0; border-left: 4px solid #ff4d4f; padding: 15px; margin-bottom: 10px; border-radius: 4px; }}
        .fail-item h4 {{ color: #ff4d4f; margin-bottom: 8px; }}
        .chain {{ background: #f0f5ff; border-left: 4px solid #1890ff; padding: 15px; border-radius: 4px; font-family: monospace; font-size: 16px; }}
        @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 顶部标题 -->
        <div class="header">
            <h1>🔧 工具调用测试报告</h1>
            <p>测试时间：{data['test_time']} | 测试用例：{data['total_cases']} 条</p>
        </div>

        <!-- 概览卡片 -->
        <div class="cards">
            <div class="card">
                <div class="label">总用例数</div>
                <div class="value">{data['total_cases']}</div>
            </div>
            <div class="card">
                <div class="label">通过率</div>
                <div class="value green">{data['pass_rate']}%</div>
            </div>
            <div class="card">
                <div class="label">工具调用准确率</div>
                <div class="value blue">{data['tool_call_accuracy']}%</div>
            </div>
            <div class="card">
                <div class="label">参数准确率</div>
                <div class="value orange">{data['args_accuracy']}%</div>
            </div>
            <div class="card">
                <div class="label">总耗时</div>
                <div class="value">{data['total_time_seconds']}s</div>
            </div>
        </div>

        <!-- 统计图表 -->
        <div class="section">
            <h2>📊 统计图表</h2>
            <div class="charts">
                <div id="toolChart" class="chart"></div>
                <div id="categoryChart" class="chart"></div>
            </div>
        </div>

        <!-- 工具调用链路示例 -->
        <div class="section">
            <h2>🔗 工具调用链路示例（最复杂用例）</h2>
            <p style="margin-bottom: 10px; color: #666;">用例：{max_tools_case['query']}</p>
            <div class="chain">{chain_tools}</div>
        </div>

        <!-- 失败案例（如果有） -->
        {failed_section}

        <!-- 用例详情表格 -->
        <div class="section">
            <h2>📋 测试用例详情</h2>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>测试问题</th>
                        <th>预期工具</th>
                        <th>实际调用</th>
                        <th>结果</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <!-- ECharts 图表脚本 -->
    <script>
        // 图表1：各工具调用准确率（柱状图）
        var toolChart = echarts.init(document.getElementById('toolChart'));
        toolChart.setOption({{
            title: {{ text: '各工具调用准确率', left: 'center' }},
            tooltip: {{ trigger: 'axis' }},
            xAxis: {{ type: 'category', data: {json.dumps(tool_names, ensure_ascii=False)}, axisLabel: {{ rotate: 30 }} }},
            yAxis: {{ type: 'value', max: 100, name: '准确率(%)' }},
            series: [{{
                type: 'bar',
                data: {json.dumps(tool_pass_rates)},
                itemStyle: {{ color: '#1890ff' }},
                label: {{ show: true, position: 'top', formatter: '{{c}}%' }}
            }}]
        }});

        // 图表2：各类别通过率对比（柱状图+折线图）
        var categoryChart = echarts.init(document.getElementById('categoryChart'));
        categoryChart.setOption({{
            title: {{ text: '各类别通过率对比', left: 'center' }},
            tooltip: {{ trigger: 'axis' }},
            legend: {{ data: ['通过率', '用例数'], bottom: 0 }},
            xAxis: {{ type: 'category', data: {json.dumps(cat_names, ensure_ascii=False)} }},
            yAxis: [
                {{ type: 'value', max: 100, name: '通过率(%)' }},
                {{ type: 'value', name: '用例数' }}
            ],
            series: [
                {{ type: 'bar', name: '通过率', data: {json.dumps(cat_pass_rates)}, itemStyle: {{ color: '#52c41a' }}, label: {{ show: true, position: 'top', formatter: '{{c}}%' }} }},
                {{ type: 'line', name: '用例数', yAxisIndex: 1, data: {json.dumps(cat_totals)}, itemStyle: {{ color: '#fa8c16' }} }}
            ]
        }});

        // 响应式：窗口大小变化时重绘图表
        window.addEventListener('resize', function() {{
            toolChart.resize();
            categoryChart.resize();
        }});
    </script>
</body>
</html>"""
    return html


def main():
    # 路径配置
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tests_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 找到最新的测试结果文件
    result_file = find_latest_result_file(tests_dir)
    print(f"📂 读取测试结果: {os.path.basename(result_file)}")

    # 2. 加载测试结果和测试用例
    data = load_json(result_file)
    test_cases_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cases_tool_calling.json")
    test_cases = load_json(test_cases_file)

    # 3. 统计分析
    tool_stats = analyze_by_tool(data["results"])
    cat_stats = analyze_by_category(test_cases, data["results"])

    # 4. 生成 HTML
    html = generate_html(data, tool_stats, cat_stats, test_cases)

    # 5. 保存报告（带时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(tests_dir, f"tool_calling_test_report_{timestamp}.html")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 报告已生成: {os.path.basename(report_file)}")
    print(f"   用浏览器打开即可查看")


if __name__ == "__main__":
    main()
