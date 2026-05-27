import os

# Ollama config
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "528a2bfc224749ccbcc972b217c649e4.F9oSaaBD1w1Ac1bxa6WOdBSc")
OLLAMA_LOCAL_HOST = os.getenv("OLLAMA_LOCAL_HOST", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4:latest")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "nomic-embed-text")

# PostgreSQL config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://myuser:mypassword@localhost:5432/cv_db")

# Docker flag
IS_DOCKER = os.getenv("IS_DOCKER", "false").lower() == "true"