import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.database import fetch_all_llm_rows, update_skill_score

DEFAULT_SKILL_WEIGHT = 0.5
SCORE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "score_config.json"

def _normalize_weight_map(data: Any) -> Dict[str, float]:
    if not isinstance(data, dict):
        return {}

    weights: Dict[str, float] = {}
    for skill_name, value in data.items():
        if isinstance(skill_name, str) and isinstance(value, (int, float)):
            key = skill_name.strip().lower()  # normalized to lowercase keys for case-insensitive matching
            if key:
                weights[key] = float(value)

    return weights

# loads a score config with optional "skills" and "tools" sections
def load_score_config(config_path: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    path = Path(config_path) if config_path else SCORE_CONFIG_PATH

    if not path.exists():
        return {"skills": {}, "tools": {}}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid configuration file: {path}") from error

    if not isinstance(data, dict):
        raise ValueError(f"The configuration file must contain a JSON object: {path}")

    if "skills" in data or "tools" in data:
        skills = _normalize_weight_map(data.get("skills", {}))
        tools = _normalize_weight_map(data.get("tools", {}))
    else:
        skills = _normalize_weight_map(data)
        tools = {}

    return {"skills": skills, "tools": tools}

# returns only skill weights for backward compatibility
def load_skill_weights(config_path: Optional[str] = None) -> Dict[str, float]:
    return load_score_config(config_path).get("skills", {})

# returns only tool weights from the config
def load_tool_weights(config_path: Optional[str] = None) -> Dict[str, float]:
    return load_score_config(config_path).get("tools", {})

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

# checks the feature tools section of the LLM output and returns a list of tool names
def get_tools_from_llm_output(llm_output: dict) -> List[str]:
    if not isinstance(llm_output, dict):
        return []

    feature_tools = llm_output.get("feature_index", {}).get("tools")
    if isinstance(feature_tools, list):
        return [tool for tool in feature_tools if isinstance(tool, str)]

    return []

# calculates the total months of experience for each skill mentioned in the LLM output
def get_experience_skill_months(llm_output: dict) -> Dict[str, float]:
    experience = llm_output.get("parsed_data", {}).get("experience")
    if not isinstance(experience, list):
        return {}

    skill_months: Dict[str, float] = {}
    for entry in experience:
        if not isinstance(entry, dict):
            continue

        raw_skill = entry.get("main_highlighted_skill")
        raw_duration = entry.get("duration")

        if not isinstance(raw_skill, str):
            continue

        normalized_skill = raw_skill.strip().lower()
        if not normalized_skill:
            continue

        duration_months = None
        if isinstance(raw_duration, (int, float)):
            duration_months = float(raw_duration)
        elif isinstance(raw_duration, str) and raw_duration.strip().isdigit():
            duration_months = float(raw_duration.strip())

        if duration_months is None or duration_months <= 0:
            continue

        skill_months[normalized_skill] = skill_months.get(normalized_skill, 0.0) + duration_months

    return skill_months

# scores for the dimensions in the LLM output and returns the sum of the scores
def get_dimension_score_sum(llm_output: dict) -> float:
    dimension_scores = llm_output.get("dimension_scores", {})
    if not isinstance(dimension_scores, dict):
        return 0.0

    total = 0.0
    for field in [
        "education_level",
        "role_fit_score",
        "domain_diversity",
        "certifications",
        "career_progression",
    ]:
        value = dimension_scores.get(field)
        if isinstance(value, (int, float)):
            total += float(value)

    return total

# applies a penalty when the role fit score is less than or equal to 5.0
def get_role_fit_penalty(llm_output: dict) -> float:
    dimension_scores = llm_output.get("dimension_scores", {})
    if not isinstance(dimension_scores, dict):
        return 0.0

    role_fit_score = dimension_scores.get("role_fit_score")
    if isinstance(role_fit_score, (int, float)) and float(role_fit_score) <= 5.0:
        return -30.0

    return 0.0

# score for language skills based on the number of languages listed in the LLM output
def get_language_bonus(llm_output: dict) -> float:
    languages = llm_output.get("feature_index", {}).get("languages")
    if not isinstance(languages, list):
        return 0.0

    return float(
        sum(
            1
            for item in languages
            if isinstance(item, dict)
            and isinstance(item.get("language"), str)
            and item.get("language").strip()
        )
    )

# calculates a penalty based on the hard skills gap in the LLM output and the skill weights from the configuration
def get_hard_skills_gap_penalty(
    llm_output: dict,
    overrides: Dict[str, float],
) -> float:
    dimension_scores = llm_output.get("dimension_scores", {})
    if not isinstance(dimension_scores, dict):
        return 0.0

    hard_skills_gap = dimension_scores.get("hard_skills_gap")
    if not isinstance(hard_skills_gap, list):
        return 0.0

    penalty = 0.0
    seen: set[str] = set()
    for skill in hard_skills_gap:
        if not isinstance(skill, str):
            continue

        normalized_skill = skill.strip().lower()
        if not normalized_skill or normalized_skill in seen:
            continue

        seen.add(normalized_skill)
        if normalized_skill in overrides:
            penalty -= float(overrides[normalized_skill])
        else:
            penalty -= 1.0

    return penalty

# main functions
def calculate_skill_score(
    llm_output: dict,
    config_path: Optional[str] = None,
    default_weight: float = DEFAULT_SKILL_WEIGHT,
    score_config_override: Optional[dict] = None,
) -> float:
    skills = get_skills_from_llm_output(llm_output)
    tools = get_tools_from_llm_output(llm_output)

    if score_config_override is not None:
        skill_overrides = _normalize_weight_map(score_config_override.get("skills", {}))
        tool_overrides = _normalize_weight_map(score_config_override.get("tools", {}))
    else:
        skill_overrides = load_skill_weights(config_path)
        tool_overrides = load_tool_weights(config_path)

    experience_skill_months = get_experience_skill_months(llm_output)

    total_score = 0.0

    for skill in skills:
        normalized_skill = skill.strip().lower()
        if not normalized_skill:
            continue

        skill_weight = skill_overrides.get(normalized_skill, default_weight)
        total_score += skill_weight

        if normalized_skill in skill_overrides and normalized_skill in experience_skill_months:
            total_score += 1.0 + (experience_skill_months[normalized_skill] / 12.0)

    for tool in tools:
        normalized_tool = tool.strip().lower()
        if not normalized_tool:
            continue

        total_score += tool_overrides.get(normalized_tool, default_weight)

    total_score += get_dimension_score_sum(llm_output)
    total_score += get_role_fit_penalty(llm_output)
    total_score += get_language_bonus(llm_output)
    total_score += get_hard_skills_gap_penalty(llm_output, skill_overrides)

    return total_score

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


# ─── Funzioni per API ───────────────────────────────

def calculate_skill_score_breakdown(
    llm_output: dict,
    config_path: Optional[str] = None,
    default_weight: float = DEFAULT_SKILL_WEIGHT,
    score_config_override: Optional[dict] = None,
) -> dict:
    """Calcola e restituisce il dettaglio completo del punteggio."""
    skills = get_skills_from_llm_output(llm_output)
    tools = get_tools_from_llm_output(llm_output)

    if score_config_override is not None:
        skill_overrides = _normalize_weight_map(score_config_override.get("skills", {}))
        tool_overrides = _normalize_weight_map(score_config_override.get("tools", {}))
    else:
        skill_overrides = load_skill_weights(config_path)
        tool_overrides = load_tool_weights(config_path)

    experience_skill_months = get_experience_skill_months(llm_output)

    skill_score_total = 0.0
    skills_breakdown = []

    for skill in skills:
        normalized_skill = skill.strip().lower()
        if not normalized_skill:
            continue

        skill_weight = skill_overrides.get(normalized_skill, default_weight)
        skill_score_total += skill_weight
        exp_bonus = 0.0

        if normalized_skill in skill_overrides and normalized_skill in experience_skill_months:
            exp_bonus = 1.0 + (experience_skill_months[normalized_skill] / 12.0)
            skill_score_total += exp_bonus

        skills_breakdown.append({
            "skill": normalized_skill,
            "weight": skill_weight,
            "experience_bonus": round(exp_bonus, 2),
            "total": round(skill_weight + exp_bonus, 2),
        })

    tools_score = 0.0
    for tool in tools:
        normalized_tool = tool.strip().lower()
        if not normalized_tool:
            continue
        tools_score += tool_overrides.get(normalized_tool, default_weight)

    dimension_sum = get_dimension_score_sum(llm_output)
    role_fit_penalty = get_role_fit_penalty(llm_output)
    language_bonus = get_language_bonus(llm_output)
    hard_skills_gap_penalty = get_hard_skills_gap_penalty(llm_output, skill_overrides)

    total_score = (
        skill_score_total
        + tools_score
        + dimension_sum
        + role_fit_penalty
        + language_bonus
        + hard_skills_gap_penalty
    )

    # Skills mancanti (hard skills gap)
    dimension_scores = llm_output.get("dimension_scores", {})
    missing_skills = []
    if isinstance(dimension_scores, dict):
        gap = dimension_scores.get("hard_skills_gap")
        if isinstance(gap, list):
            missing_skills = [s for s in gap if isinstance(s, str)]

    return {
        "total_score": round(total_score, 2),
        "components": {
            "skills": round(skill_score_total, 2),
            "tools": round(tools_score, 2),
            "dimension_scores_sum": round(dimension_sum, 2),
            "role_fit_penalty": round(role_fit_penalty, 2),
            "language_bonus": round(language_bonus, 2),
            "hard_skills_gap_penalty": round(hard_skills_gap_penalty, 2),
        },
        "skills_breakdown": skills_breakdown,
        "missing_skills": missing_skills,
        "config_used": {
            "skills": skill_overrides,
            "tools": tool_overrides,
        },
    }


def save_score_config(config_data: dict, config_path: Optional[str] = None) -> None:
    """Salva la configurazione dei pesi su disco."""
    path = Path(config_path) if config_path else SCORE_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if not isinstance(config_data, dict):
        raise ValueError("La configurazione deve essere un oggetto JSON")

    existing = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            existing = json.load(f)

    if "skills" in config_data:
        existing["skills"] = config_data["skills"]
    if "tools" in config_data:
        existing["tools"] = config_data["tools"]

    with path.open("w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
