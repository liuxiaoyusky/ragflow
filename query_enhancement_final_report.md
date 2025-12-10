# Query Enhancement 最终分析报告

## 目标
找到一种Query Enhancement策略，使"想要的chunk"（Top holdings）与"不想要的chunk"（其他类型）之间的分数差距最大化。

## 评估标准
1. **差距百分比** - WANTED平均分与UNWANTED平均分的差距比例（越大越好）
2. **UNWANTED首位排名** - 第一个UNWANTED chunk出现的位置（越靠后越好）
3. **WANTED覆盖率** - 19个Top holdings chunk全部覆盖

---

## 策略对比总览

| 策略 | 查询 | WANTED数 | 差距% | UNWANTED首位 |
|------|------|----------|-------|--------------|
| baseline | What are top holdings of Asian Income Fund from January to September 2025 | 19 | 10.84% | Rank 1 |
| **strategy_A** | What are top holdings top holdings top holdings... equities fixed income | 19 | **28.08%** | **Rank 20** |
| strategy_B | ...January 2025, February 2025, March 2025... | 17 | 4.43% | Rank 18 |
| strategy_C | top holdings equities fixed income Asian Income Fund... | 19 | 17.58% | Rank 20 |
| strategy_D | ...NOT performance NOT investment NOT credit... | 19 | 10.44% | Rank 1 |
| **strategy_E** | top holdings equities Asian Income Fund 2025 | 19 | **25.78%** | **Rank 20** |
| strategy_F | What are the top 5 stock holdings and top 5 bond holdings... | 19 | 8.19% | Rank 6 |

---

## 最佳策略: Strategy A

**查询**: `What are top holdings top holdings top holdings of Asian Income Fund from January to September 2025 equities fixed income`

### 完整30个Chunk分布

| Rank | 状态 | Score | 文档 |
|------|------|-------|------|
| 1 | ✅ | 0.3669 | VP_Asian_Income_Fund_2025Jan_Top_holdings_-_fixed_income.md |
| 2 | ✅ | 0.3578 | VP_Asian_Income_Fund_2025Jan_Top_holdings_-_equities.md |
| 3 | ✅ | 0.3573 | VP_Asian_Income_Fund_2025Sep_Top_holdings_-_equities.md |
| 4 | ✅ | 0.3569 | VP_Asian_Income_Fund_2025Sep_Top_holdings_-_fixed_income.md |
| 5 | ✅ | 0.3553 | VP_Asian_Income_Fund_2025May_Top_holdings_-_fixed_income.md |
| 6 | ✅ | 0.3544 | VP_Asian_Income_Fund_2025Feb_Top_holdings_-_fixed_income.md |
| 7 | ✅ | 0.3543 | VP_Asian_Income_Fund_2025Apr_Top_holdings_-_fixed_income.md |
| 8 | ✅ | 0.3539 | VP_Asian_Income_Fund_2025Jun_Top_holdings_-_fixed_income.md |
| 9 | ✅ | 0.3501 | VP_Asian_Income_Fund_2025Aug_Top_holdings_-_equities(1).md |
| 10 | ✅ | 0.3470 | VP_Asian_Income_Fund_2025Jun_Top_holdings_-_equities.md |
| 11 | ✅ | 0.3465 | VP_Asian_Income_Fund_2025May_Top_holdings_-_equities.md |
| 12 | ✅ | 0.3458 | VP_Asian_Income_Fund_2025Apr_Top_holdings_-_equities.md |
| 13 | ✅ | 0.3455 | VP_Asian_Income_Fund_2025Mar_Top_holdings_-_equities.md |
| 14 | ✅ | 0.3447 | VP_Asian_Income_Fund_2025Feb_Top_holdings_-_equities.md |
| 15 | ✅ | 0.3447 | VP_Asian_Income_Fund_2025Aug_Top_holdings_-_fixed_income.md |
| 16 | ✅ | 0.3447 | VP_Asian_Income_Fund_2025Jul_Top_holdings_-_equities.md |
| 17 | ✅ | 0.3443 | VP_Asian_Income_Fund_2025Aug_Top_holdings_-_equities.md |
| 18 | ✅ | 0.3438 | VP_Asian_Income_Fund_2025Mar_Top_holdings_-_fixed_income.md |
| 19 | ✅ | 0.3429 | VP_Asian_Income_Fund_2025Jul_Top_holdings_-_fixed_income.md |
| 20 | ❌ | 0.2892 | VP_Asian_Income_Fund_2025Jan_Asset_type_by_sector.md |
| 21 | ❌ | 0.2878 | VP_Asian_Income_Fund_2025Sep_Asset_type_by_sector.md |
| ... | ... | ... | ... |
| 30 | ❌ | 0.2587 | VP_Asian_Income_Fund_2025Sep_Fee_structure.md |

### 关键指标
- **WANTED平均分**: 0.3504
- **UNWANTED平均分**: 0.2736
- **分数差距**: 0.0768 (28.08%)
- **WANTED最低分**: 0.3429 (Rank 19)
- **UNWANTED最高分**: 0.2892 (Rank 20)
- **清晰分界线**: 0.3429 vs 0.2892 = **0.0537分差**

---

## 策略原理分析

### 为什么重复关键词有效？

RagFlow的关键词相似度计算基于token权重匹配：

```python
# rag/nlp/search.py:317-318
tks = content_ltks + title_tks * 2 + important_kwd * 5 + question_tks * 6
```

- **question_tks * 6**: 查询中的token权重最高
- 重复"top holdings"会显著提高这些token的权重
- 只有包含"top holdings"关键词的chunk才能获得高分

### 为什么时间范围展开无效？

strategy_B (展开月份) 效果最差，因为：
1. 展开后的"January 2025, February 2025..."被分散成多个独立token
2. 每个月份token权重被稀释
3. 反而让"Credit ratings"等UNWANTED chunk混入更多

---

## 推荐的LLM Prompt

```
你是一个金融数据查询预处理助手。请分析用户问题并增强查询。

## 规则

### 关键词强调
- 识别核心关键词（如 top holdings, dividend, performance）
- 重复核心关键词3次以增强匹配权重
- 添加相关变体（如 equities, fixed income）

### 示例
- 输入: "What are top holdings of Asian Income Fund from January to September 2025?"
- 输出: "What are top holdings top holdings top holdings of Asian Income Fund from January to September 2025 equities fixed income"

- 输入: "What is the dividend information of High Dividend Fund?"
- 输出: "What is the dividend dividend dividend information of High Dividend Fund payout yield"

### 不要做的事
- 不要展开时间范围（January to September → 不要列出每个月份）
- 不要改变问题的核心意图
```

---

## 结论

**最佳策略**: 重复核心关键词 + 添加相关术语变体

**效果提升**:
- 差距从10.84%提升到28.08% (+159%)
- UNWANTED从Rank 1推到Rank 20
- 100%覆盖所有19个Top holdings chunk

