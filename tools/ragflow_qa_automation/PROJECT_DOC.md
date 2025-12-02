# RAGFlow QA 自动化测评说明

本工具链通过自动化流程，从 PDF 解析数据生成测试问答，用来衡量知识库的检索与回答能力，并对 RAGFlow 和 Knowledge AI（飞书）两套回复进行质量评估。

## 流程概览
- **问题生成**：从指定 PDF 的 parsed chunks 自动生成 100 个多样化问题，覆盖事实、对比、排行、时间、风险等维度。
- **双路答复获取**：
  - **RAGFlow**：调用 Chat API（`run_test.py` / `chat_tester.py`）批量获取回答。
  - **Knowledge AI（飞书）**：使用已有的测试结果文件（`feishu-test-results.json`），或通过 `feishu_compare.py` 抓取。
- **质量评估标准**：使用评估 LLM（`evaluator.py` / `evaluate_feishu.py`）对每个回答按以下维度 1-5 分打分，并计算综合评分：
  - `accuracy` 准确性
  - `relevance` 相关性
  - `completeness` 完整性
  - `citation_quality` 引用匹配度
  - `overall` 综合（加权汇总）
- **报告生成**：`reporter.py` / `comparison_report.py` / `generate_final_report.py` 生成 JSON + HTML（可选 PDF）报告，展示总体分、分布、每题对比。

## 配置要点（新知识库/新版本时修改）
在 `config.py` 使用环境变量覆盖：
- `RAGFLOW_HOST` / `RAGFLOW_API_KEY` / `RAGFLOW_API_VERSION`
- `RAGFLOW_CHAT_ID` / `RAGFLOW_DATASET_ID` / `RAGFLOW_DOCUMENT_ID`（指向新的知识库/文档）
- 问题数量与输出目录：`NUM_QUESTIONS`、`TEST_OUTPUT_DIR`
- 评估 LLM：`EVAL_LLM_PROVIDER` / `EVAL_LLM_MODEL` / `EVAL_LLM_API_KEY` / `EVAL_LLM_BASE_URL`

若更换源 PDF，请确保其 chunks 已导入对应 dataset/document，并更新上述 ID。

飞书侧测试结果路径可在命令行指定（如 `--feishu feishu-test-results.json`），或通过 `feishu_compare.py` 重新抓取。

## 核心命令
- 全流程（生成问题、测试、评估、报告）：
  ```bash
  cd tools/ragflow_qa_automation
  python run_test.py
  ```
- 仅生成问题：`python run_test.py --skip-test --skip-evaluation`
- 仅执行 API 测试：`python run_test.py --skip-questions --skip-evaluation`
- 仅评估已有结果：`python run_test.py --skip-questions --skip-test`
- RAGFlow vs 飞书对比报告：`python comparison_report.py --ragflow test_output/test_results.json --feishu feishu-test-results.json --output test_output`

## 每次评分包含内容
- 总体指标：成功率、平均响应时间、各维度平均分、综合分。
- 维度评分：accuracy / relevance / completeness / citation_quality，各 1-5 分。
- 综合评分：依据维度加权的 `overall` 分（1-5）。
- 单题详情：问题、回答、引用摘要、耗时、各维度得分与综合分。

## 目的与能力衡量
该流程用于衡量知识库在以下方面的表现：
- **检索精度**：是否抓到正确 chunks 并引用。
+- **生成质量**：回答是否准确、相关、完整。
- **稳定性与时效**：不同题型/领域下的响应耗时与成功率。

通过定期在新版本知识库运行上述流程，可量化对比版本间能力变化，快速定位回归或提升。 
