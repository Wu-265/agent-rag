"""
工具调用测试脚本
批量运行测试用例，验证 agent 能否在正确时机调用正确的工具、传入正确的参数。
输出：控制台报告 + JSON 结果文件
指标：工具调用准确率、参数准确率
"""
import json
import os
import sys
import time
from datetime import datetime

# 把项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.react_agent import ReactAgent


def load_test_cases(file_path: str) -> list:
    """加载测试用例 JSON 文件。"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_args_match(expected_args: dict, actual_args: dict) -> tuple:
    """
    检查实际参数是否包含预期参数的键值对。
    返回 (是否匹配, 不匹配的原因)
    匹配规则：expected_args 中的每个键值对，都要在 actual_args 中存在且值相等。
    """
    if not expected_args:
        return True, ""  # 没有预期参数，默认通过

    mismatched = []
    for key, expected_value in expected_args.items():
        actual_value = actual_args.get(key)
        if actual_value is None:
            mismatched.append(f"缺少参数 {key}（预期: {expected_value}）")
        elif str(actual_value) != str(expected_value):
            mismatched.append(f"参数 {key} 不匹配（预期: {expected_value}, 实际: {actual_value}）")

    if mismatched:
        return False, "; ".join(mismatched)
    return True, ""


def run_single_test(agent: ReactAgent, test_case: dict) -> dict:
    """
    运行单个测试用例，返回测试结果。
    判断规则：
    - expected_tool 为 null：预期不调用任何工具，实际也没调用 → 工具调用通过
    - expected_tool 不为 null：预期工具在实际调用列表中 → 工具调用通过
    - 如果有 expected_args：还要检查参数是否匹配 → 参数通过
    - 最终通过 = 工具调用通过 AND 参数通过
    """
    query = test_case["query"]
    expected_tool = test_case.get("expected_tool")
    expected_args = test_case.get("expected_args")
    case_id = test_case["id"]

    print(f"  [{case_id}] 问题: {query}")
    print(f"           预期工具: {expected_tool or '不调用工具'}")
    if expected_args:
        print(f"           预期参数: {expected_args}")

    try:
        # 用 execute_with_trace 捕获实际调用
        answer, actual_calls = agent.execute_with_trace(query)

        # 提取实际调用的工具名列表和参数列表
        actual_tools = [c["tool"] for c in actual_calls]
        actual_args_list = [c["args"] for c in actual_calls]
        print(f"           实际调用: {actual_tools if actual_tools else '无'}")

        # === 判断1：工具调用是否正确 ===
        if expected_tool is None:
            # 预期不调用工具
            tool_passed = len(actual_tools) == 0
            tool_fail_reason = "" if tool_passed else f"预期不调用工具，但实际调用了 {actual_tools}"
        else:
            # 预期调用特定工具
            tool_passed = expected_tool in actual_tools
            tool_fail_reason = "" if tool_passed else f"预期调用 {expected_tool}，但实际调用了 {actual_tools}"

        # === 判断2：参数是否正确（仅当有预期参数且工具调用通过时）===
        args_passed = True
        args_fail_reason = ""
        if expected_args and tool_passed and expected_tool is not None:
            # 找到预期工具对应的实际参数
            target_index = actual_tools.index(expected_tool)
            target_args = actual_args_list[target_index]
            args_passed, args_fail_reason = check_args_match(expected_args, target_args)
            if args_passed:
                print(f"           参数检查: ✅ 匹配")
            else:
                print(f"           参数检查: ❌ {args_fail_reason}")

        # === 最终结果 ===
        final_passed = tool_passed and args_passed

        # 汇总失败原因
        fail_reasons = []
        if not tool_passed:
            fail_reasons.append(f"工具调用错误: {tool_fail_reason}")
        if not args_passed:
            fail_reasons.append(f"参数错误: {args_fail_reason}")
        fail_reason = " | ".join(fail_reasons)

        result = {
            "id": case_id,
            "query": query,
            "expected_tool": expected_tool,
            "expected_args": expected_args,
            "actual_tools": actual_tools,
            "actual_args": actual_args_list,
            "tool_passed": tool_passed,
            "args_passed": args_passed,
            "passed": final_passed,
            "fail_reason": fail_reason,
            "answer_preview": answer[:100] if answer else "",
        }

        status = "✅ 通过" if final_passed else "❌ 失败"
        print(f"           结果: {status}")
        if fail_reason:
            print(f"           原因: {fail_reason}")

        return result

    except Exception as e:
        print(f"           结果: ❌ 异常")
        print(f"           异常: {str(e)[:200]}")
        return {
            "id": case_id,
            "query": query,
            "expected_tool": expected_tool,
            "expected_args": expected_args,
            "actual_tools": [],
            "actual_args": [],
            "tool_passed": False,
            "args_passed": False,
            "passed": False,
            "fail_reason": f"执行异常: {str(e)[:200]}",
            "answer_preview": "",
        }


def main():
    # 路径配置
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_cases_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cases_tool_calling.json")
    # 结果文件名带时间戳，保留历史记录，不覆盖
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"tool_calling_test_results_{timestamp}.json")

    print("=" * 70)
    print("🔧 工具调用测试（含参数准确率）")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 加载测试用例
    print(f"\n📋 加载测试用例: {test_cases_file}")
    test_cases = load_test_cases(test_cases_file)
    print(f"   共 {len(test_cases)} 条测试用例")
    # 支持 --only-failed 参数：只跑上次失败的用例
    if "--only-failed" in sys.argv:
        # 找到最近一次的测试结果文件
        result_files = sorted([f for f in os.listdir(os.path.dirname(os.path.abspath(__file__)))
                               if (f.startswith("tool_calling_test_results_") or f == "tool_calling_test_results.json")
                               and f.endswith(".json")],
                              reverse=True)

        if result_files:
            latest_result_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), result_files[0])
            with open(latest_result_file, "r", encoding="utf-8") as f:
                latest_result = json.load(f)
            failed_ids = [r["id"] for r in latest_result["results"] if not r["passed"]]
            test_cases = [c for c in test_cases if c["id"] in failed_ids]
            print(f"   🎯 只跑上次失败的用例：{len(test_cases)} 条（{failed_ids}）")
        else:
            print("   ⚠️  未找到历史测试结果，将运行全部用例")


    # 统计有预期参数的用例数
    args_cases = [c for c in test_cases if c.get("expected_args")]
    print(f"   其中 {len(args_cases)} 条含参数校验")

    # 初始化 agent
    print("\n🤖 初始化 Agent...")
    agent = ReactAgent()
    print("   Agent 初始化完成")

    # 批量运行测试
    print(f"\n🚀 开始批量测试（共 {len(test_cases)} 条）...")
    print("-" * 70)

    results = []
    start_time = time.time()

    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}]")
        result = run_single_test(agent, case)
        results.append(result)

    end_time = time.time()
    total_time = end_time - start_time

    # === 统计结果 ===
    # 总体通过率
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    pass_rate = passed_count / len(results) * 100 if results else 0

    # 工具调用准确率
    tool_passed_count = sum(1 for r in results if r["tool_passed"])
    tool_pass_rate = tool_passed_count / len(results) * 100 if results else 0

    # 参数准确率（只统计有预期参数的用例）
    args_results = [r for r in results if r.get("expected_args")]
    if args_results:
        args_passed_count = sum(1 for r in args_results if r["args_passed"])
        args_pass_rate = args_passed_count / len(args_results) * 100
    else:
        args_passed_count = 0
        args_pass_rate = 0

    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"  总用例数: {len(results)}")
    print(f"  最终通过: {passed_count}")
    print(f"  最终失败: {failed_count}")
    print(f"  最终通过率: {pass_rate:.1f}%")
    print()
    print(f"  🛠️  工具调用准确率: {tool_passed_count}/{len(results)} ({tool_pass_rate:.1f}%)")
    if args_results:
        print(f"  📝 参数准确率: {args_passed_count}/{len(args_results)} ({args_pass_rate:.1f}%)")
    print(f"  ⏱️  总耗时: {total_time:.1f} 秒")
    print(f"  📈 平均每条: {total_time / len(results):.1f} 秒")

    # 按类别统计
    print("\n📂 按类别统计:")
    categories = {}
    for case, result in zip(test_cases, results):
        cat = case.get("category", "未分类")
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "tool_passed": 0}
        categories[cat]["total"] += 1
        if result["passed"]:
            categories[cat]["passed"] += 1
        if result["tool_passed"]:
            categories[cat]["tool_passed"] += 1

    for cat, stats in categories.items():
        rate = stats["passed"] / stats["total"] * 100
        tool_rate = stats["tool_passed"] / stats["total"] * 100
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({rate:.1f}%) [工具调用: {tool_rate:.1f}%]")

    # 按工具统计
    print("\n🔧 按工具统计（工具调用准确率）:")
    tool_stats = {}
    for case, result in zip(test_cases, results):
        expected_tool = case.get("expected_tool") or "不调用工具"
        if expected_tool not in tool_stats:
            tool_stats[expected_tool] = {"total": 0, "tool_passed": 0}
        tool_stats[expected_tool]["total"] += 1
        if result["tool_passed"]:
            tool_stats[expected_tool]["tool_passed"] += 1

    for tool_name, stats in tool_stats.items():
        rate = stats["tool_passed"] / stats["total"] * 100
        print(f"  {tool_name}: {stats['tool_passed']}/{stats['total']} ({rate:.1f}%)")

    # 失败案例详情
    if failed_count > 0:
        print("\n❌ 失败案例详情:")
        for result in results:
            if not result["passed"]:
                print(f"  [{result['id']}] {result['query']}")
                print(f"       原因: {result['fail_reason']}")

    # 保存结果到 JSON
    output = {
        "test_name": "工具调用测试（含参数准确率）",
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": round(pass_rate, 1),
        "tool_call_accuracy": round(tool_pass_rate, 1),
        "args_accuracy": round(args_pass_rate, 1),
        "total_time_seconds": round(total_time, 1),
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
