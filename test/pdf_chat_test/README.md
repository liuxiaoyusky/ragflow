# RAGFlow Chat 自动化测试工具

这个工具用于自动化测试RAGFlow Chat API，特别是针对PDF文档的问答质量。

## 功能特性

1. **问题生成**: 从PDF的parsed chunks中自动生成100个多样化测试问题
2. **API测试**: 批量调用Chat API并记录所有回复
3. **质量评估**: 使用LLM自动评估回复的准确性、相关性、完整性和引用质量
4. **报告生成**: 生成详细的JSON和HTML格式测试报告

## 安装依赖

```bash
pip install requests openai
```

## 配置

通过环境变量配置：

```bash
# RAGFlow API配置（必需）
export RAGFLOW_HOST="https://10.1.9.133:8443"
export RAGFLOW_API_KEY="your_api_key"
export RAGFLOW_CHAT_ID="your_chat_id"
export RAGFLOW_DATASET_ID="your_dataset_id"
export RAGFLOW_DOCUMENT_ID="fee15b84cb6311f09cf40242ac130006"

# LLM评估配置（必需，用于问题生成和评估）
export EVAL_LLM_API_KEY="your_openai_api_key"
export EVAL_LLM_MODEL="gpt-4"  # 可选，默认gpt-4
export EVAL_LLM_BASE_URL="https://api.openai.com/v1"  # 可选

# 测试配置（可选）
export NUM_QUESTIONS=100  # 默认100
export TEST_OUTPUT_DIR="./test_output"  # 默认./test_output
```

## 使用方法

### 完整测试流程

```bash
cd test/pdf_chat_test
python run_test.py
```

### 分步执行

```bash
# 只生成问题
python run_test.py --skip-test --skip-evaluation

# 只执行API测试（使用已有问题）
python run_test.py --skip-questions --skip-evaluation

# 只进行评估（使用已有测试结果）
python run_test.py --skip-questions --skip-test
```

### 指定文件路径

```bash
python run_test.py --questions-file ./custom_questions.json --results-file ./custom_results.json
```

## 输出文件

测试完成后，在 `TEST_OUTPUT_DIR` 目录下会生成：

- `questions.json`: 生成的所有测试问题
- `test_results.json`: API测试的原始结果
- `test_report.json`: 包含评估结果的完整报告（JSON格式）
- `test_report.html`: 可视化测试报告（HTML格式）

## 报告说明

### JSON报告结构

```json
{
  "metadata": {
    "chat_id": "...",
    "document_id": "...",
    "total_questions": 100,
    "generated_at": "..."
  },
  "statistics": {
    "total_questions": 100,
    "successful_requests": 95,
    "failed_requests": 5,
    "success_rate": 95.0,
    "average_scores": {
      "accuracy": 4.2,
      "relevance": 4.1,
      "completeness": 3.9,
      "citation_quality": 4.0,
      "overall": 4.05
    },
    "response_time": {
      "average": 2.5,
      "min": 1.2,
      "max": 5.8
    }
  },
  "results": [...]
}
```

### HTML报告

打开 `test_report.html` 可以在浏览器中查看：
- 总体统计信息
- 分数分布
- 各维度平均分
- 每个问题的详细结果

## 评估维度

每个回复会被评估以下维度（1-5分）：

1. **准确性 (Accuracy)**: 回复内容是否与PDF原文一致
2. **相关性 (Relevance)**: 回复是否直接回答了问题
3. **完整性 (Completeness)**: 回复是否涵盖了问题的所有方面
4. **引用质量 (Citation Quality)**: 检索的chunks是否与问题相关

## 注意事项

1. 确保RAGFlow服务正常运行且可访问
2. 确保PDF文档已成功解析并生成chunks
3. 评估LLM（如OpenAI）需要有效的API密钥
4. 测试过程可能需要较长时间（100个问题约需10-30分钟）
5. 支持断点续测：如果测试中断，重新运行会自动从上次停止的地方继续

## 故障排除

### API连接错误

检查：
- RAGFLOW_HOST是否正确
- RAGFLOW_API_KEY是否有效
- 网络连接是否正常

### 问题生成失败

检查：
- EVAL_LLM_API_KEY是否设置
- LLM API是否可访问
- PDF chunks是否已成功解析

### 评估失败

检查：
- EVAL_LLM_API_KEY是否有效
- LLM API配额是否充足
- 测试结果文件是否完整

