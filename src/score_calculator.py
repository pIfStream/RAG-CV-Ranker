import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.database import fetch_all_llm_rows, update_skill_score

DEFAULT_SKILL_WEIGHT = 0.5
SCORE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "score_config.json"

# creates a dictionary of skill weights from the json file
def load_skill_weights(config_path: Optional[str] = None) -> Dict[str, float]:

    path = Path(config_path) if config_path else SCORE_CONFIG_PATH

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid configuration file: {path}") from error

    if not isinstance(data, dict):
        raise ValueError(f"The configuration file must contain a JSON object: {path}")

    # storage for skill weights
    weights: Dict[str, float] = {}
    for skill_name, value in data.items():
        if isinstance(skill_name, str) and isinstance(value, (int, float)):
            key = skill_name.strip().lower() # normalized to lowercase keys for case-insensitive matching
            if key:
                weights[key] = float(value)

    return weights

# checks the feature skills section of the LLM output and returns a list of skill names
def get_skills_from_llm_output(llm_output: dict) -> List[str]:
    if not isinstance(llm_output, dict):
        return []

    feature_skills = llm_output.get("feature_index", {}).get("skills")
    if isinstance(feature_skills, list):
        return [skill for skill in feature_skills if isinstance(skill, str)]

    """
    top_skills = llm_output.get("candidate_profile", {}).get("top_skills")
    if isinstance(top_skills, list):
        return [skill for skill in top_skills if isinstance(skill, str)]
    """

    return []

def calculate_skill_score(
    llm_output: dict,
    config_path: Optional[str] = None,
    default_weight: float = DEFAULT_SKILL_WEIGHT,
) -> float:
    skills = get_skills_from_llm_output(llm_output)
    if not skills:
        return 0.0

    # apply score overrides if available
    overrides = load_skill_weights(config_path)
    total_score = 0.0

    for skill in skills:
        normalized_skill = skill.strip().lower()
        if not normalized_skill:
            continue

        skill_weight = overrides.get(normalized_skill, default_weight)
        total_score += skill_weight

    return total_score

# main function
def calculate_skill_score_from_json_file(
    json_file_path: str,
    config_path: Optional[str] = None,
    default_weight: float = DEFAULT_SKILL_WEIGHT,
) -> float:
    path = Path(json_file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {json_file_path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            llm_output = json.load(f)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON file: {json_file_path}") from error
        
    return calculate_skill_score(llm_output, config_path=config_path, default_weight=default_weight)


def recalculate_skill_scores_in_db() -> int:
    rows = fetch_all_llm_rows()
    updated = 0

    for cv_id, llm_data in rows:
        if isinstance(llm_data, str):
            try:
                llm_data = json.loads(llm_data)
            except json.JSONDecodeError:
                llm_data = {}

        score = calculate_skill_score(
            llm_data if isinstance(llm_data, dict) else {},
            config_path=SCORE_CONFIG_PATH,
            default_weight=DEFAULT_SKILL_WEIGHT,
        )
        update_skill_score(cv_id, score)
        updated += 1

    return updated


def main() -> int:
    try:
        updated_count = recalculate_skill_scores_in_db()
        print(f"Updated {updated_count} entries in the database.")
        return 0
    except Exception as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
