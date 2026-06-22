import json
import os
import tempfile
import unittest
from pathlib import Path

from src.score_calculator import (
    calculate_skill_score,
    calculate_skill_score_from_json_file,
    load_score_config,
    load_skill_weights,
    load_tool_weights,
)


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
            config_path.write_text(json.dumps({"skills": {"python": 1.0, "sql": 1.5}}), encoding="utf-8")

            score = calculate_skill_score(self.sample_output, config_path=str(config_path))
            self.assertEqual(score, 1.0 + 1.5 + 0.5)

    def test_calculate_with_json_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "output.json"
            json_path.write_text(json.dumps(self.sample_output), encoding="utf-8")

            missing_config = Path(tmpdir) / "missing_config.json"
            score = calculate_skill_score_from_json_file(str(json_path), config_path=str(missing_config))
            self.assertEqual(score, 0.5 * 3)

    def test_load_score_config_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"skills": {"python": 1.0}, "tools": {"docker": 2.0}}),
                encoding="utf-8",
            )
            config = load_score_config(str(config_path))
            self.assertEqual(config["skills"], {"python": 1.0})
            self.assertEqual(config["tools"], {"docker": 2.0})

    def test_calculate_with_tool_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"tools": {"docker": 2.5}}),
                encoding="utf-8",
            )

            llm_output = {
                "feature_index": {
                    "skills": [],
                    "tools": ["Docker"],
                },
                "dimension_scores": {},
                "parsed_data": {"experience": []},
            }

            score = calculate_skill_score(llm_output, config_path=str(config_path))
            self.assertEqual(score, 2.5)

    def test_calculate_with_dimension_scores_language_and_gap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"skills": {"python": 1.0, "sql": 1.5, "excel": 0.75}}),
                encoding="utf-8",
            )

            llm_output = {
                "feature_index": {
                    "skills": ["Python", "SQL", "Excel"],
                    "languages": [
                        {"language": "Italiano", "level": "C1"},
                        {"language": "English", "level": "C2"},
                    ],
                },
                "dimension_scores": {
                    "education_level": 4.0,
                    "role_fit_score": 8.0,
                    "domain_diversity": 2.0,
                    "certifications": 1.0,
                    "career_progression": 5.0,
                    "hard_skills_gap": ["excel", "docker"],
                },
                "parsed_data": {
                    "experience": [
                        {
                            "company": "ACME",
                            "role": "Developer",
                            "duration": 24,
                            "main_highlighted_skill": "Python",
                        }
                    ]
                },
            }

            score = calculate_skill_score(llm_output, config_path=str(config_path))
            expected = 6.25 + 20.0 + 2.0 - 1.75
            self.assertEqual(score, expected)

    def test_calculate_with_tool_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"tools": {"docker": 2.5}}),
                encoding="utf-8",
            )

            llm_output = {
                "feature_index": {
                    "skills": [],
                    "tools": ["Docker"],
                },
                "dimension_scores": {},
                "parsed_data": {"experience": []},
            }

            score = calculate_skill_score(llm_output, config_path=str(config_path))
            self.assertEqual(score, 2.5)

    def test_low_role_fit_score_applies_penalty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps({"skills": {"python": 1.0, "sql": 1.5, "excel": 0.75}}),
                encoding="utf-8",
            )

            llm_output = {
                "feature_index": {
                    "skills": ["Python", "SQL", "Excel"],
                    "languages": [
                        {"language": "Italiano", "level": "C1"},
                        {"language": "English", "level": "C2"},
                    ],
                },
                "dimension_scores": {
                    "education_level": 4.0,
                    "role_fit_score": 3.0,
                    "domain_diversity": 2.0,
                    "certifications": 1.0,
                    "career_progression": 5.0,
                    "hard_skills_gap": ["excel", "docker"],
                },
                "parsed_data": {
                    "experience": [
                        {
                            "company": "ACME",
                            "role": "Developer",
                            "duration": 24,
                            "main_highlighted_skill": "Python",
                        }
                    ]
                },
            }

            score = calculate_skill_score(llm_output, config_path=str(config_path))
            expected = 6.25 + 15.0 + 2.0 - 1.75 - 30.0
            self.assertEqual(score, expected)

    def test_load_skill_weights_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("not valid json", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_skill_weights(str(config_path))


if __name__ == "__main__":
    unittest.main()
