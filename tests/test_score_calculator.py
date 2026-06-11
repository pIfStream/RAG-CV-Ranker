import json
import os
import tempfile
import unittest
from pathlib import Path

from src.score_calculator import calculate_skill_score, calculate_skill_score_from_json_file, load_skill_weights


class TestScoreCalculator(unittest.TestCase):
    def setUp(self):
        self.sample_output = {
            "feature_index": {
                "skills": ["Python", "SQL", "Machine Learning"]
            }
        }

    def test_calculate_default_weight(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_config = Path(tmpdir) / "missing_config.json"
            score = calculate_skill_score(self.sample_output, config_path=str(missing_config))
            self.assertEqual(score, 0.5 * 3)

    def test_calculate_with_config_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps({"python": 1.0, "sql": 1.5}), encoding="utf-8")

            score = calculate_skill_score(self.sample_output, config_path=str(config_path))
            self.assertEqual(score, 1.0 + 1.5 + 0.5)

    def test_calculate_with_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "output.json"
            json_path.write_text(json.dumps(self.sample_output), encoding="utf-8")

            missing_config = Path(tmpdir) / "missing_config.json"
            score = calculate_skill_score_from_json_file(str(json_path), config_path=str(missing_config))
            self.assertEqual(score, 0.5 * 3)

    def test_load_skill_weights_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("not valid json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_skill_weights(str(config_path))


if __name__ == "__main__":
    unittest.main()
