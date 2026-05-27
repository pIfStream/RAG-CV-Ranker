import os
import tkinter as tk
from tkinter import filedialog
from docling.document_converter import DocumentConverter

# extracts text from a file and returns it as a string
def extract_text_from_file(file_path: str) -> str:
    print(f"Avvio parsing del file: {os.path.basename(file_path)}")
    converter = DocumentConverter()
    result = converter.convert(file_path)
    return result.document.export_to_markdown()

# helper function to open a file dialog and get the path of the selected file
def get_local_file_via_ui() -> str:
    
    root = tk.Tk()
    root.withdraw() 
    root.attributes('-topmost', True)

    file_path = filedialog.askopenfilename(
        title="Seleziona il CV da analizzare",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    root.destroy()
    return file_path
