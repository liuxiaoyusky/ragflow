#!/usr/bin/env python3
"""
Run 21-question evaluation against a RagFlow Chat assistant (next-chat) using:
1) Query enhancement v3.1 prompt (OpenRouter Claude Haiku 4.5)
2) RagFlow /api/v1/chats/{chat_id}/completions (stream=false)
3) LLM judge scoring (OpenRouter Claude Sonnet 4.5) - ragflow-only rubric

Outputs:
- tools/next_chat_eval_v3_1/results/run_<ts>/raw/*.json  (raw completions)
- tools/next_chat_eval_v3_1/results/run_<ts>/eval_results.json
- tools/next_chat_eval_v3_1/results/run_<ts>/summary_table.txt

Debug logging:
- Appends NDJSON to /home/calvin/github/ragflow/.cursor/debug.log
  NOTE: This file may be protected from automated deletion; use runId to distinguish runs.

SECURITY: Never log API keys. Never log full prompts; only lengths and fingerprints.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import urllib3
import yaml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOG_PATH = Path("/home/calvin/github/ragflow/.cursor/debug.log")


def ndlog(*, run_id: str, hypothesis_id: str, location: str, message: str, data: dict):
    payload = {
        "id": f"log_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}",
        "timestamp": int(time.time() * 1000),
        "sessionId": "debug-session",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class RagflowCfg:
    base_url: str
    api_key: str
    dataset_id: str


@dataclass(frozen=True)
class OpenRouterCfg:
    api_key: str
    base_url: str
    model_enhance: str
    model_judge: str


def load_ragflow_cfg() -> RagflowCfg:
    cfg = yaml.safe_load(Path("ragflow_config.yaml").read_text())
    return RagflowCfg(
        base_url=str(cfg["base_url"]).rstrip("/"),
        api_key=str(cfg["api_key"]),
        dataset_id=str(cfg["dataset_id"]),
    )


def load_openrouter_cfg() -> OpenRouterCfg:
    # openai.apikey layout (repo convention):
    # line1: key, line2: base_url, line3: default model, etc.
    lines = Path("openai.apikey").read_text().splitlines()
    api_key = (lines[0] or "").strip()
    base_url = (lines[1] if len(lines) > 1 else "https://openrouter.ai/api/v1").strip()
    # Hard-pin models used in your prompt file header
    return OpenRouterCfg(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model_enhance="anthropic/claude-haiku-4.5",
        model_judge="anthropic/claude-sonnet-4.5",
    )


def http_post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int = 120) -> dict:
    r = requests.post(url, headers=headers, json=body, verify=False, timeout=timeout)
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Non-JSON response {r.status_code}: {r.text[:500]}") from e


def http_get_json(url: str, headers: dict[str, str], timeout: int = 60) -> dict:
    r = requests.get(url, headers=headers, verify=False, timeout=timeout)
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Non-JSON response {r.status_code}: {r.text[:500]}") from e


def load_questions_21() -> list[dict[str, Any]]:
    """
    Canonical 21-question set:
    - Q1-Q11: from tools/optimized_comparison_results.json (keeps current regression set)
    - TC001-TC010: from docs/benchmark/rag_evaluation_dataset.json
    """
    out: list[dict[str, Any]] = []

    # Q1-Q11
    opt = json.loads(Path("tools/optimized_comparison_results.json").read_text(encoding="utf-8"))
    for r in opt.get("results", []):
        qid = r.get("id")
        q = r.get("question")
        if not qid or not q:
            continue
        out.append({"id": qid, "question": q, "category": "regression_q"})

    # TC001-TC010
    bench = json.loads(Path("docs/benchmark/rag_evaluation_dataset.json").read_text(encoding="utf-8"))
    for tc in bench.get("test_cases", []):
        tid = tc.get("id")
        q = tc.get("question")
        if not tid or not q:
            continue
        out.append(
            {
                "id": tid,
                "question": q,
                "category": tc.get("category", "benchmark"),
                "expected_answer": tc.get("expected_answer", ""),
            }
        )

    # Stable ordering: Q1..Q11 then TC001..TC010
    def sort_key(x: dict[str, Any]):
        i = x["id"]
        if i.startswith("Q"):
            try:
                return (0, int(i[1:]))
            except Exception:
                return (0, 999)
        if i.startswith("TC"):
            try:
                return (1, int(i[2:]))
            except Exception:
                return (1, 999)
        return (2, 999)

    out.sort(key=sort_key)
    assert len(out) == 21, f"Expected 21 questions, got {len(out)}"
    return out


def render_query_enhancement_prompt(template_txt: str, *, current_date: str, latest_month: str, original_question: str) -> str:
    # Minimal templating (avoid extra deps)
    return (
        template_txt.replace("${currentDate}", current_date)
        .replace("${latestDataMonth}", latest_month)
        .replace("${originalQuestion}", original_question)
    )


def enhance_query_v3_1(or_cfg: OpenRouterCfg, template_txt: str, question: str) -> tuple[str, float]:
    current_date = datetime.now().strftime("%Y-%m-%d")
    latest_month = "September 2025"
    prompt = render_query_enhancement_prompt(
        template_txt,
        current_date=current_date,
        latest_month=latest_month,
        original_question=question,
    )
    url = f"{or_cfg.base_url}/chat/completions"
    payload = {
        "model": or_cfg.model_enhance,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0,
    }
    t0 = time.time()
    last_err = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {or_cfg.api_key}",
                    "Content-Type": "application/json",
                    "Connection": "close",
                },
                json=payload,
                timeout=90,
            )
            dt = time.time() - t0
            if resp.status_code != 200:
                last_err = f"http_{resp.status_code}"
                if resp.status_code >= 500 or resp.status_code == 429:
                    time.sleep(min(2 * attempt, 10))
                    continue
                return question, dt
            enhanced = resp.json()["choices"][0]["message"]["content"].strip()
            return enhanced, dt
        except requests.exceptions.ChunkedEncodingError as e:
            last_err = f"chunked_encoding_error:{str(e)[:120]}"
        except requests.exceptions.Timeout as e:
            last_err = f"timeout:{str(e)[:120]}"
        except Exception as e:
            last_err = f"exception:{str(e)[:120]}"
        time.sleep(min(2 * attempt, 10))
    dt = time.time() - t0
    _ = last_err  # keep for potential future logging
    return question, dt


def create_session(rf: RagflowCfg, chat_id: str, name: str) -> str:
    url = f"{rf.base_url}/api/v1/chats/{chat_id}/sessions"
    obj = http_post_json(url, headers={"Authorization": f"Bearer {rf.api_key}"}, body={"name": name}, timeout=60)
    if obj.get("code") != 0:
        raise RuntimeError(f"create_session failed: {obj}")
    return obj["data"]["id"]


def rag_completion(rf: RagflowCfg, chat_id: str, session_id: str, question: str) -> tuple[dict, float]:
    url = f"{rf.base_url}/api/v1/chats/{chat_id}/completions"
    t0 = time.time()
    obj = http_post_json(
        url,
        headers={"Authorization": f"Bearer {rf.api_key}", "Content-Type": "application/json"},
        body={"session_id": session_id, "question": question, "stream": False},
        timeout=600,
    )
    dt = time.time() - t0
    return obj, dt


JUDGE_PROMPT_RAGFLOW_ONLY = """You are an impartial judge evaluating ONE RAG system answer about fund factsheets.

