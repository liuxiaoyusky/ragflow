#!/usr/bin/env python3
"""
用增强后的问题重新测试RAGFlow，更新回原结果文件
"""
import json
import time
import sys
import urllib3
from pathlib import Path

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent))
from config import TestConfig

FUND_NAME = "Value Partners High-Dividend Stocks Fund"

# 59个需要重新测试的问题（增强版）
ENHANCED_QUESTIONS = {
    2: f"{FUND_NAME}的Class A1 HKD2和Class A HKD Hedged Acc的NAV相比如何？",
    5: f"{FUND_NAME}的Class A RMB Hedged Acc和Class A RMB Unhedged Acc的NAV差异有多大？",
    6: f"{FUND_NAME}中哪个份额类别的NAV最低？",
    10: f"{FUND_NAME}在2017年和2018年的Class A1 USD年度收益率分别是多少？",
    11: f"{FUND_NAME}在2019年表现最好的月份是哪个？",
    14: f"{FUND_NAME}的最小初始认购金额要求是多少？",
    17: f"{FUND_NAME}在亚洲新兴市场投资面临哪些主要风险？",
    18: f"{FUND_NAME}在信息技术行业的配置比例是多少？",
    19: f"{FUND_NAME}的Class A1 USD最新资产净值是多少？",
    21: f"{FUND_NAME}的Class A1 USD过去12个月的资产净值变动幅度是多少？",
    24: f"{FUND_NAME}的Class A HKD Hedged Acc资产净值在过去一年中的最高值和最低值是多少？",
    26: f"{FUND_NAME}的Class A1 USD资产净值在最近一个季度的增长率是多少？",
    27: f"{FUND_NAME}资产净值最大的五个份额类别是哪些？",
    28: f"{FUND_NAME}的Class A1 HKD2资产净值与同类基金平均水平相比如何？",
    32: f"{FUND_NAME}各份额类别的资产净值在最近一个月的表现排名如何？",
    33: f"{FUND_NAME}资产净值与总资产规模的比值是多少？",
    34: f"{FUND_NAME}的Class A1 USD当前NAV是多少？",
    35: f"{FUND_NAME}的Class A2 HKD MDis年度化分红收益率是多少？",
    36: f"请比较{FUND_NAME}的Class A1 USD和Class A1 HKD的NAV差异？",
    37: f"{FUND_NAME}在2023年的前五大持仓行业是什么？",
    39: f"{FUND_NAME}的地理配置中权重最高的地区是哪里？",
    40: f"{FUND_NAME}的Class A2 AUD Hedged MDis最近除息日是什么时候？",
    41: f"{FUND_NAME}自成立以来的年化收益率是多少？",
    43: f"{FUND_NAME}在2018年10月的月收益率是多少？",
    44: f"{FUND_NAME}投资组合中信息技术行业的权重占比是多少？",
    46: f"{FUND_NAME}在2019年全年收益率与2017年相比如何？",
    49: f"{FUND_NAME}在印度市场的配置比例是多少？",
    50: f"{FUND_NAME}在2016年至2019年间，哪一年的年度表现最差？",
    51: f"{FUND_NAME}最低首次申购金额要求最高的份额类别是哪个？",
    53: f"{FUND_NAME}的房地产行业在行业配置中的排名是第几位？",
    54: f"{FUND_NAME}的Class A1 USD在2019年相对于基准指数的超额收益是多少？",
    56: f"{FUND_NAME}过去五年间表现最好和最差的年份分别是哪一年？",
    58: f"{FUND_NAME}一年期和三年期的年化收益率分别是多少？",
    61: f"{FUND_NAME}在2018年市场下跌期间的表现如何？",
    62: f"{FUND_NAME}的Class C USD份额类别今年以来的累计收益是多少？",
    65: f"{FUND_NAME}过去12个月的信息比率是多少？",
    68: f"{FUND_NAME}目前相对于其业绩比较基准的表现如何？",
    69: f"{FUND_NAME}的Class A2 USD MDis每单位派息金额是多少？",
    74: f"{FUND_NAME}的主要投资策略和风险特征是什么？",
    75: f"{FUND_NAME}投资组合中前五大持仓股的权重分别是多少？",
    76: f"{FUND_NAME}在2017年的最佳月度收益率出现在哪个月份？",
    77: f"{FUND_NAME}从成立以来的年化收益率是多少？",
    78: f"{FUND_NAME}各份额类别的最低认购金额分别是多少？",
    79: f"{FUND_NAME}对不同币种份额收取的管理费有什么差异？",
    80: f"{FUND_NAME}在行业配置上最大的三个权重行业是什么？",
    82: f"{FUND_NAME}在2016年至2019年间，表现最好和最差的年份分别是哪一年？",
    83: f"{FUND_NAME}的Class A1 USD份额的ISIN编码是多少？",
    85: f"{FUND_NAME}收取的最高认购费率是多少？",
    87: f"{FUND_NAME}投资组合中信息技术行业的配置比例是多少？",
    88: f"{FUND_NAME}对新兴市场的投资风险披露包含哪些主要内容？",
    89: f"{FUND_NAME}的Class A2 USD MDis份额最新季度派息金额是多少？",
    92: f"{FUND_NAME}哪个币种计价的份额类别最近12个月的分红收益率最高？",
    93: f"{FUND_NAME}最近一个财年的总分红金额是多少？",
    94: f"{FUND_NAME}的分红支付频率和支付日是如何安排的？",
    95: f"{FUND_NAME}的股息再投资计划(DRIP)有哪些具体条款？",
    97: f"{FUND_NAME}在股息支付方面有哪些税务预扣安排？",
    98: f"{FUND_NAME}的Class A1 USD和Class A1 HKD当前资产净值(NAV)分别是多少？",
    99: f"{FUND_NAME}不同份额类别的最低认购金额要求有何区别？",
    100: f"{FUND_NAME}的Class A2 USD MDis和Class A2 HKD MDis年度化股息收益率分别是多少？",
}


