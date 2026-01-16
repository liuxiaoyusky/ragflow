#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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
Unit tests for semantic_merge_mineru function.
"""
import pytest
from rag.nlp import semantic_merge_mineru


class TestSemanticMergeMineru:
    """Test cases for semantic_merge_mineru function."""

    def test_empty_input(self):
        """Test with empty input."""
        result = semantic_merge_mineru([])
        assert result == []

    def test_single_text_block(self):
        """Test with a single text block."""
        sections = [
            {
                "content": "This is a text block.",
                "type": "text",
                "caption": "",
                "position": "@@1\t0\t100\t0\t50##",
                "page_idx": 0,
            }
        ]
        result = semantic_merge_mineru(sections)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert "This is a text block." in result[0]["content"]

    def test_table_block_independent(self):
        """Test that table blocks are kept as independent chunks."""
        sections = [
            {"content": "Text before table.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {
                "content": "<table><tr><td>A</td><td>B</td></tr></table>",
                "type": "table",
                "caption": "Table 1: Sample Data",
                "position": "",
                "page_idx": 0,
            },
            {"content": "Text after table.", "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections)
        
        # Should have 3 chunks: text, table, text
        assert len(result) == 3
        assert result[0]["type"] == "text"
        assert result[1]["type"] == "table"
        assert result[2]["type"] == "text"
        
        # Table should have caption prepended
        assert "Table 1: Sample Data" in result[1]["content"]
        
        # Caption should be preserved separately
        assert result[1]["caption"] == "Table 1: Sample Data"

    def test_image_block_independent(self):
        """Test that image blocks are kept as independent chunks."""
        sections = [
            {"content": "Text before image.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "Figure description", "type": "image", "caption": "Figure 1: Chart", "position": "", "page_idx": 0},
            {"content": "Text after image.", "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections)
        
        assert len(result) == 3
        assert result[1]["type"] == "image"
        assert result[1]["caption"] == "Figure 1: Chart"

    def test_text_merge_within_limit(self):
        """Test that small text blocks are merged together."""
        sections = [
            {"content": "Short text 1.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "Short text 2.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "Short text 3.", "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections, chunk_token_num=512)
        
        # All short texts should be merged into one chunk
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert "Short text 1." in result[0]["content"]
        assert "Short text 2." in result[0]["content"]
        assert "Short text 3." in result[0]["content"]

    def test_text_split_at_limit(self):
        """Test that text is split when exceeding token limit."""
        # Create a long text that should be split
        long_text = "This is a sentence. " * 100  # ~400 tokens
        sections = [
            {"content": long_text, "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": long_text, "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections, chunk_token_num=200)
        
        # Should create multiple chunks
        assert len(result) >= 2
        for chunk in result:
            assert chunk["type"] == "text"

    def test_mixed_content_types(self):
        """Test with mixed content types (text, table, image, equation)."""
        sections = [
            {"content": "Introduction text.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "E = mc^2", "type": "equation", "caption": "", "position": "", "page_idx": 0},
            {"content": "<table>...</table>", "type": "table", "caption": "Results", "position": "", "page_idx": 0},
            {"content": "Conclusion text.", "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections, chunk_token_num=512)
        
        # Text and equation should be merged, table separate
        # Final structure: merged(text+equation), table, text
        types = [r["type"] for r in result]
        assert "table" in types

    def test_legacy_tuple_format_fallback(self):
        """Test fallback handling of legacy tuple format."""
        sections = [
            ("Text content 1", "@@1\t0\t100\t0\t50##"),
            ("Text content 2", "@@1\t0\t100\t50\t100##"),
        ]
        result = semantic_merge_mineru(sections, chunk_token_num=512)
        
        # Should handle legacy format without errors
        assert len(result) >= 1
        assert "Text content" in result[0]["content"]

    def test_empty_content_filtered(self):
        """Test that empty content blocks are filtered out."""
        sections = [
            {"content": "Valid text.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "   ", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "Another valid text.", "type": "text", "caption": "", "position": "", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections)
        
        # Empty blocks should be filtered
        assert len(result) == 1
        assert "Valid text." in result[0]["content"]
        assert "Another valid text." in result[0]["content"]

    def test_position_preserved(self):
        """Test that position information is preserved."""
        sections = [
            {"content": "Text block.", "type": "text", "caption": "", "position": "@@1\t0\t100\t0\t50##", "page_idx": 0},
        ]
        result = semantic_merge_mineru(sections)
        
        assert len(result) == 1
        assert result[0]["position"] == "@@1\t0\t100\t0\t50##"
        assert result[0]["page_idx"] == 0

    def test_page_idx_preserved(self):
        """Test that page_idx is preserved correctly."""
        sections = [
            {"content": "Page 1 content.", "type": "text", "caption": "", "position": "", "page_idx": 0},
            {"content": "<table>...</table>", "type": "table", "caption": "Table", "position": "", "page_idx": 1},
        ]
        result = semantic_merge_mineru(sections, chunk_token_num=512)
        
        # Check that page_idx is preserved
        table_chunks = [r for r in result if r["type"] == "table"]
        assert len(table_chunks) == 1
        assert table_chunks[0]["page_idx"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
