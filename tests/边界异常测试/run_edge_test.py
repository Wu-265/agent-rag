"""
边界/对抗 文本测试 通用执行脚本
职责：逐条执行测试用例，记录结果（是否崩溃、耗时、工具调用、回答），不做自动判对错。
判据为人判定：运行后人工阅读每条回答，判断是否合理兜底/是否被诱导/是否成功拒绝。
用法：
    python run_edge_test.py <用例文件名> <测试标题> <输出前缀>
示例：
    python run_edge_test.py test_cases_edge_text.json "边界与异常测试-A类(纯文本边界)" edge_text
    python run_edge_test.py test_cases_adv.json "对抗性与安全测试" adv
"""
import json
import os
import sys
import time
from datetime import datetime

# 把项目根目录加入路径（脚本在 tests/边界异常测试/ 下，要往上跳2级）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.react_agent import ReactAgent


def load_test_cases(file_path: str) -> list:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    # 命令行参数：<用例文件名> <测试标题> <输出前缀>
    if len(sys.argv) < 4:
        print("❌ 用法：python run_edge_test.py <用例文件名> <测试标题> <输出前缀>")
        sys.exit(1)
    cases_filename = sys.argv[1]
    test_title = sys.argv[2]
    output_prefix = sys.argv[3]

    # 路径配置
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_cases_file = os.path.join(base_dir, cases_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(base_dir, f"{output_prefix}_test_results_{timestamp}.json")

    print("=" * 70)
    print(f"🧪 {test_title}")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 加载用例
    config = load_test_cases(test_cases_file)
    cases = config["cases"]
    print(f"📋 加载 {len(cases)} 条测试用例")

    # 初始化 agent
    print("\n🤖 初始化 Agent...")
    agent = ReactAgent()
    print("   Agent 初始化完成")

    # 逐条执行
    print("\n🚀 开始测试...")
    print("-" * 70)

    results = []
    start_time = time.time()

    for case in cases:
        cid = case["id"]
        ctype = case["type"]
        user_input = case["input"]
        note = case.get("expected_note", "")

        print(f"\n[{cid}] {ctype}")
        print(f"   输入: {user_input[:60] if user_input else '(空)'}")

        # 记录单条耗时
        case_start = time.time()
        crashed = False
        error_msg = ""
        answer = ""
        tool_calls = []

        try:
            answer, tool_calls = agent.execute_with_trace(user_input, history=[])
        except Exception as e:
            crashed = True
            error_msg = str(e)[:200]

        case_time = time.time() - case_start

        print(f"   是否崩溃: {'❌ 崩溃!' if crashed else '✅ 正常执行'}")
        print(f"   耗时: {case_time:.1f}s")
        print(f"   调用工具: {[c['tool'] for c in tool_calls] if tool_calls else '无'}")
        if crashed:
            print(f"   错误: {error_msg}")
        else:
            print(f"   回答预览: {answer[:100]}...")

        results.append({
            "id": cid,
            "type": ctype,
            "input": user_input,
            "expected_note": note,
            "crashed": crashed,
            "error_msg": error_msg,
            "time_seconds": round(case_time, 1),
            "tool_calls": [c["tool"] for c in tool_calls],
            "answer": answer,
        })

    end_time = time.time()
    total_time = end_time - start_time

    # 统计
    crash_count = sum(1 for r in results if r["crashed"])
    normal_count = len(results) - crash_count

    print("\n" + "=" * 70)
    print("📊 边界测试执行汇总")
    print("=" * 70)
    print(f"   总用例数: {len(results)}")
    print(f"   正常执行: {normal_count}")
    print(f"   崩溃数: {crash_count}")
    print(f"   总耗时: {total_time:.1f} 秒")
    print("\n   ⚠️ 注意：本测试不自动判定对错，请人工阅读每条回答，判断'是否合理兜底、是否瞎编'。")

    # 保存结果
    output = {
        "test_name": config["test_name"],
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(results),
        "crash_count": crash_count,
        "normal_count": normal_count,
        "total_time_seconds": round(total_time, 1),
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {os.path.basename(output_file)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
