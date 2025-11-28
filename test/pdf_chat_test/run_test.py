#!/usr/bin/env python3
#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
RAGFlow Chat自动化测试工具

用法:
    python run_test.py [--skip-questions] [--skip-test] [--skip-evaluation]

环境变量:
    RAGFLOW_HOST: RAGFlow服务器地址 (默认: https://10.1.9.133:8443)
    RAGFLOW_API_KEY: RAGFlow API密钥 (必需)
    RAGFLOW_CHAT_ID: Chat Assistant ID (必需)
    RAGFLOW_DATASET_ID: Dataset ID (必需)
    RAGFLOW_DOCUMENT_ID: Document ID (默认: fee15b84cb6311f09cf40242ac130006)
    EVAL_LLM_API_KEY: 用于问题生成和评估的LLM API密钥 (必需)
    EVAL_LLM_MODEL: LLM模型名称 (默认: gpt-4)
    EVAL_LLM_BASE_URL: LLM API基础URL (可选)
    NUM_QUESTIONS: 生成的问题数量 (默认: 100)
    TEST_OUTPUT_DIR: 测试输出目录 (默认: ./test_output)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# 添加当前目录到路径，以便导入模块
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# 直接导入（当前目录已在sys.path中）
from config import TestConfig
from question_generator import QuestionGenerator
from chat_tester import ChatTester
from evaluator import Evaluator
from reporter import Reporter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="RAGFlow Chat自动化测试工具")
    parser.add_argument("--skip-questions", action="store_true", help="跳过问题生成，使用已有问题文件")
    parser.add_argument("--skip-test", action="store_true", help="跳过API测试，使用已有测试结果")
    parser.add_argument("--skip-evaluation", action="store_true", help="跳过评估，使用已有评估结果")
    parser.add_argument("--append-questions", action="store_true", help="保留已有好问题，补充到目标数量")
    parser.add_argument("--questions-file", type=str, help="指定问题文件路径")
    parser.add_argument("--results-file", type=str, help="指定测试结果文件路径")
    
    args = parser.parse_args()
    
    try:
        # 初始化配置
        config = TestConfig()
        logger.info("Configuration loaded")
        
        # 确保输出目录存在
        os.makedirs(config.output_dir, exist_ok=True)
        
        # 步骤1: 生成问题
        questions = []
        questions_file = args.questions_file or os.path.join(config.output_dir, "questions.json")
        
        if not args.skip_questions:
            logger.info("=" * 60)
            logger.info("Step 1: Generating questions from PDF chunks")
            logger.info("=" * 60)
            
            generator = QuestionGenerator(config)
            questions = generator.generate(questions_file, append_to_existing=args.append_questions)
            logger.info(f"Generated/Loaded {len(questions)} questions")
        else:
            logger.info(f"Loading questions from {questions_file}")
            generator = QuestionGenerator(config)
            questions = generator.load_questions(questions_file)
            logger.info(f"Loaded {len(questions)} questions")
        
        if not questions:
            logger.error("No questions available. Exiting.")
            return
        
        # 步骤2: 执行Chat API测试
        test_results = []
        results_file = args.results_file or os.path.join(config.output_dir, "test_results.json")
        
        if not args.skip_test:
            logger.info("=" * 60)
            logger.info("Step 2: Testing Chat API with questions")
            logger.info("=" * 60)
            
            tester = ChatTester(config)
            test_results = tester.test_questions(questions, results_file)
            logger.info(f"Tested {len(test_results)} questions")
        else:
            logger.info(f"Loading test results from {results_file}")
            import json
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                test_results = data.get("results", [])
            logger.info(f"Loaded {len(test_results)} test results")
        
        if not test_results:
            logger.error("No test results available. Exiting.")
            return
        
        # 步骤3: 评估回复质量
        evaluated_results = test_results
        
        if not args.skip_evaluation:
            logger.info("=" * 60)
            logger.info("Step 3: Evaluating response quality")
            logger.info("=" * 60)
            
            evaluator = Evaluator(config)
            evaluated_results = evaluator.evaluate_all(test_results)
            logger.info(f"Evaluated {len(evaluated_results)} responses")
            
            # 保存评估结果回文件
            import json
            with open(results_file, "r", encoding="utf-8") as f:
                results_data = json.load(f)
            results_data["results"] = evaluated_results
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Evaluation results saved to {results_file}")
        else:
            # 检查是否已有评估结果
            if test_results and test_results[0].get("evaluation"):
                logger.info("Using existing evaluation results")
                evaluated_results = test_results
            else:
                logger.warning("No evaluation results found. Running evaluation...")
                evaluator = Evaluator(config)
                evaluated_results = evaluator.evaluate_all(test_results)
                
                # 保存评估结果
                import json
                with open(results_file, "r", encoding="utf-8") as f:
                    results_data = json.load(f)
                results_data["results"] = evaluated_results
                with open(results_file, "w", encoding="utf-8") as f:
                    json.dump(results_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Evaluation results saved to {results_file}")
        
        # 步骤4: 生成报告
        logger.info("=" * 60)
        logger.info("Step 4: Generating test report")
        logger.info("=" * 60)
        
        reporter = Reporter(config)
        report_data = reporter.generate_report(evaluated_results)
        
        # 生成完整PDF报告（评分汇总+详细问答）
        logger.info("=" * 60)
        logger.info("Step 5: Generating full PDF report")
        logger.info("=" * 60)
        
        from full_report import FullReportGenerator
        full_reporter = FullReportGenerator(config)
        full_report_path = full_reporter.generate(
            results_file,
            os.path.join(config.output_dir, "full_report.pdf")
        )
        
        stats = report_data.get("statistics", {})
        logger.info("=" * 60)
        logger.info("Test Summary:")
        logger.info(f"  Total Questions: {stats.get('total_questions', 0)}")
        logger.info(f"  Success Rate: {stats.get('success_rate', 0):.1f}%")
        logger.info(f"  Average Overall Score: {stats.get('average_scores', {}).get('overall', 0):.2f}/5.0")
        logger.info(f"  Average Response Time: {stats.get('response_time', {}).get('average', 0):.2f}s")
        logger.info("=" * 60)
        logger.info(f"Reports saved to: {config.output_dir}")
        logger.info("  - test_report.json (detailed data)")
        logger.info("  - test_report.html (visual report)")
        logger.info("  - full_report.pdf (完整报告：评分汇总+详细问答)")
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

