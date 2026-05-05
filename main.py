import tkinter as tk
from tkinter import filedialog
from docling.document_converter import DocumentConverter
from ollama import Client
from schemas import CVJSONSchema
import os


# apre finestra e ritorna path del file
def open_cv_file():

    root = tk.Tk()
    root.withdraw() 
    root.attributes('-topmost', True)

    file_path = filedialog.askopenfilename(
        title="Seleziona il CV da analizzare",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    
    root.destroy()
    
    return file_path

path_cv = open_cv_file()

if path_cv:
    print(f"Selected file: {os.path.basename(path_cv)}")
    print("parsing")
    
    try:
        converter = DocumentConverter()
        result = converter.convert(path_cv)
        parsed_cv_data = result.document.export_to_markdown()

        with open("parsed_cv_output.md", "w", encoding="utf-8") as f:
            f.write(parsed_cv_data)

        print("parsed data written on file")
        
    except Exception as e:
        print(f"Errore: {e}")
else:
    print("No file selected.")

# secondo parsing con LLM, ritorno data in list del cv
if parsed_cv_data:
    print("Sending rerquest to LLM")

    client = Client(
        host='https://ollama.com',
        headers={
            'Authorization': f'Bearer 528a2bfc224749ccbcc972b217c649e4.F9oSaaBD1w1Ac1bxa6WOdBSc'
        }
    )

    # preparazione prompt + inizializzazione schema json
    instructions = (
        "Extract the CV data into the specified JSON schema"
        "Do not alter the structure of the schema and only fill with what's available from the resume"
        "Do not include any conversational text, preamble, or markdown blocks. "
        "Focus on accuracy for 'dimension_scores' (0.0-10.0)"
    )
    prompt = f"{instructions}\n\n{parsed_cv_data}"
    format_schema = CVJSONSchema.model_json_schema()

    try:
        response = client.chat(
            model = 'gemma4:31b-cloud',
            messages = [
                {'role': 'user', 'content': prompt}
            ],
            format = format_schema
        )
        with open("llm_response.md", "w", encoding="utf-8") as f:
            f.write(response.message.content)

        print(response['message']['content'])

    except Exception as e:
        print(f"API call error: {e}")

