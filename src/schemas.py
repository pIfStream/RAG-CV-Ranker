from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

# --- Substructures ---

class CandidateData(BaseModel):
    name: str
    age: Optional[int]
    email: Optional[str]
    phone: Optional[str]


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
    tools: List[str] = Field(description="Normalized list of tools including synonyms in lowercase for exact matching (e.g., git, docker, jenkins)")
    domains: List[str] = Field(description="Industry sectors (e.g., fintech, b2b)")
    seniority: str = Field(description="Normalized level: junior, mid, senior, lead")
    certifications: List[str] = Field(description="List of certifications (e.g., AWS Certified, PMP)")
    languages: List[LanguageSkill]

class DimensionScores(BaseModel):
    main_cv_role: str = Field(description="The primary role identified from the CV (e.g., software engineer, data scientist)")
    education_level: float = Field(ge=0, le=10, description="A score representing the education level, normalized to a 0-10 scale (e.g., high school=2, bachelor's=5, master's=7, PhD=10)")
    career_progression: float = Field(ge=0, le=10, description="A score representing career progression, normalized to a 0-10 scale")
    certifications: float = Field(ge=0, le=10)
    domain_diversity: float = Field(ge=0, le=10)
    role_fit_score: float = Field(ge=0, le=10, description="A score representing how well the CV matches the target role based on skills, experience, and other factors")
    hard_skills_gap: List[str] = Field(description="List of important hard skills mentioned in the job description but missing from the CV")

class WorkExperience(BaseModel):
    company: str
    role: str
    duration: int = Field(description="Duration in months")
    main_highlighted_skill: str = Field(description="The most important skill in this experience, normalized in lowercase for exact matching")

class Education(BaseModel):
    institution: str
    degree: str
    year: int

class ParsedData(BaseModel):
    experience: List[WorkExperience]
    education: List[Education]

# --- Main Structure ---

class CVJSONSchema(BaseModel):
    candidate_data: CandidateData
    candidate_profile: CandidateProfile
    feature_index: FeatureIndex
    dimension_scores: DimensionScores
    parsed_data: ParsedData