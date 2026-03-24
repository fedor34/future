from __future__ import annotations

import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from future_news_forecaster.settings import current_openai_api_key, save_openai_api_key


class SettingsTest(unittest.TestCase):
    def test_api_key_roundtrip_in_env_file(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            with TemporaryDirectory() as tmp_dir:
                env_path = Path(tmp_dir) / ".env"
                save_openai_api_key("test-key-123", env_path=env_path)
                self.assertEqual(current_openai_api_key(env_path=env_path), "test-key-123")
                self.assertTrue(env_path.exists())


if __name__ == "__main__":
    unittest.main()
