"""
边界与异常测试 - B类(文件边界) 执行脚本
职责：用异常文件直接调用 analyze_file 函数（不调大模型，省token、快），记录返回结果。
判据为人判定：人工阅读每条返回，判断是否优雅兜底、不崩溃、正确识别异常。
"""
import json
import os
import sys
import time
from datetime import datetime

# 项目根目录加入路径（脚本在 tests/边界异常测试/，往上跳2级）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent.tools.file_tools import analyze_file


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_cases_file = os.path.join(base_dir, "test_cases_edge_file.json")
    test_files_dir = os.path.join(base_dir, "test_files")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(base_dir, f"edge_file_test_results_{timestamp}.json")

    print("=" * 70)
    print("🧪 边界与异常测试 - B类(文件边界)")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    with open(test_cases_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    cases = config["cases"]
    print(f"📋 加载 {len(cases)} 条文件边界测试用例")

    results = []
    start_time = time.time()

    for case in cases:
        cid = case["id"]
        ctype = case["type"]
        fname = case["file"]
        note = case.get("expected_note", "")
        skip = case.get("skip", False)

        if skip:
            print(f"\n[{cid}] {ctype} - {fname}")
            print(f"   ⏭️ 跳过执行: {case.get('skip_reason', '已标注跳过')}")
            results.append({
                "id": cid,
                "type": ctype,
                "file": fname,
                "expected_note": note,
                "skipped": True,
                "skip_reason": case.get("skip_reason", ""),
                "crashed": False,
                "error_msg": "",
                "result": "(已跳过)",
            })
            continue

        print(f"\n[{cid}] {ctype} - {fname}")

        # 构造绝对路径（不存在的文件也传，测容错）
        file_path = os.path.join(test_files_dir, fname)

        crashed = False
        error_msg = ""
        result = ""

        try:
            result = analyze_file.invoke({"file_path": file_path})
        except Exception as e:
            crashed = True
            error_msg = str(e)[:200]

        print(f"   是否崩溃: {'❌ 崩溃!' if crashed else '✅ 正常执行'}")
        if crashed:
            print(f"   错误: {error_msg}")
        else:
            print(f"   返回预览: {result[:120] if result else '(空)'}")

        results.append({
            "id": cid,
            "type": ctype,
            "file": fname,
            "expected_note": note,
            "crashed": crashed,
            "error_msg": error_msg,
            "result": result,
        })

    end_time = time.time()
    total_time = end_time - start_time

    crash_count = sum(1 for r in results if r["crashed"])
    skip_count = sum(1 for r in results if r.get("skipped"))
    normal_count = len(results) - crash_count - skip_count

    print("\n" + "=" * 70)
    print("📊 文件边界测试执行汇总")
    print("=" * 70)
    print(f"   总用例数: {len(results)}")
    print(f"   正常执行: {normal_count}")
    print(f"   跳过: {skip_count}")
    print(f"   崩溃数: {crash_count}")
    print(f"   总耗时: {total_time:.1f} 秒")
    print("\n   ⚠️ 注意：本测试不自动判定对错，请人工阅读每条返回，判断是否优雅兜底、正确识别异常文件。")

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
