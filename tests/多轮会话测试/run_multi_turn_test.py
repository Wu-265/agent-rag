"""
多轮对话测试脚本
批量运行多轮对话测试用例，验证 agent 的上下文记忆、指代消解、逻辑连贯能力。
判断方式：关键词匹配（预期回答包含指定关键词）
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.react_agent import ReactAgent


def load_test_cases(file_path: str) -> list:
    """加载测试用例 JSON 文件。"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_keywords(answer: str, expected_keywords: list) -> tuple:
    """检查回答是否包含所有预期关键词，返回 (是否通过, 失败原因)。"""
    if not expected_keywords:
        return True, ""  # 没有预期关键词，默认通过（第一轮只是输入信息）

    missing = []
    for kw in expected_keywords:
        if kw not in answer:
            missing.append(kw)

    if missing:
        return False, f"缺少关键词: {missing}"
    return True, ""


def run_single_dialogue(agent: ReactAgent, test_case: dict) -> dict:
    """运行一组多轮对话测试。"""
    dialogue_id = test_case["id"]
    dialogue_name = test_case["name"]
    turns = test_case["turns"]

    print(f"\n  【{dialogue_id}】{dialogue_name}")
    print(f"  共 {len(turns)} 轮")

    history = []  # 历史消息，每轮运行后追加
    turn_results = []
    passed_count = 0
    checked_count = 0

    for turn in turns:
        turn_num = turn["turn"]
        query = turn["query"]
        expected_keywords = turn.get("expected_keywords")
        note = turn.get("note", "")

        print(f"\n    第{turn_num}轮: {query}")
        if note:
            print(f"      备注: {note}")
        if expected_keywords:
            print(f"      预期关键词: {expected_keywords}")

        try:
            # 关键：把 history 传给 execute_with_trace，模拟多轮对话
            answer, tool_calls = agent.execute_with_trace(query, history=history)

            # 把这轮的问答加入历史，供下一轮使用
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": answer})

            # 检查关键词（只有设置了预期关键词的轮次才判断）
            if expected_keywords:
                checked_count += 1
                passed, fail_reason = check_keywords(answer, expected_keywords)
                if passed:
                    passed_count += 1
                    print(f"      ✅ 通过")
                else:
                    print(f"      ❌ 失败（{fail_reason}）")
            else:
                passed = True
                fail_reason = "无预期关键词，不判断"
                print(f"      ⏭️  不判断（仅输入信息）")

            print(f"      回答预览: {answer[:80]}...")
            if tool_calls:
                print(f"      调用工具: {[c['tool'] for c in tool_calls]}")

            turn_results.append({
                "turn": turn_num,
                "query": query,
                "expected_keywords": expected_keywords,
                "answer": answer,
                "tool_calls": [c["tool"] for c in tool_calls],
                "passed": passed,
                "fail_reason": fail_reason,
            })

        except Exception as e:
            print(f"      ❌ 异常: {str(e)[:100]}")
            turn_results.append({
                "turn": turn_num,
                "query": query,
                "expected_keywords": expected_keywords,
                "answer": "",
                "tool_calls": [],
                "passed": False,
                "fail_reason": f"执行异常: {str(e)[:100]}",
            })

    # 计算这组对话的通过率
    dialogue_pass_rate = passed_count / checked_count * 100 if checked_count > 0 else 100

    return {
        "id": dialogue_id,
        "name": dialogue_name,
        "category": test_case.get("category", "未分类"),
        "total_turns": len(turns),
        "checked_turns": checked_count,
        "passed_turns": passed_count,
        "pass_rate": round(dialogue_pass_rate, 1),
        "turn_results": turn_results,
    }


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_cases_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cases_multi_turn.json")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"multi_turn_test_results_{timestamp}.json")

    print("=" * 70)
    print("🔄 多轮对话测试")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 加载测试用例
    print(f"\n📋 加载测试用例: {os.path.basename(test_cases_file)}")
    test_cases = load_test_cases(test_cases_file)
    total_turns = sum(len(tc["turns"]) for tc in test_cases)
    print(f"   共 {len(test_cases)} 组对话，{total_turns} 轮")

    # 初始化 agent
    print("\n🤖 初始化 Agent...")
    agent = ReactAgent()
    print("   Agent 初始化完成")

    # 批量运行
    print(f"\n🚀 开始测试...")
    print("-" * 70)

    results = []
    start_time = time.time()

    for i, case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}]")
        result = run_single_dialogue(agent, case)
        results.append(result)

    end_time = time.time()
    total_time = end_time - start_time

    # 统计
    total_checked = sum(r["checked_turns"] for r in results)
    total_passed = sum(r["passed_turns"] for r in results)
    overall_pass_rate = total_passed / total_checked * 100 if total_checked > 0 else 0

    # 按类别统计
    category_stats = {}
    for r in results:
        cat = r["category"]
        if cat not in category_stats:
            category_stats[cat] = {"checked": 0, "passed": 0}
        category_stats[cat]["checked"] += r["checked_turns"]
        category_stats[cat]["passed"] += r["passed_turns"]

    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"  对话组数: {len(results)}")
    print(f"  总轮数: {total_turns}")
    print(f"  判断轮数: {total_checked}")
    print(f"  通过轮数: {total_passed}")
    print(f"  整体通过率: {overall_pass_rate:.1f}%")
    print(f"  总耗时: {total_time:.1f} 秒")

    print("\n📂 按组统计:")
    for r in results:
        print(f"  {r['id']} {r['name']}: {r['passed_turns']}/{r['checked_turns']} ({r['pass_rate']}%)")

    print("\n📂 按类别统计:")
    for cat, stats in category_stats.items():
        rate = stats["passed"] / stats["checked"] * 100 if stats["checked"] > 0 else 0
        print(f"  {cat}: {stats['passed']}/{stats['checked']} ({rate:.1f}%)")

    # 失败详情
    failed_turns = []
    for r in results:
        for tr in r["turn_results"]:
            if not tr["passed"] and tr["expected_keywords"]:
                failed_turns.append({
                    "dialogue_id": r["id"],
                    "dialogue_name": r["name"],
                    "turn": tr["turn"],
                    "query": tr["query"],
                    "expected_keywords": tr["expected_keywords"],
                    "answer": tr["answer"][:100],
                    "fail_reason": tr["fail_reason"],
                })

    if failed_turns:
        print("\n❌ 失败轮次详情:")
        for ft in failed_turns:
            print(f"  [{ft['dialogue_id']}] 第{ft['turn']}轮: {ft['query']}")
            print(f"       预期关键词: {ft['expected_keywords']}")
            print(f"       原因: {ft['fail_reason']}")

    # 保存结果（带时间戳，不覆盖）
    output = {
        "test_name": "多轮对话测试",
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_dialogues": len(results),
        "total_turns": total_turns,
        "checked_turns": total_checked,
        "passed_turns": total_passed,
        "overall_pass_rate": round(overall_pass_rate, 1),
        "total_time_seconds": round(total_time, 1),
        "category_stats": {k: {"checked": v["checked"], "passed": v["passed"], "pass_rate": round(v["passed"]/v["checked"]*100, 1) if v["checked"]>0 else 0} for k, v in category_stats.items()},
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {os.path.basename(output_file)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
