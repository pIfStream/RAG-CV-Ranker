from src.parser import extract_text_from_file, get_local_file_via_ui
from src.llm_service import analize_cv_via_llm


file_path: str = get_local_file_via_ui()
extracted_text = None


if file_path:
    try:
        # parsing
        extracted_text = extract_text_from_file(file_path)
        print("Parsing complete. Extracted text in test/raw_text.txt")
        # saving to file
        with open("tests/raw_text.txt", "w", encoding="utf-8") as f:
            f.write(extracted_text)

    except Exception as e:
        print(f"Error while parsing file: {e}")

if extracted_text:
    try:
        # LLM analysis
        result = analize_cv_via_llm(extracted_text)
        print("LLM analysis complete. Result in test/llm_result.txt")
        # saving to file
        with open("tests/llm_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
    except Exception as e:
        print(f"Error while analyzing CV with LLM: {e}")