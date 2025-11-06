#!/bin/bash

# SILICONFLOW-Overseas 功能测试脚本
# 功能：验证修复后的配置是否正常工作

set -e

echo "=========================================="
echo "SILICONFLOW-Overseas 功能测试"
echo "=========================================="
echo ""

# 检查是否提供了 API Key
if [ -z "$SILICONFLOW_API_KEY" ]; then
    echo "❌ 错误: 未设置 SILICONFLOW_API_KEY 环境变量"
    echo "用法: SILICONFLOW_API_KEY=your_api_key bash $0"
    exit 1
fi

API_KEY="$SILICONFLOW_API_KEY"
BASE_URL="https://api.siliconflow.com/v1"

echo "[1/3] 测试 Qwen Embedding API（应该可用）"
echo "----------------------------------------"
RESPONSE=$(curl -s -X POST "$BASE_URL/embeddings" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-Embedding-8B",
    "input": ["测试文本"]
  }')

if echo "$RESPONSE" | grep -q '"object":"list"'; then
    echo "✅ Qwen Embedding API 测试成功"
    echo "   模型: Qwen/Qwen3-Embedding-8B"
    DIMENSIONS=$(echo "$RESPONSE" | grep -o '"embedding":\[[^]]*\]' | head -1 | tr ',' '\n' | wc -l)
    echo "   向量维度: $DIMENSIONS"
else
    echo "❌ Qwen Embedding API 测试失败"
    echo "   响应: $RESPONSE"
fi
echo ""

echo "[2/3] 测试 Rerank API"
echo "----------------------------------------"
RESPONSE=$(curl -s -X POST "$BASE_URL/rerank" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Pro/BAAI/bge-reranker-v2-m3",
    "query": "什么是人工智能？",
    "documents": ["人工智能是计算机科学的一个分支", "今天天气很好", "机器学习是人工智能的子领域"]
  }')

if echo "$RESPONSE" | grep -q '"results"'; then
    echo "✅ Rerank API 测试成功"
    echo "   模型: Pro/BAAI/bge-reranker-v2-m3"
    BEST_SCORE=$(echo "$RESPONSE" | grep -o '"relevance_score":[0-9.]*' | head -1 | cut -d':' -f2)
    echo "   最高相关度分数: $BEST_SCORE"
else
    echo "❌ Rerank API 测试失败"
    echo "   响应: $RESPONSE"
fi
echo ""

echo "[3/3] 测试 Chat API (DeepSeek-V3.1)"
echo "----------------------------------------"
RESPONSE=$(curl -s -X POST "$BASE_URL/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-ai/DeepSeek-V3.1",
    "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己"}],
    "max_tokens": 100
  }')

if echo "$RESPONSE" | grep -q '"choices"'; then
    echo "✅ Chat API 测试成功"
    echo "   模型: deepseek-ai/DeepSeek-V3.1"
    CONTENT=$(echo "$RESPONSE" | grep -o '"content":"[^"]*"' | head -1 | cut -d':' -f2- | tr -d '"')
    echo "   响应: ${CONTENT:0:100}..."
else
    echo "❌ Chat API 测试失败"
    echo "   响应: $RESPONSE"
fi
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="
echo ""
echo "【测试总结】"
echo "✅ 表示该功能正常工作"
echo "❌ 表示该功能存在问题，需要进一步排查"
echo ""
echo "【注意事项】"
echo "1. 如果所有测试都通过，说明 API 配置正确"
echo "2. 部署后需要在 Web UI 中进一步测试完整功能"
echo "3. 确认 Pro/BAAI/bge-m3 不再出现在模型列表中"
echo ""

