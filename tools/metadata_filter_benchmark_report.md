# Metadata Filter Benchmark Report

**Date:** 2025-12-11  
**Prompt Version:** v3.0  
**Total Questions:** 21

## Executive Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| Chat wins (better precision) | 5 | 24% |
| Tie (same result) | 9 | 43% |
| Chat N/A (no results) | 6 | 29% |
| Chat Error (ES nested) | 1 | 5% |

**Key Finding:** When metadata filter auto works correctly, it either matches or outperforms pure retrieval. Out of 14 successful queries, Chat wins 5 (36%) and ties 9 (64%).

---

## Detailed Results

| ID | Question | Retrieval #1 | Chat #1 | Winner |
|----|----------|--------------|---------|--------|
| Q1 | management fee for High Dividend | Fee structure | Fee structure | TIE |
| Q2 | performance fees for High Dividend | Fee structure | Fee structure | TIE |
| Q3 | performance fee for High Dividend | Fee structure | Fee structure | TIE |
| Q4 | performance fee rate for High Dividend | Fee structure | Fee structure | TIE |
| **Q5** | **top fixed income holdings Asian Income Sep 2025** | Credit ratings | **Top holdings fixed income** | **CHAT ✅** |
| Q6 | top equity holdings Asian Income Mar 2025 | Top holdings equities | Top holdings equities | TIE |
| Q7 | top holdings High Dividend Jan-Jul 2025 | Top holdings equities | ERROR | ES ERROR |
| Q8 | geographic exposures Asian Income | Investment objective | N/A | N/A |
| Q9 | geographic locations High Dividend Jan-Jul 2025 | Credit ratings | N/A | N/A |
| Q10 | top holdings Asian Income Jan-Sep 2025 | Credit ratings | N/A | N/A |
| **Q11** | **return for High Dividend Sep 2025** | Credit ratings | **Monthly performance** | **CHAT ✅** |
| TC001 | top holdings Asian Income Jan-Sep 2025 | Credit ratings | N/A | N/A |
| TC002 | 比较两基金股息率 Aug 2025 | Credit ratings | N/A | N/A |
| **TC003** | **asset allocation by sector Asian Income Sep 2025** | Credit ratings | **Asset type by sector** | **CHAT ✅** |
| TC004 | credit rating distribution Asian Income | Credit ratings | Credit ratings | TIE |
| **TC005** | **亚洲收益基金 Q1 业绩** | Credit ratings | **Monthly performance** | **CHAT ✅** |
| TC006 | NAV codes Asian Income Class A | NAVs & codes | NAVs & codes | TIE |
| TC007 | Compare fee structures two funds | Credit ratings | N/A | N/A |
| **TC008** | **Portfolio characteristics Asian Income May-Aug 2025** | Investment objective | **Portfolio characteristics** | **CHAT ✅** |
| TC009 | 哪些月份持有台积电 | Top holdings equities | Top holdings equities | TIE |
| TC010 | investment objective Asian Income | Investment objective | Investment objective | TIE |

---

## Analysis

### Chat Wins (5 cases) - Metadata Filter Significantly Better

1. **Q5** (fixed income holdings): Pure retrieval returns "Credit ratings" (wrong), Chat returns "Top holdings fixed income" (correct)
2. **Q11** (fund return): Pure retrieval returns "Credit ratings" (wrong), Chat returns "Monthly performance" (correct)
3. **TC003** (sector allocation): Pure retrieval returns "Credit ratings" (wrong), Chat returns "Asset type by sector" (correct)
4. **TC005** (Q1 performance): Pure retrieval returns "Credit ratings" (wrong), Chat returns "Monthly performance" (correct)
5. **TC008** (portfolio characteristics): Pure retrieval returns "Investment objective" (wrong), Chat returns "Portfolio characteristics" (correct)

**Pattern:** Metadata filter auto precisely matches `section_type` field, avoiding irrelevant high-similarity chunks like "Credit ratings".

### Chat N/A Cases (6 cases) - Metadata Filter Too Strict

| ID | Issue |
|----|-------|
| Q8 | Single fund, no time range - metadata filter may be too narrow |
| Q9 | Time range (Jan-Jul) - possible ES query limit |
| Q10 | Long time range (Jan-Sep) - 9 months too complex |
| TC001 | Long time range (Jan-Sep) - same as Q10 |
| TC002 | Multi-fund comparison - metadata filter can't match both |
| TC007 | Multi-fund comparison - same as TC002 |

**Root Cause Analysis:**
- Long time ranges (7-9 months) may still hit ES nested clause limits
- Multi-fund comparisons don't work well with metadata filter (can only match one fund at a time)

### ES Error (1 case)

- **Q7**: "January 2025 to July 2025" (7 months) still triggers `search_phase_execution_exception`

---

## Recommendations

### 1. For Single-Month Queries
✅ Metadata filter auto is highly effective - use it.

### 2. For Multi-Month Time Ranges
⚠️ Current v3.0 prompt still has issues with 7+ month ranges. Consider:
- Further simplify: use "2025" instead of listing all months
- Or disable metadata filter for time range queries

### 3. For Multi-Fund Comparisons
❌ Metadata filter doesn't work well. Consider:
- Run separate queries for each fund
- Or disable metadata filter for comparison queries

### 4. Query Enhancement Prompt v3.1 Suggestions
```
# For very long time ranges (5+ months), use year only:
- "从1月到9月" → 2025 (instead of listing 9 months)

# For multi-fund comparisons, add special handling:
- "Compare Fund A and Fund B" → Run two separate queries
```

---

## Files Generated

- `tools/prompts/query_enhancement_v3.0.txt` - Updated prompt with simplified date format
- `tools/metadata_filter_benchmark.py` - Benchmark script
- `tools/metadata_filter_benchmark_results.json` - Raw test results
- `tools/metadata_filter_benchmark_report.md` - This report


