"""
记忆极限测试（多组独立测试版）
验证 agent 的多轮记忆窗口是否生效，以及实际能记住多少轮对话。
方法：多组独立测试，每组 history 从头开始，避免"刷新效应"。
每组结构：埋密码 + N轮无关对话 + 最后一轮问密码。
"""
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.react_agent import ReactAgent


def load_test_config(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_memory(answer: str, secret_keywords: list) -> tuple:
    """检查回答中是否包含密码关键词，包含任意一个就算记住了。"""
    matched = []
    for kw in secret_keywords:
        if kw in answer:
            matched.append(kw)
    if matched:
        return True, f"记住了！匹配到关键词: {matched}"
    return False, "没记住，回答中未包含任何密码关键词"


def run_single_group(agent: ReactAgent, group: dict, secret_keywords: list) -> dict:
    """运行一组独立的记忆极限测试。"""
    group_id = group["group_id"]
    description = group["description"]
    embed_query = group["embed_turn"]["query"]
    distract_queries = [t["query"] for t in group["distract_turns"]]
    test_query = group["test_turn"]["query"]

    print(f"\n{'='*60}")
    print(f"  测试组 {group_id}: {description}")
    print(f"{'='*60}")

    history = []  # 每组独立，从头开始
    all_turns = []

    # 第1轮：埋密码
    print(f"\n  [第1轮] 📌 埋藏信息: {embed_query}")
    answer, tool_calls = agent.execute_with_trace(embed_query, history=history)
    history.append({"role": "user", "content": embed_query})
    history.append({"role": "assistant", "content": answer})
    print(f"       回答预览: {answer[:60]}...")
    all_turns.append({"turn": 1, "type": "embed", "query": embed_query, "answer": answer})

    # 中间轮：无关对话
    for i, dq in enumerate(distract_queries, 2):
        print(f"\n  [第{i}轮] 🔀 干扰对话: {dq}")
        answer, tool_calls = agent.execute_with_trace(dq, history=history)
        history.append({"role": "user", "content": dq})
        history.append({"role": "assistant", "content": answer})
        print(f"       回答预览: {answer[:60]}...")
        if tool_calls:
            print(f"       调用工具: {[c['tool'] for c in tool_calls]}")
        all_turns.append({"turn": i, "type": "distract", "query": dq, "answer": answer})

    # 最后一轮：测试记忆
    test_turn_num = len(distract_queries) + 2
    history_msg_count = len(history)
    print(f"\n  [第{test_turn_num}轮] 🧪 测试记忆: {test_query}")
    print(f"       当前历史消息数: {history_msg_count} 条（约 {history_msg_count//2} 轮完整对话）")
    answer, tool_calls = agent.execute_with_trace(test_query, history=history)
    history.append({"role": "user", "content": test_query})
    history.append({"role": "assistant", "content": answer})

    remembered, reason = check_memory(answer, secret_keywords)
    print(f"       记忆检查: {'✅ ' + reason if remembered else '❌ ' + reason}")
    print(f"       回答预览: {answer[:80]}...")
    all_turns.append({"turn": test_turn_num, "type": "test", "query": test_query, "answer": answer})

    return {
        "group_id": group_id,
        "description": description,
        "distract_count": len(distract_queries),
        "history_msg_count_at_test": history_msg_count,
        "full_dialogue_rounds": history_msg_count // 2,
        "remembered": remembered,
        "reason": reason,
        "test_answer": answer,
        "all_turns": all_turns,
    }


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cases_memory_limit.json")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"memory_limit_test_results_{timestamp}.json")

    print("=" * 70)
    print("🧠 记忆极限测试（多组独立测试版）")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 加载测试配置
    print(f"\n📋 加载测试配置: {os.path.basename(test_config_file)}")
    config = load_test_config(test_config_file)
    secret_keywords = config["secret_keywords"]
    memory_window = config.get("memory_window_config", 12)
    test_groups = config["test_groups"]
    print(f"   密码关键词: {secret_keywords}")
    print(f"   配置的记忆窗口: {memory_window} 条消息（约 {memory_window // 2} 轮完整对话）")
    print(f"   测试组数: {len(test_groups)}")

    # 初始化 agent
    print("\n🤖 初始化 Agent...")
    agent = ReactAgent()
    print("   Agent 初始化完成")

    # 逐组运行
    print(f"\n🚀 开始测试...")
    start_time = time.time()

    group_results = []
    for group in test_groups:
        result = run_single_group(agent, group, secret_keywords)
        group_results.append(result)

    end_time = time.time()
    total_time = end_time - start_time

    # 分析结果
    print("\n" + "=" * 70)
    print("📊 记忆极限测试结果汇总")
    print("=" * 70)

    print(f"\n  配置的记忆窗口: {memory_window} 条消息（约 {memory_window // 2} 轮完整对话）")
    print(f"  测试组数: {len(group_results)}")
    print(f"  总耗时: {total_time:.1f} 秒")

    print("\n  🧪 各组测试结果:")
    print(f"  {'组':<6} {'干扰轮数':<10} {'历史消息数':<12} {'完整对话轮数':<14} {'是否记住':<10}")
    print("  " + "-" * 55)

    for r in group_results:
        status = "✅ 记住" if r["remembered"] else "❌ 没记住"
        print(f"  {r['group_id']:<6} {r['distract_count']:<10} {r['history_msg_count_at_test']:<12} {r['full_dialogue_rounds']:<14} {status}")

    # 临界点分析
    print("\n  📈 记忆临界点分析:")
    last_remembered = None
    first_forgot = None
    for r in group_results:
        if r["remembered"]:
            last_remembered = r
        elif not r["remembered"] and first_forgot is None:
            first_forgot = r

    if last_remembered:
        print(f"  最后一次记住: 组{last_remembered['group_id']}（{last_remembered['distract_count']}轮干扰，历史{last_remembered['history_msg_count_at_test']}条消息，约{last_remembered['full_dialogue_rounds']}轮完整对话）")
    if first_forgot:
        print(f"  第一次遗忘: 组{first_forgot['group_id']}（{first_forgot['distract_count']}轮干扰，历史{first_forgot['history_msg_count_at_test']}条消息，约{first_forgot['full_dialogue_rounds']}轮完整对话）")

    if last_remembered and first_forgot:
        print(f"  记忆临界点: 约 {last_remembered['full_dialogue_rounds']}~{first_forgot['full_dialogue_rounds']} 轮完整对话")
        # 检查是否与配置一致
        expected_boundary = memory_window // 2  # 理论上约6轮
        if last_remembered['full_dialogue_rounds'] <= expected_boundary < first_forgot['full_dialogue_rounds']:
            print(f"  与配置值({expected_boundary}轮)对比: ✅ 一致，MEMORY_WINDOW={memory_window} 生效正常")
        else:
            print(f"  与配置值({expected_boundary}轮)对比: ⚠️  有差异，建议检查 MEMORY_WINDOW 配置或模型行为")

    # 保存结果
    output = {
        "test_name": "记忆极限测试（多组独立测试版）",
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "memory_window_config": memory_window,
        "secret_keywords": secret_keywords,
        "test_groups_count": len(group_results),
        "total_time_seconds": round(total_time, 1),
        "last_remembered_group": last_remembered["group_id"] if last_remembered else None,
        "first_forgot_group": first_forgot["group_id"] if first_forgot else None,
        "group_results": group_results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {os.path.basename(output_file)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