class RAGFlowRetester:
    def __init__(self, config: TestConfig):
        self.config = config
        self.headers = config.get_headers()
        self.base_url = config.get_base_url()
        self.session_id = None
    
    def create_session(self) -> str:
        url = f"{self.base_url}/chats/{self.config.chat_id}/sessions"
        payload = {"name": f"Retest_{time.strftime('%Y%m%d_%H%M%S')}"}
        response = requests.post(url, headers=self.headers, json=payload, verify=False)
        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"Failed to create session: {result}")
        self.session_id = result["data"]["id"]
        print(f"✓ Created session: {self.session_id}")
        return self.session_id
    
    def ask_question(self, question: str) -> dict:
        url = f"{self.base_url}/chats/{self.config.chat_id}/completions"
        payload = {
            "question": question,
            "stream": False,
            "session_id": self.session_id
        }
        
        start_time = time.time()
        try:
            response = requests.post(url, headers=self.headers, json=payload, verify=False, timeout=120)
            response_time = time.time() - start_time
            result = response.json()
            
            if result.get("code") != 0:
                return {"success": False, "answer": "", "error": result.get("message"), "response_time": response_time}
            
            data = result.get("data", {})
            return {
                "success": True,
                "answer": data.get("answer", ""),
                "reference": data.get("reference", {}),
                "response_time": response_time
            }
        except Exception as e:
            return {"success": False, "answer": "", "error": str(e), "response_time": time.time() - start_time}
    
    def run_retest(self, original_file: str, output_file: str):
        # 加载原始结果
        with open(original_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = data.get("results", [])
        results_map = {r["index"]: r for r in results}
        
        # 创建会话
        self.create_session()
        
        # 重新测试
        total = len(ENHANCED_QUESTIONS)
        for i, (idx, question) in enumerate(ENHANCED_QUESTIONS.items(), 1):
            print(f"[{i}/{total}] Q{idx}: {question[:50]}...")
            
            result = self.ask_question(question)
            
            # 更新结果
            if idx in results_map:
                results_map[idx]["enhanced_question"] = question
                results_map[idx]["retest_answer"] = result.get("answer", "")
                results_map[idx]["retest_response_time"] = result.get("response_time", 0)
                results_map[idx]["retest_success"] = result.get("success", False)
                results_map[idx]["retest_reference"] = result.get("reference", {})
            
            # 每10个保存一次
            if i % 10 == 0:
                self._save(data, results_map, output_file)
                print(f"  Progress saved at {i}/{total}")
            
            time.sleep(1)
        
        # 最终保存
        self._save(data, results_map, output_file)
        print(f"\n✓ Retest completed. Results saved to {output_file}")
    
    def _save(self, data, results_map, output_file):
        data["results"] = sorted(results_map.values(), key=lambda x: x.get("index", 0))
        data["metadata"]["retested_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    config = TestConfig()
    retester = RAGFlowRetester(config)
    
    original_file = "test_output/ragflow_cn_evaluated.json"
    output_file = "test_output/ragflow_cn_retested.json"
    
    retester.run_retest(original_file, output_file)


if __name__ == "__main__":
    main()

