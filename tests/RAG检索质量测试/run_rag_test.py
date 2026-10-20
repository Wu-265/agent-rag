"""
RAG检索质量测试 - 执行脚本
两层测试：
  ① 召回层：直接 retriever_docs(query) 检索，看该命中的资料有没有命中（不调大模型，省token）
  ② 忠实层：直接 rag_summarize(query) 检索+总结，看基于检索资料的回答是否忠实准确（调大模型）
判据为人判定：人工阅读召回文档与忠实回答，判断召回是否准确、回答是否忠实不编造。
"""
import json
import os
import sys
import time
from datetime import datetime

# 项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from rag.rag_service import RagSummarizerService


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_cases_file = os.path.join(base_dir, "test_cases_rag.json")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(base_dir, f"rag_test_results_{timestamp}.json")

    print("=" * 70)
    print("🧪 RAG检索质量测试（召回层 + 忠实层）")
    print(f"📅 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    with open(test_cases_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    cases = config["cases"]
    print(f"📋 加载 {len(cases)} 条RAG测试用例")

    print("\n🤖 初始化 RAG 服务...")
    rag = RagSummarizerService()
    print("   RAG 服务初始化完成")

    results = []
    start_time = time.time()

    for case in cases:
        cid = case["id"]
        ctype = case["type"]
        query = case["query"]
        key_answer = case.get("key_answer", "")
        note = case.get("expected_note", "")

        print(f"\n[{cid}] {ctype}")
        print(f"   检索词: {query}")
        print(f"   预期关键答案: {key_answer[:60] if key_answer else '(无)'}")

        # ===== 召回层（不调大模型）=====
        recall_start = time.time()
        try:
            docs = rag.retriever_docs(query)
            recall_docs = []
            for i, doc in enumerate(docs):
                content = doc.page_content[:120]
                source = (doc.metadata or {}).get("source", "?")
                recall_docs.append({
                    "index": i,
                    "source": source,
                    "content_preview": content,
                })
                print(f"   召回[{i}] 来源:{source.split(chr(92))[-1]}")
                print(f"          内容: {content}...")
            # 判断是否命中关键答案（粗判断，供人工参考）
            hit = key_answer and any(
                any(word in d["content_preview"] for word in [key_answer[:10]])
                for d in recall_docs
            )
            # 更宽松：判断召回内容是否包含关键数字/词
            hit = False
            for d in recall_docs:
                for kw in ["3米", "300%", "4组", "保修", "避障", "充电座"]:
                    if kw in d["content_preview"]:
                        hit = True
                        break
                if hit:
                    break
            recall_crashed = False
            recall_err = ""
        except Exception as e:
            recall_crashed = True
            recall_err = str(e)[:200]
            recall_docs = []
            hit = False
            print(f"   ❌ 召回层崩溃: {recall_err}")
        recall_time = time.time() - recall_start
        print(f"   召回层: {'✅正常' if not recall_crashed else '❌崩溃'} | 疑似命中关键: {'✅是' if hit else '❓待判定'} | {recall_time:.1f}s")

        # ===== 忠实层（调大模型）=====
        if recall_crashed:
            # 召回崩了，忠实层也没意义（没检索到资料）
            faithful_answer = "(召回层异常，未执行忠实层)"
            faithful_crashed = True
            faithful_err = recall_err
            faithful_time = 0.0
        else:
            faithful_start = time.time()
            try:
                faithful_answer = rag.rag_summarize(query)
                faithful_crashed = False
                faithful_err = ""
            except Exception as e:
                faithful_crashed = True
                faithful_err = str(e)[:200]
                faithful_answer = ""
            faithful_time = time.time() - faithful_start
            print(f"   忠实层回答: {faithful_answer[:120] if faithful_answer else '(空)'}")
            print(f"   忠实层: {'✅正常' if not faithful_crashed else '❌崩溃'} | {faithful_time:.1f}s")

        results.append({
            "id": cid,
            "type": ctype,
            "query": query,
            "key_answer": key_answer,
            "expected_note": note,
            "recall": {
                "crashed": recall_crashed,
                "error_msg": recall_err,
                "docs": recall_docs,
                "suspected_hit": hit,
                "time_seconds": round(recall_time, 1),
            },
            "faithful": {
                "crashed": faithful_crashed,
                "error_msg": faithful_err,
                "answer": faithful_answer,
                "time_seconds": round(faithful_time, 1),
            },
        })

    end_time = time.time()

    crash_count = sum(1 for r in results if r["recall"]["crashed"] or r["faithful"]["crashed"])
    recall_hit = sum(1 for r in results if r["recall"]["suspected_hit"])

    print("\n" + "=" * 70)
    print("📊 RAG检索质量测试执行汇总")
    print("=" * 70)
    print(f"   总用例数: {len(results)}")
    print(f"   召回层疑似命中: {recall_hit}/{len(results)}")
    print(f"   崩溃数: {crash_count}")
    print(f"   总耗时: {end_time - start_time:.1f} 秒")
    print("\n   ⚠️ 注意：'疑似命中'仅为关键词粗判，请人工阅读召回文档与回答，判断召回准确率与回答忠实度。")

    output = {
        "test_name": config["test_name"],
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(results),
        "recall_suspected_hit": recall_hit,
        "crash_count": crash_count,
        "total_time_seconds": round(end_time - start_time, 1),
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 详细结果已保存到: {os.path.basename(output_file)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
