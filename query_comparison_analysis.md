# Query Comparison Analysis

## 测试时间
2025-12-10

## 测试目的
对比两种查询方式下，"想要的chunk"（Top holdings）和"不想要的chunk"（其他类型）之间的分数差距。

---

## 查询1: 带括号展开版本

### Curl请求
```bash
curl -s -k -X POST \
  -H "Authorization: Bearer ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are top holdings of Asian Income Fund from January to September 2025 (months: January 2025, February 2025, March 2025, April 2025, May 2025, June 2025, July 2025, August 2025, September 2025)",
    "dataset_ids": ["fbc7fb98d4b311f084b30242ac130006"],
    "top_n": 30,
    "metadata_condition": {
      "logic": "and",
      "conditions": [
        {"name": "fund_name", "comparison_operator": "=", "value": "Asian Income Fund"}
      ]
    }
  }' \
  "https://10.1.9.133:8443/api/v1/retrieval"
```

### 查询问题
```
What are top holdings of Asian Income Fund from January to September 2025 (months: January 2025, February 2025, March 2025, April 2025, May 2025, June 2025, July 2025, August 2025, September 2025)
```

### 返回结果统计

#### Top holdings - equities 覆盖
- ✅ January 2025: Rank 4, Score=0.5809
- ✅ February 2025: Rank 14, Score=0.5692
- ❌ March 2025: NOT IN TOP 30
- ✅ April 2025: Rank 16, Score=0.5688
- ❌ May 2025: NOT IN TOP 30
- ✅ June 2025: Rank 13, Score=0.5701
- ✅ July 2025: Rank 19, Score=0.5675
- ✅ August 2025: Rank 10, Score=0.5735
- ✅ September 2025: Rank 8, Score=0.5776
- **覆盖: 7/9**

#### Top holdings - fixed income 覆盖
- ✅ January 2025: Rank 1, Score=0.5913
- ✅ February 2025: Rank 5, Score=0.5809
- ❌ March 2025: NOT IN TOP 30
- ✅ April 2025: Rank 3, Score=0.5819
- ❌ May 2025: NOT IN TOP 30
- ✅ June 2025: Rank 6, Score=0.5803
- ✅ July 2025: Rank 17, Score=0.5687
- ✅ August 2025: Rank 12, Score=0.5705
- ✅ September 2025: Rank 2, Score=0.5830
- **覆盖: 7/9**

#### 其他类型chunks (Top 5)
- Rank 7: VP_Asian_Income_Fund_2025Jan_Investment_objective.md, Score=0.5783
- Rank 9: VP_Asian_Income_Fund_2025Jan_Monthly_performance.md, Score=0.5736
- Rank 11: VP_Asian_Income_Fund_2025Sep_Investment_objective.md, Score=0.5734
- Rank 15: VP_Asian_Income_Fund_2025Sep_Monthly_performance.md, Score=0.5691
- Rank 20: VP_Asian_Income_Fund_2025Jan_Performance_update.md, Score=0.5620

**其他类型chunks总数: 15**

---

## 查询2: 原始版本（不带括号）

### Curl请求
```bash
curl -s -k -X POST \
  -H "Authorization: Bearer ragflow-NB-Mo_q3z2SaAgPl_Bn9t6lgysmj6cj-WPWEdUV-7Iw" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are top holdings of Asian Income Fund from January to September 2025",
    "dataset_ids": ["fbc7fb98d4b311f084b30242ac130006"],
    "top_n": 30,
    "metadata_condition": {
      "logic": "and",
      "conditions": [
        {"name": "fund_name", "comparison_operator": "=", "value": "Asian Income Fund"}
      ]
    }
  }' \
  "https://10.1.9.133:8443/api/v1/retrieval"
```

### 查询问题
```
What are top holdings of Asian Income Fund from January to September 2025
```

### 返回结果统计

#### Top holdings - equities 覆盖
- ✅ January 2025: Rank 3, Score=0.4231
- ✅ February 2025: Rank 13, Score=0.3953
- ✅ March 2025: Rank 16, Score=0.3929
- ✅ April 2025: Rank 20, Score=0.3916
- ✅ May 2025: Rank 18, Score=0.3918
- ✅ June 2025: Rank 17, Score=0.3925
- ✅ July 2025: Rank 19, Score=0.3917
- ✅ August 2025: Rank 11, Score=0.3968
- ✅ September 2025: Rank 6, Score=0.4215
- **覆盖: 9/9**

#### Top holdings - fixed income 覆盖
- ✅ January 2025: Rank 2, Score=0.4478
- ✅ February 2025: Rank 5, Score=0.4228
- ✅ March 2025: Rank 12, Score=0.3959
- ✅ April 2025: Rank 8, Score=0.4200
- ✅ May 2025: Rank 7, Score=0.4204
- ✅ June 2025: Rank 9, Score=0.4185
- ✅ July 2025: Rank 14, Score=0.3943
- ✅ August 2025: Rank 10, Score=0.3969
- ✅ September 2025: Rank 4, Score=0.4231
- **覆盖: 9/9**

#### 其他类型chunks (Top 5)
- Rank 1: VP_Asian_Income_Fund_2025Sep_Credit_ratings.md, Score=0.4569
- Rank 21: VP_Asian_Income_Fund_2025Sep_Investment_objective.md, Score=0.3774
- Rank 22: VP_Asian_Income_Fund_2025Sep_Monthly_performance.md, Score=0.3687
- Rank 23: VP_Asian_Income_Fund_2025Sep_Asset_type_by_geography.md, Score=0.3645
- Rank 24: VP_Asian_Income_Fund_2025Sep_Portfolio_characteristics.md, Score=0.3594

**其他类型chunks总数: 11**

---

## 对比分析

### 覆盖率对比

| 指标 | 查询1（带括号） | 查询2（原始） |
|------|----------------|--------------|
| **equities覆盖** | 7/9 ❌ | **9/9** ✅ |
| **fixed income覆盖** | 7/9 ❌ | **9/9** ✅ |
| **其他类型chunks** | 15个 | 11个 |

### 分数分布对比

#### 查询1（带括号）
- **Top holdings分数范围**: 0.5675 - 0.5913
- **其他类型分数范围**: 0.5620 - 0.5783
- **分数重叠**: 严重重叠，难以区分

#### 查询2（原始）
- **Top holdings分数范围**: 0.3916 - 0.4478
- **其他类型分数范围**: 0.3594 - 0.4569
- **分数重叠**: 有重叠，但Top holdings整体更高

### 关键发现

1. **查询1（带括号）的问题**:
   - 虽然分数绝对值更高（0.56-0.59），但Top holdings和其他类型的分数差距很小
   - 其他类型chunks因为匹配到月份关键词，分数被拉高
   - 导致March和May的Top holdings被挤出Top 30

2. **查询2（原始）的优势**:
   - 虽然分数绝对值较低（0.39-0.45），但覆盖了全部9个月份
   - Top holdings的分数整体高于其他类型（除了Rank 1的Credit ratings）
   - 更符合用户需求

---

## 结论

**原始版本（不带括号）更适合**，因为：
1. ✅ 覆盖了全部9个月份的Top holdings
2. ✅ Top holdings和其他类型的分数差距更明显（虽然绝对值较低）
3. ✅ 其他类型chunks更少（11 vs 15）

**建议**: 不要用括号附加月份列表，而是直接替换时间范围，或者保持原问题不变。

