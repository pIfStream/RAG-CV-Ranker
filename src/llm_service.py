import json
from ollama import Client
from src.config import OLLAMA_HOST, OLLAMA_LOCAL_HOST, OLLAMA_TOKEN, LLM_MODEL
from src.schemas import CVJSONSchema

def _get_ollama_client():
    return Client(
        host=OLLAMA_HOST,
        headers={'Authorization': f'Bearer {OLLAMA_TOKEN}'}
    )

def _get_ollama_local_client():
    return Client(
        host=OLLAMA_LOCAL_HOST,
    )

def analize_cv_via_llm(parsed_cv_data: str) -> dict:
    #client = _get_ollama_client() # cloud client for testing purposes
    client = _get_ollama_local_client()


    instructions = (
        "Extract the CV data into the specified JSON schema. "
        "Do not alter the structure of the schema and only fill with what's available from the resume. "
        "Do not include any conversational text, preamble, or markdown blocks. "
        "Focus on accuracy for 'dimension_scores' (0.0-10.0)"
    )
    prompt = f"{instructions}\n\n{parsed_cv_data}"
    format_schema = CVJSONSchema.model_json_schema()

    response = client.chat(
        model=LLM_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        format=format_schema
    )
    
    return json.loads(response.message.content)