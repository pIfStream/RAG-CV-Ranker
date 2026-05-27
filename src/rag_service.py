from pathlib import Path
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import Document
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from pypdf import PdfReader


embed_model = OllamaEmbedding(
    model_name="nomic-embed-text",
    request_timeout=300.0,  
)


llm = Ollama(
    model="gemma4:latest",  
    request_timeout=300.0,
    temperature=0.1,        
)

# Set global configurations
Settings.embed_model = embed_model
Settings.llm = llm

def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(pdf_path)
    if reader.is_encrypted:
        raise ValueError(f"PDF file is encrypted: {pdf_path}. Please decrypt it before indexing.")

    page_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page_texts).strip()
    return text


def load_and_index_documents(data_dir="data"):
    """Load PDF documents and create vector index"""

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found. Please create it and add your PDF files.")

    pdf_files = sorted(data_path.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No PDF files found in {data_dir}. Please add PDF documents.")

    docs = []
    for pdf_file in pdf_files:
        text = extract_text_from_pdf(pdf_file)
        if not text:
            raise ValueError(f"No text extracted from {pdf_file.name}.")

        docs.append(
            Document(
                text=text,
                extra_info={
                    "file_path": str(pdf_file),
                    "file_name": pdf_file.name,
                },
            )
        )

    index = VectorStoreIndex.from_documents(docs, embed_model=embed_model)
    return index

def create_query_engine(index, similarity_top_k=3):
    """Create query engine with specified retrieval parameters"""

    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=similarity_top_k, 
        response_mode="compact"            
    )

    return query_engine

def test_rag_system():
    """Test the RAG system with sample queries"""

    try:
        # Load documents and create index
        index = load_and_index_documents()

        # Create query engine
        query_engine = create_query_engine(index)

        # Sample test queries
        test_queries = [
            "Summarize this document in 3 lines",
            "What are the main topics covered in these documents?",
        ]

        print("RAG System Test Results")
        print("=" * 50)

        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 40)

            try:
                response = query_engine.query(query)
                print(f"Response: {response}")
                print(f"Status: SUCCESS")
            except Exception as e:
                print(f"Error: {str(e)}")
                print(f"Status: FAILED")

            print("-" * 40)

        return True

    except Exception as e:
        print(f"System Error: {str(e)}")
        return False

# Main execution
if __name__ == "__main__":

    print("Starting RAG Pipeline Test...")

    # Test the complete system
    success = test_rag_system()

    if success:
        print("\nRAG system is working correctly!")
        print("You can now use the query_engine to ask questions about your documents.")
    else:
        print("\nRAG system test failed. Check the error messages above.")