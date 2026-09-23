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

    def test_isolates_table_from_heading_and_following_prose(self):
        table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        text = f"### Heading\n{table}\nNext sentence."
        chunks = split_mattermost_message(text, 4000)
        self.assertEqual(len(chunks), 1)
        self.assertIn("### Heading\n\n| A | B |", chunks[0])
        self.assertIn("| 1 | 2 |\n\nNext sentence.", chunks[0])

    def test_does_not_glue_continuation_onto_table_separator(self):
        header = "| Rank | Agency ID | Name | Bucket | One-line reason |\n|---|---|---|---|---|"
        rows = "\n".join(
            "| **Primary** | PMC{0:09d} | NAME {0} | **Recommended** | "
            "Only completed university graduate in the packet with extra padding. |".format(i)
            for i in range(12)
        )
        chinese = _chinese(2200)
        english = (
            "## English\n\n"
            + _english(400)
            + "\n\n### 1. Primary and ranked alternates (one-line reasons)\n\n"
            f"{header}\n{rows}"
        )
        text = f"{chinese}\n\n---\n\n{english}"
        chunks = split_mattermost_message(text, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)
            self.assertIsNone(
                __import__("re").search(r"\|-+\| \(\d+/\d+\)", chunk),
                msg=chunk[-80:],
            )
            last = chunk.rstrip().splitlines()[-1]
            if last.startswith("(") and "/" in last:
                continue
            if last.startswith("|"):
                self.assertTrue(last.rstrip().endswith("|"), msg=repr(last))

    def test_continuation_marker_is_own_line(self):
        msg = "a " * 2500
        chunks = split_mattermost_message(msg, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        for index, chunk in enumerate(chunks, start=1):
            self.assertTrue(
                chunk.rstrip().endswith(f"({index}/{len(chunks)})"),
                msg=repr(chunk[-40:]),
            )
            self.assertNotIn(f" a ({index}/{len(chunks)})", chunk)

    def test_keeps_distinct_tables_separated_after_packing(self):
        first = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        second = "| C | D |\n| --- | --- |\n| 3 | 4 |"
        text = f"Intro\n\n{first}\n\n{second}\n\n{_english(5000)}"
        chunks = split_mattermost_message(text, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("| 1 | 2 |\n\n| C | D |", "\n".join(chunks))
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

    def test_alignment_separators_repeat_header(self):
        header = "| Name | Qty |\n| :---: | ---: |"
        rows = "\n".join(f"| item-{i:02d} | {i} |" for i in range(40))
        chunks = split_mattermost_message(f"{header}\n{rows}", 220)
        data_chunks = [chunk for chunk in chunks if "item-" in chunk]
        self.assertGreaterEqual(len(data_chunks), 2)
        for chunk in data_chunks:
            self.assertLessEqual(len(chunk), 220)
            self.assertIn("| Name | Qty |", chunk)
            self.assertIn("| :---: | ---: |", chunk)

    def test_left_and_right_alignment_is_isolated(self):
        text = "### Heading\n| Name | Qty |\n| :--- | ---: |\n| a | 1 |"
        chunks = split_mattermost_message(text, 4000)
        self.assertEqual(len(chunks), 1)
        self.assertIn("### Heading\n\n| Name | Qty |", chunks[0])
        self.assertIn("| :--- | ---: |\n| a | 1 |", chunks[0])

    def test_long_reply_isolates_heading_from_table(self):
        table = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        text = f"### Heading\n{table}\n{_english(5000)}"
        chunks = split_mattermost_message(text, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        found = False
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)
            if "| A | B |" not in chunk:
                continue
            found = True
            self.assertIn("### Heading\n\n| A | B |", chunk)
            self.assertIn("| 1 | 2 |\n\n", chunk)
            last = chunk.rstrip().splitlines()[-1]
            self.assertTrue(last.startswith("(") and "/" in last, msg=repr(last))
        self.assertTrue(found)

    def test_several_tables_stay_within_limit(self):
        tables = [
            f"| H{i} | V |\n| --- | --- |\n| r{i} | {i} |"
            for i in range(6)
        ]
        text = "\n\n".join(tables) + "\n\n" + _english(4500)
        chunks = split_mattermost_message(text, 4000)
        self.assertGreaterEqual(len(chunks), 2)
        blob = "\n".join(chunks)
        for index in range(5):
            self.assertIn(
                f"| r{index} | {index} |\n\n| H{index + 1} | V |",
                blob,
            )
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 4000)

    def test_reopens_fence_when_code_block_exceeds_budget(self):
        fence = "```python\n" + ("print('x')\n" * 80) + "```"
        chunks = split_mattermost_message(fence, 400)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 400)
            lines = chunk.rstrip().splitlines()
            if lines and lines[-1].startswith("(") and "/" in lines[-1]:
                lines = lines[:-1]
            code = "\n".join(lines).strip()
            self.assertTrue(code.startswith("```"), msg=repr(code[:40]))
            self.assertTrue(code.endswith("```"), msg=repr(code[-40:]))
            self.assertEqual(code.count("```") % 2, 0)


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

    def test_max_post_length_is_not_raised(self):
        from plugins.platforms.mattermost.adapter import MAX_POST_LENGTH

        self.assertLessEqual(MAX_POST_LENGTH, 4000)


if __name__ == "__main__":
    unittest.main()
