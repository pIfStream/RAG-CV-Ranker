import json
from ollama import Client
from pydantic import ValidationError
from src.config import OLLAMA_HOST, OLLAMA_LOCAL_HOST, OLLAMA_TOKEN, LLM_MODEL
from src.schemas import CVJSONSchema
from src.rag_service import build_rag_query_engine, retrieve_relevant_context

def _get_ollama_client():
    return Client(
        host=OLLAMA_HOST,
        headers={'Authorization': f'Bearer {OLLAMA_TOKEN}'}
    )

def _get_ollama_local_client():
    return Client(
        host=OLLAMA_LOCAL_HOST,
    )

def analize_cv_via_llm(parsed_cv_data: str, reference_context: str | None = None) -> dict:
    #client = _get_ollama_client() # cloud client for testing purposes
    client = _get_ollama_local_client()


    instructions = (
        "Extract the CV data into the specified JSON schema."
        "Do not alter the structure of the schema and only fill with what's available from the resume. "
        "Do not include any conversational text, preamble, or markdown blocks. "
        "Focus on accuracy for 'dimension_scores' (0.0-10.0)"
        "You will be analysing data looking for data-analyst role, evaluate accordingly. "
    )

    prompt = instructions
    # include reference context from RAG retrieval
    if reference_context:
        prompt += f"\n\nReference CV knowledge:\n{reference_context}"

    prompt += f"\n\nCurrent CV:\n{parsed_cv_data}"

    format_schema = CVJSONSchema.model_json_schema()

    response = client.chat(
        model=LLM_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        format=format_schema
    )
    
    raw_content = response.message.content
    try:
        # pydantic validation to ensure the LLM output adheres to the schema
        validated_schema = CVJSONSchema.model_validate_json(raw_content)

        return validated_schema.model_dump() # return a dict from the pydantic model

    except ValidationError as e:  # catching validation errors from pydantic
        print(f"Error validating schema: {e}")
        raise ValueError("LLM output did not conform to the expected schema.") from e
    
    except json.JSONDecodeError as e: # catching JSON parsing errors
        print(f"Error decoding JSON: {e}")
        raise ValueError("LLM output was not valid JSON.") from e