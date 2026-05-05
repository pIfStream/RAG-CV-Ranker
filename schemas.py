from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# --- Substructures ---

class Metadata(BaseModel):
    ingestion_date: str = Field(description="ISO 8601 processing timestamp")

class CandidateProfile(BaseModel):
    current_role: str
    total_years_exp: float
    education_level: str
    top_skills: List[str]

class LanguageSkill(BaseModel):
    language: str = Field(description="Language name (e.g., italian, english)")
    level: str = Field(description="Proficiency level (CEFR levels: A1, A2, B1, B2, C1, C2, Native, or NA if not specified")

class FeatureIndex(BaseModel):
    skills: List[str] = Field(description="Normalized list of skills including synonyms in lowercase for exact matching (e.g, java, k8s)")
    domains: List[str] = Field(description="Industry sectors (e.g., fintech, b2b)")
    seniority: str = Field(description="Normalized level: junior, mid, senior, lead")
    certifications: List[str]
    languages: List[LanguageSkill]

class DimensionScores(BaseModel):
    years_of_experience: float = Field(ge=0, le=10)
    education_level: float = Field(ge=0, le=10)
    skills_breadth: float = Field(ge=0, le=10)
    career_progression: float = Field(ge=0, le=10)
    certifications: float = Field(ge=0, le=10)
    domain_diversity: float = Field(ge=0, le=10)

class WorkExperience(BaseModel):
    company: str
    role: str
    duration: str
    highlights: str

class Education(BaseModel):
    institution: str
    degree: str
    year: int

class ParsedData(BaseModel):
    experience: List[WorkExperience]
    education: List[Education]

# --- Main Structure ---

class CVJSONSchema(BaseModel):
    cv_id: str
    metadata: Metadata
    candidate_profile: CandidateProfile
    feature_index: FeatureIndex
    dimension_scores: DimensionScores
    parsed_data: ParsedData