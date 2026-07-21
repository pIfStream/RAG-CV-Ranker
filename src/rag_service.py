from pathlib import Path
from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import Document
from pypdf import PdfReader

# Variabili lazy: vengono inizializzate al primo uso, non all'import
# Questo permette all'app di avviarsi anche se Ollama non è ancora in esecuzione
_embed_model = None
_llm = None


def _ensure_ollama_ready():
    """Inizializza i modelli Ollama al primo uso (lazy loading)."""
    global _embed_model, _llm

    if _embed_model is None:
        from llama_index.embeddings.ollama import OllamaEmbedding
        _embed_model = OllamaEmbedding(
            model_name="nomic-embed-text",
            request_timeout=300.0,
        )
        Settings.embed_model = _embed_model

    if _llm is None:
        from llama_index.llms.ollama import Ollama
        _llm = Ollama(
            model="gemma4:latest",
            request_timeout=300.0,
            temperature=0.1,
        )
        Settings.llm = _llm

def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(pdf_path)
    if reader.is_encrypted:
        raise ValueError(f"PDF file is encrypted: {pdf_path}.")

    page_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(page_texts).strip()
    return text

def load_and_index_documents(data_dir="data"):
    _ensure_ollama_ready()

    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    pdf_files = sorted(data_path.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(f"No PDF files found in {data_dir}.")

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

    index = VectorStoreIndex.from_documents(docs, embed_model=_embed_model)
    return index

def create_query_engine(index, similarity_top_k=3):
    _ensure_ollama_ready()

    query_engine = index.as_query_engine(
        llm=_llm,
        similarity_top_k=similarity_top_k, 
        response_mode="compact"            
    )

    return query_engine

def build_rag_query_engine(data_dir="rag_knowledge", similarity_top_k=3):
    index = load_and_index_documents(data_dir)
    return create_query_engine(index, similarity_top_k)


def build_rag_query_engine_from_dir(data_dir: str, similarity_top_k: int = 3):
    """Come build_rag_query_engine ma restituisce None se la directory non esiste o è vuota."""
    data_path = Path(data_dir)
    if not data_path.exists():
        return None

    pdf_files = sorted(data_path.glob("*.pdf"))
    if not pdf_files:
        return None

    try:
        return build_rag_query_engine(data_dir, similarity_top_k)
    except Exception:
        return None


def retrieve_relevant_context(query_engine, query_text: str) -> str:
    response = query_engine.query(query_text)
    return str(response)

