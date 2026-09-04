"""Mattermost language-first / markdown-safe long-post splitting."""

from __future__ import annotations

import unittest

from plugins.platforms.mattermost.message_split import split_mattermost_message


def _english(n: int) -> str:
    return ("alpha bravo charlie delta echo foxtrot " * ((n // 36) + 1))[:n]


def _chinese(n: int) -> str:
    unit = "這是一段繁體中文說明內容用於測試長度切割行為。"
    return (unit * ((n // len(unit)) + 1))[:n]


class TestLanguageFirstSplit(unittest.TestCase):
    def test_short_message_unchanged(self):
        text = "Hello\n\n---\n\n你好"
        self.assertEqual(split_mattermost_message(text, 4000), [text])

    def test_splits_by_language_before_character_budget(self):
        english = _english(2200)
        chinese = _chinese(2200)
        text = f"{english}\n\n---\n\n{chinese}"
        chunks = split_mattermost_message(text, 4000)
        self.assertEqual(len(chunks), 2)
        self.assertIn(english, chunks[0])
        self.assertIn(chinese, chunks[1])
        self.assertNotIn(chinese, chunks[0])
        self.assertNotIn(english, chunks[1])
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

    def test_preserves_chinese_then_english_order(self):
        chinese = _chinese(2200)
        english = _english(2200)
        text = f"{chinese}\n\n---\n\n{english}"
        chunks = split_mattermost_message(text, 4000)
        self.assertIn(chinese, chunks[0])
        self.assertIn(english, chunks[1])

    def test_splits_on_script_switch_without_horizontal_rule(self):
        english = _english(2200)
        chinese = _chinese(2200)
        text = f"{english}\n\n{chinese}"
        chunks = split_mattermost_message(text, 4000)
        self.assertEqual(len(chunks), 2)
        self.assertIn(english, chunks[0])
        self.assertIn(chinese, chunks[1])


class TestMarkdownAtomicSplit(unittest.TestCase):
    def test_does_not_split_inside_fenced_code(self):
        fence = "```python\n" + ("print('x')\n" * 80) + "```"
        intro = _english(500)
        outro = _english(500)
        text = f"{intro}\n\n{fence}\n\n{outro}"
        chunks = split_mattermost_message(text, 1200)
        code_chunks = [chunk for chunk in chunks if "print('x')" in chunk]
        self.assertTrue(code_chunks)
        for chunk in code_chunks:
            self.assertEqual(chunk.strip().count("```") % 2, 0)
            self.assertIn("```", chunk)

    def test_does_not_split_inside_markdown_table(self):
        header = "| Name | Qty |\n| --- | --- |"
        rows = "\n".join(f"| item-{i} | {i} |" for i in range(40))
        table = f"{header}\n{rows}"
        intro = _english(200)
        text = f"{intro}\n\n{table}"
        chunks = split_mattermost_message(text, 400)
        table_chunks = [chunk for chunk in chunks if "|" in chunk]
        self.assertTrue(table_chunks)
        for chunk in table_chunks:
            if "item-" in chunk:
                self.assertIn("| Name | Qty |", chunk)
                self.assertIn("| --- | --- |", chunk)
                for line in chunk.splitlines():
                    if line.startswith("|"):
                        self.assertTrue(
                            line.rstrip().endswith("|"),
                            msg=repr(line),
                        )

    def test_repeats_table_header_when_table_exceeds_limit(self):
        header = "| Name | Qty |\n| --- | --- |"
        rows = "\n".join(f"| item-{i:02d} | {i} |" for i in range(80))
        table = f"{header}\n{rows}"
        chunks = split_mattermost_message(table, 250)
        self.assertGreaterEqual(len(chunks), 2)
        data_chunks = [chunk for chunk in chunks if "item-" in chunk]
        self.assertGreaterEqual(len(data_chunks), 2)
        for chunk in data_chunks:
            self.assertIn("| Name | Qty |", chunk)

    def test_long_monolingual_still_splits(self):
        msg = "a " * 2500
        chunks = split_mattermost_message(msg, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)


class TestAdapterHook(unittest.TestCase):
    def test_adapter_truncate_uses_language_first_splitter(self):
        from gateway.config import PlatformConfig
        from plugins.platforms.mattermost.adapter import MattermostAdapter

        config = PlatformConfig(
            enabled=True,
            token="test-token",
            extra={"url": "https://mm.example.com", "pd_one_policy_bridge": False},
        )
        adapter = MattermostAdapter(config)
        english = _english(2200)
        chinese = _chinese(2200)
        text = f"{english}\n\n---\n\n{chinese}"
        chunks = adapter.truncate_message(text, 4000)
        self.assertEqual(len(chunks), 2)
        self.assertIn(english, chunks[0])
        self.assertIn(chinese, chunks[1])


if __name__ == "__main__":
    unittest.main()
