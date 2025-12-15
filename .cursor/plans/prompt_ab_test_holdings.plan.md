# Prompt A/B Test — Asian Income Fund Top Holdings (2025-01..2025-09)

## Goal / Non-negotiables
- **Goal**: Under a *fixed retrieval input* (same 30 chunks), find the best **system prompt × generator model** combo for answering:\n  “What are top holdings of Asian Income Fund from January to September 2025? (Asian Income Fund, Top holdings - equities, Top holdings - fix income, January 2025, …, September 2025)”.
- **Never break userspace**:\n  - Answer **strictly based on `{knowledge}`** (retrieved chunks only)\n  - **No cross-month mixing**: facts and citations must remain within the correct `report_month`\n  - **Citations must be verifiable**: include `file_name` + `report_month` + `section` + **verbatim quote**\n+- **This round scope**: optimize **answer stage only** (do not change retrieval strategy). We will *freeze retrieval once* then run prompt/model ablations.

## Fixed Retrieval (single source of truth)
- Use existing script: `[tools/retrieval_test_util.py](tools/retrieval_test_util.py)`
- Retrieval parameters (override defaults):\n  - `top_k = 30`\n  - `keyword_similarity_weight = 0.5`  ✅ (per your requirement)\n+- Output: save the returned chunks **verbatim** as the baseline `{knowledge}` input, e.g.\n  - `tools/prompt_ab_test_holdings/data/retrieval_top30_chunks.json`

## System Prompt Variants (ablation set)
1. **baseline_rag_chat_v2**\n   - Baseline: current `[rag_chat v2](rag_chat v2)` as-is
2. **v2_plus_bucket_covmap**\n   - v2 + hard constraints:\n     - Parse intent: fund=`Asian Income Fund`, months=`2025-01..2025-09`, sections=`Top holdings - equities` + `Top holdings - fixed income`\n     - **Hard filter + bucket** `{knowledge}` by `(report_month, section)`; ignore non-matching chunks\n     - Build **Coverage Map** (internal-only): for each month, whether equities/fixed-income chunks exist + file names\n     - Generate answer **strictly driven** by the bucket table; missing parts must be explicit and aggregated in Limitations\n     - Dedup only within same `(report_month, section)`\n     - Output order fixed: `2025-09 → … → 2025-01`
3. **v2_plus_bucket_compact**\n   - Same as v2_plus_bucket_covmap, but enforce compact output to prevent truncation:\n     - Each month: two small tables (equities/fixed income), max 5 rows each\n     - Minimal narrative; citations remain mandatory and bound per month+section

## Generator Models (parallel)
- `openai/gpt-5.2`\n- `anthropic/claude-sonnet-4.5`\n- `anthropic/claude-haiku-4.5`

## Judge / Scoring
- Judge model (OpenRouter): `deepseek/deepseek-reasoner` ✅
- Judge rubric (per answer):\n  - **Accuracy**: correct month/section holdings, no invented facts\n  - **Completeness**: covers 9 months × 2 sections; missing explicitly disclosed\n  - **Citation quality**: every month+section has verifiable reference (file_name/report_month/section/verbatim quote)\n  - **Structure**: fixed order and stable formatting\n  - **Hallucination penalty**: any unsupported statement triggers heavy penalty / fail flag
- Record latency:\n  - Retrieval latency (once)\n  - Generation latency (per combo)\n  - Judge latency (per combo)

## Project Output Layout (everything saved separately)
Create a dedicated directory under repo:\n- `tools/prompt_ab_test_holdings/`\n  - `prompts/` (system prompt variants, judge rubric prompt)\n  - `data/` (frozen retrieval chunks)\n  - `runs/` (raw model outputs + timing)\n  - `reports/` (summary tables / comparisons)\n  - `src/` (runner scripts)

## Connectivity First (no full run until this passes)
Before running the full 3×3 matrix, run a small connectivity/smoke phase:\n1. **RagFlow retrieval endpoint** reachable (1 retrieval call)\n2. **OpenRouter generator** reachable for each generator model (1 tiny completion each)\n3. **OpenRouter judge** reachable for DeepSeek (1 tiny completion)\nIf any fail, stop and report errors; do not proceed to the full batch.

## Minimal TDD (sanity, not ceremony)
Unit tests for:\n- `bucketize(chunks) -> bucket[month][section]`\n- `coverage_map(bucket)`\n- `validate_citations(answer)` (format-level checks)\nThis prevents the classic “special case explosion” (missing month/section, repeated chunks, etc.).

## Implementation Todos
- **T1-smoke-connectivity**: Add a small script to test retrieval + OpenRouter models + judge before batch.\n- **T2-freeze-retrieval**: Run retrieval once with `keyword_similarity_weight=0.5`, save top30 chunks JSON.\n- **T3-prompts**: Materialize 3 system prompt variants + judge rubric prompt into `tools/prompt_ab_test_holdings/prompts/`.\n- **T4-run-matrix**: Parallel run 3 prompts × 3 models; capture raw outputs + latency.\n- **T5-judge**: Score each output with DeepSeek; produce ranked summary + failure tags.\n- **T6-tests**: Add minimal unit tests around bucketing/coverage/citation checks.


