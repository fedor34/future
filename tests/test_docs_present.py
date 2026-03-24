from __future__ import annotations

import unittest
from pathlib import Path


class DocsPresenceTest(unittest.TestCase):
    def test_project_concept_docs_exist(self) -> None:
        concept_dir = Path("docs/project-concept")
        self.assertTrue((concept_dir / "README.md").exists())
        self.assertTrue((concept_dir / "principles.md").exists())


if __name__ == "__main__":
    unittest.main()