## Question
{question}

## Expected Answer (may be partial / high-level)
{expected_answer}

## RagFlow Answer
{ragflow_answer}

## Evaluation Criteria
Rate the answer on a scale of 1-10 for each criterion:
1. Accuracy (1-10): factually correct, no hallucinations
2. Completeness (1-10): fully answers the question and covers required parts
3. Structure (1-10): well-organized, easy to read
4. Citation (1-10): cites sources properly (IDs/files) where appropriate
5. Professionalism (1-10): precise, client-ready

## Output Format (JSON only)
{{
  "accuracy": <score>,
  "completeness": <score>,
  "structure": <score>,
  "citation": <score>,
  "professionalism": <score>,
  "total": <sum>,
  "analysis": "<one paragraph explaining the scoring>"
}}"""


def judge_answer(or_cfg: OpenRouterCfg, *, question: str, expected_answer: str, ragflow_answer: str) -> tuple[dict, float]:
    # Keep prompt bounded
    prompt = JUDGE_PROMPT_RAGFLOW_ONLY.format(
        question=question,
        expected_answer=(expected_answer or "")[:1200],
        ragflow_answer=(ragflow_answer or "")[:3500],
    )
    url = f"{or_cfg.base_url}/chat/completions"
    payload = {"model": or_cfg.model_judge, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800, "temperature": 0.1}
    t0 = time.time()
    last_err = None
    content = None
    for attempt in range(1, 6):
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {or_cfg.api_key}",
                    "Content-Type": "application/json",
                    "Connection": "close",
                },
                json=payload,
                timeout=120,
            )
            dt = time.time() - t0
            if resp.status_code != 200:
                last_err = f"http_{resp.status_code}"
                if resp.status_code >= 500 or resp.status_code == 429:
                    time.sleep(min(2 * attempt, 10))
                    continue
                return {"error": f"judge_http_{resp.status_code}", "raw": resp.text[:300]}, dt
            content = resp.json()["choices"][0]["message"]["content"]
            break
        except requests.exceptions.ChunkedEncodingError as e:
            last_err = f"chunked_encoding_error:{str(e)[:120]}"
        except requests.exceptions.Timeout as e:
            last_err = f"timeout:{str(e)[:120]}"
        except Exception as e:
            last_err = f"exception:{str(e)[:120]}"
        time.sleep(min(2 * attempt, 10))
    else:
        dt = time.time() - t0
        return {"error": "judge_retry_exhausted", "raw": (last_err or "")[:300]}, dt

    assert content is not None
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= start:
        return {"error": "judge_no_json", "raw": content[:300]}, dt
    try:
        obj = json.loads(content[start:end])
    except Exception:
        return {"error": "judge_bad_json", "raw": content[:300]}, dt
    return obj, dt


def doc_type_counts(doc_names: list[str]) -> dict[str, int]:
    keys = ["Top_holdings", "Credit_ratings", "Investment_objective", "Monthly_performance", "Fee_structure", "Dividend_information", "NAVs_&_codes"]
    out = {k: 0 for k in keys}
    for d in doc_names:
        for k in keys:
            if k in d:
                out[k] += 1
    out["other"] = max(0, len(doc_names) - sum(out.values()))
    return out


def main():
    # Allow resuming an existing run directory by setting RUN_ID
    run_id = os.environ.get("RUN_ID") or datetime.now().strftime("eval21_%Y%m%d_%H%M%S")
    rf = load_ragflow_cfg()
    or_cfg = load_openrouter_cfg()

    # Target chat assistant: the one you provided (no_cross_languages version)
    chat_id = os.environ.get("RAGFLOW_CHAT_ID", "262db9f4d73411f0a4630242ac130006")
    max_workers = int(os.environ.get("MAX_WORKERS", "4"))

    # Load enhancement template file
    enh_template = Path("tools/prompts/query_enhancement_v3.1.txt").read_text(encoding="utf-8")

    questions = load_questions_21()

    out_root = Path("tools/next_chat_eval_v3_1/results") / f"run_{run_id}"
    (out_root / "raw").mkdir(parents=True, exist_ok=True)
    (out_root / "judged").mkdir(parents=True, exist_ok=True)

    # Log run start (no secrets)
    ndlog(
        run_id=run_id,
        hypothesis_id="H0",
        location="run_eval_21_next_chat.py:main",
        message="run_start",
        data={
            "chat_id": chat_id,
            "questions": [q["id"] for q in questions],
            "models": {"enhance": or_cfg.model_enhance, "judge": or_cfg.model_judge},
            "max_workers": max_workers,
        },
    )

    results: list[dict[str, Any]] = []
    total_score = 0
    total_time = 0.0

    def process_one(item: dict[str, Any]) -> dict[str, Any]:
        qid = item["id"]
        q = item["question"]
        expected = item.get("expected_answer", "")

        judged_path = out_root / "judged" / f"{qid}.json"
        raw_path = out_root / "raw" / f"{qid}.json"

        if judged_path.exists() and raw_path.exists():
            saved = json.loads(judged_path.read_text(encoding="utf-8"))
            return saved

        # Each question gets an isolated session to avoid cross-talk and to allow safe parallelism
        session_id = create_session(rf, chat_id, name=f"eval21_{run_id}_{qid}")

        # Enhance
        enhanced, t_enh = enhance_query_v3_1(or_cfg, enh_template, q)
        ndlog(
            run_id=run_id,
            hypothesis_id="H1",
            location="run_eval_21_next_chat.py:enhance_query_v3_1",
            message="enhanced",
            data={"id": qid, "enhance_s": round(t_enh, 2), "orig_len": len(q), "enhanced_len": len(enhanced)},
        )

        # Completion
        comp, t_chat = rag_completion(rf, chat_id, session_id, enhanced)
        raw_path.write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8")

        data = comp.get("data", {}) if isinstance(comp, dict) else {}
        answer = data.get("answer", "") if isinstance(data, dict) else ""
        reference = data.get("reference", {}) if isinstance(data, dict) else {}
        chunks = reference.get("chunks", []) if isinstance(reference, dict) else []
        doc_names = [c.get("document_name") or "" for c in chunks if isinstance(c, dict)]

        ndlog(
            run_id=run_id,
            hypothesis_id="H2",
            location="run_eval_21_next_chat.py:rag_completion",
            message="completion",
            data={
                "id": qid,
                "chat_s": round(t_chat, 2),
                "answer_len": len(answer or ""),
                "ref_chunks": len(doc_names),
                "ref_doc_type_counts": doc_type_counts(doc_names),
            },
        )

        # Judge
        judge, t_judge = judge_answer(or_cfg, question=q, expected_answer=expected, ragflow_answer=answer)
        ndlog(
            run_id=run_id,
            hypothesis_id="H3",
            location="run_eval_21_next_chat.py:judge_answer",
            message="judged",
            data={
                "id": qid,
                "judge_s": round(t_judge, 2),
                "judge_error": judge.get("error") if isinstance(judge, dict) else None,
                "total": judge.get("total") if isinstance(judge, dict) else None,
            },
        )

        out = {
            "id": qid,
            "question": q,
            "enhanced_question": enhanced,
            "enhance_time": t_enh,
            "ragflow_time": t_chat,
            "total_time": t_enh + t_chat + t_judge,
            "ragflow_answer": answer,
            "ragflow_reference": {"chunks": chunks},
            "judge": judge,
            "judge_time": t_judge,
            "raw_path": str(raw_path),
        }
        judged_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    # Parallel execution across questions
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(process_one, item): item["id"] for item in questions}
        for fut in as_completed(futs):
            qid = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                # Record failure but keep the run going
                ndlog(
                    run_id=run_id,
                    hypothesis_id="H9",
                    location="run_eval_21_next_chat.py:process_one",
                    message="question_failed",
                    data={"id": qid, "error": str(e)[:200]},
                )
                res = {
                    "id": qid,
                    "question": next((x["question"] for x in questions if x["id"] == qid), ""),
                    "error": str(e),
                    "judge": {"error": "pipeline_failed"},
                    "total_time": 0.0,
                    "ragflow_answer": "",
                    "ragflow_reference": {"chunks": []},
                    "raw_path": "",
                }
            results.append(res)

    # Deterministic ordering for output
    def _sort_key(r: dict[str, Any]):
        i = r.get("id", "")
        if i.startswith("Q"):
            try:
                return (0, int(i[1:]))
            except Exception:
                return (0, 999)
        if i.startswith("TC"):
            try:
                return (1, int(i[2:]))
            except Exception:
                return (1, 999)
        return (2, 999)

    results.sort(key=_sort_key)
    for r in results:
        judge = r.get("judge", {}) if isinstance(r.get("judge"), dict) else {}
        if isinstance(judge.get("total"), (int, float)):
            total_score += int(judge["total"])
        if isinstance(r.get("enhance_time"), (int, float)) and isinstance(r.get("ragflow_time"), (int, float)):
            total_time += float(r.get("enhance_time", 0.0)) + float(r.get("ragflow_time", 0.0))

    summary = {
        "timestamp": datetime.now().isoformat(),
        "run_id": run_id,
        "chat_id": chat_id,
        "evaluation_type": "next_chat_eval_v3.1_ragflow_only",
        "models": {"enhance": or_cfg.model_enhance, "judge": or_cfg.model_judge},
        "summary": {
            "total_questions": len(results),
            "total_score": total_score,
            "avg_score": round(total_score / max(1, len(results)), 2),
            "avg_total_time": round(total_time / max(1, len(results)), 2),
        },
        "results": results,
    }

    (out_root / "eval_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Text summary table
    lines = []
    lines.append(f"run_id: {run_id}")
    lines.append(f"chat_id: {chat_id}")
    lines.append(f"total_questions: {len(results)}")
    lines.append(f"avg_score: {summary['summary']['avg_score']}")
    lines.append("")
    lines.append(f"{'ID':<6} {'Score':<6} {'Time(s)':<8} {'AnswerLen':<10} {'TopHoldingsRef':<14} {'CreditRatingsRef':<15}")
    lines.append("-" * 70)
    for r in results:
        judge = r.get("judge", {}) if isinstance(r.get("judge"), dict) else {}
        score = judge.get("total", 0) if isinstance(judge.get("total"), (int, float)) else 0
        tt = r.get("total_time", 0.0)
        ans_len = len(r.get("ragflow_answer", "") or "")
        chunks = ((r.get("ragflow_reference") or {}).get("chunks") or []) if isinstance(r.get("ragflow_reference"), dict) else []
        doc_names = [c.get("document_name") or "" for c in chunks if isinstance(c, dict)]
        th = sum(1 for d in doc_names if "Top_holdings" in d)
        cr = sum(1 for d in doc_names if "Credit_ratings" in d)
        lines.append(f"{r['id']:<6} {int(score):<6} {tt:<8.2f} {ans_len:<10} {th:<14} {cr:<15}")
    (out_root / "summary_table.txt").write_text("\n".join(lines), encoding="utf-8")

    ndlog(
        run_id=run_id,
        hypothesis_id="H0",
        location="run_eval_21_next_chat.py:main",
        message="run_end",
        data={"out_dir": str(out_root), "total_score": total_score, "avg_score": summary["summary"]["avg_score"]},
    )

    print(f"OK: wrote {out_root/'eval_results.json'}")
    print(f"OK: wrote {out_root/'summary_table.txt'}")


if __name__ == "__main__":
    main()


