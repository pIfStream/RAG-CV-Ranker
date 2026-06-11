import os
import shutil
from src.parser import extract_text_from_file, get_local_file_via_ui
from src.llm_service import analize_cv_via_llm
from src.database import initialize_database, insert_cv_data
from src.rag_service import build_rag_query_engine, retrieve_relevant_context
from src.score_calculator import calculate_skill_score

# variable to determine wether the application will process a single file selected via UI 
# or all files in a directory 
manual_mode = False

# full pipeline for single file
def elaborate_single_cv(file_path: str, rag_engine=None) -> bool:
    try:
        raw_text = extract_text_from_file(file_path)
        print("sending CV data to LLM for analysis...")

        reference_context = None
        if rag_engine is not None:
            reference_context = retrieve_relevant_context(rag_engine, raw_text)

        json_data = analize_cv_via_llm(raw_text, reference_context=reference_context)
        skill_score = calculate_skill_score(json_data)
        print(f"Calculated skill score: {skill_score:.2f}")
        print("inserting CV data into database...")

        id_db = insert_cv_data(file_path, raw_text, json_data, skill_score)
        print(f"CV data inserted into database with ID: {id_db}\n")
        return True

    except Exception as e:
        print(f"Error processing CV: {e}\n")
        return False

def main():
    try:
        initialize_database()
    except Exception as e:
        print(f"Error initializing database: {e}")
        return
    
    if manual_mode:
        # manual mode, single file selected from ui
        print("Running in manual mode. Select a CV file to process.")
        file_path = get_local_file_via_ui()
        if file_path:
            elaborate_single_cv(file_path)
        else:
            print("No file selected. Exiting.")

    else:
        # automated mode, process all files in /data directory
        print("Running in automated mode. Processing all CV files in /cv_storage directory.")
        cv_directory = "cv_storage"

        if not os.path.exists(cv_directory):
            print(f"Directory {cv_directory} does not exist. Exiting.")
            return
        
        presence_of_files = False

        # create processed directory if it doesn't exist
        processed_dir = os.path.join(cv_directory, "processed")
        os.makedirs(processed_dir, exist_ok=True)

        try:
            rag_engine = build_rag_query_engine("rag_knowledge")
        except Exception as e:
            rag_engine = None
            print(f"Warning: could not build RAG index: {e}")
                
        for filename in os.listdir(cv_directory):
            # check for valid file extensions
            if filename.lower().endswith(('.pdf', '.docx', '.txt')):
                presence_of_files = True
                file_path = os.path.join(cv_directory, filename)
                print(f"Processing file: {file_path}")
                
                # process the CV and move it to processed folder if successful
                if elaborate_single_cv(file_path, rag_engine):
                    destination_path = os.path.join(processed_dir, filename)
                    try:
                        shutil.move(file_path, destination_path)
                    except Exception as e:
                        print(f"Error moving processed file: {e}")

        if not presence_of_files:
            print("No valid CV files found in the directory.")

if __name__ == "__main__":
    main()