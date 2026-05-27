import os
from src.config import IS_DOCKER
from src.parser import extract_text_from_file, get_local_file_via_ui
from src.llm_service import analize_cv_via_llm
from src.database import initialize_database, insert_cv_data

# full pipeline for single file
def elaborate_single_cv(file_path: str):

    try:
        raw_text = extract_text_from_file(file_path)
        print("sending CV data to LLM for analysis...")

        json_data = analize_cv_via_llm(raw_text)
        print("inserting CV data into database...")

        id_db = insert_cv_data(file_path, raw_text, json_data)
        print(f"CV data inserted into database with ID: {id_db}\n")
    
    except Exception as e:
        print(f"Error processing CV: {e}\n")

def main():
    try:
        initialize_database()
    except Exception as e:
        print(f"Error initializing database: {e}")
        return
    
    if not IS_DOCKER:  # local mode, single file selected from ui
        print("Running in local mode. Select a CV file to process.")
        file_path = get_local_file_via_ui()
        if file_path:
            elaborate_single_cv(file_path)
        else:
            print("No file selected. Exiting.")

    else:        # Docker mode, process all files in /data directory
        print("Running in Docker mode. Processing all CV files in /cv_storage directory.")
        cv_directory = "/cv_storage"

        if not os.path.exists(cv_directory):
            print(f"Directory {cv_directory} does not exist. Exiting.")
            return
        
        presence_of_files = False
        for filename in os.listdir(cv_directory):
            if filename.lower().endswith(('.pdf', '.docx', '.txt')):
                presence_of_files = True
                file_path = os.path.join(cv_directory, filename)
                print(f"Processing file: {file_path}")
                elaborate_single_cv(file_path)

        if not presence_of_files:
            print("No valid CV files found in the directory.")

if __name__ == "__main__":
    main()