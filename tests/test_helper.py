import unittest

from tests.docs_metadata_helper import parse_front_matter


class ParseFrontMatterTest(unittest.TestCase):
    def test_parses_readable_front_matter_example(self) -> None:
        sample_doc = """---
title: "Example Document"
status: draft
depends_on:
  - "overview.md"
  - "runtime-model.md"
citations_used:
  - "S7"
  - "S8"
---

# Example Document

Body text goes here.
"""

        expected = {
            "title": "Example Document",
            "status": "draft",
            "depends_on": ["overview.md", "runtime-model.md"],
            "citations_used": ["S7", "S8"],
        }

        self.assertEqual(parse_front_matter(sample_doc), expected)

    def test_parses_empty_list_values_clearly(self) -> None:
        sample_doc = """---
title: "Index Page"
status: index
depends_on: []
citations_used: []
---

# Index Page
"""

        expected = {
            "title": "Index Page",
            "status": "index",
            "depends_on": [],
            "citations_used": [],
        }

        self.assertEqual(parse_front_matter(sample_doc), expected)

    def test_rejects_missing_opening_delimiter(self) -> None:
        sample_doc = """title: "Broken Document"
status: stub
"""

        with self.assertRaisesRegex(ValueError, "missing YAML front matter"):
            parse_front_matter(sample_doc)

    def test_rejects_unterminated_front_matter(self) -> None:
        sample_doc = """---
title: "Broken Document"
status: stub
"""

        with self.assertRaisesRegex(ValueError, "unterminated YAML front matter"):
            parse_front_matter(sample_doc)


if __name__ == "__main__":
    unittest.main()
