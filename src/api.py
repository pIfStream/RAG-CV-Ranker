"""
API REST per RAG-CV-Ranker.

Fornisce endpoint per:
- Gestione ruoli (CRUD)
- Caricamento CV di reference per ruolo
- Caricamento ed elaborazione CV con selezione ruolo
- Consultazione, ricerca e filtraggio CV
- Dettaglio score e breakdown
- Statistiche dashboard
- Configurazione pesi score
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src.database import (
    initialize_database,
    insert_cv_data,
    fetch_cv_by_id,
    fetch_cvs_paginated,
    fetch_total_cvs,
    delete_cv_by_id,
    get_dashboard_stats,
    create_role,
    get_all_roles,
    get_role_by_id,
    update_role,
    delete_role,
    add_role_reference,
    get_role_references,
    delete_role_reference,
)
from src.parser import extract_text_from_file
from src.llm_service import analize_cv_via_llm
from src.rag_service import build_rag_query_engine_from_dir, retrieve_relevant_context
from src.storage import FileStorage, name_to_slug
from src.score_calculator import (
    calculate_skill_score,
    calculate_skill_score_breakdown,
    load_score_config,
    save_score_config,
    recalculate_skill_scores_in_db,
)

# ── Configurazione da ambiente ─────────────────────────
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rag-cv-ranker")

# ── App FastAPI ────────────────────────────────────────
app = FastAPI(
    title="RAG-CV-Ranker API",
    version="1.0.0",
    description="API per la gestione, analisi e ranking di CV tramite RAG e LLM",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Path configurabili via ambiente ────────────────────
CV_STORAGE_DIR = Path(os.getenv("CV_STORAGE_DIR", "cv_storage"))
CV_STORAGE_DIR.mkdir(exist_ok=True)

ROLE_REFS_BASE = os.getenv("ROLE_REFS_DIR", "role_references")
storage = FileStorage(base_path=ROLE_REFS_BASE)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    """Inizializza il database all'avvio."""
    initialize_database()


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _validate_file_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato file non supportato: {ext}. "
                   f"Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    return ext


# ── Endpoint: Upload CV ────────────────────────────────────────────────────────

@app.post("/api/upload", summary="Carica ed elabora un CV")
async def upload_cv(
    file: UploadFile = File(..., description="File CV (PDF, DOCX o TXT)"),
    role_id: Optional[int] = Form(None, description="ID del ruolo per cui valutare il CV"),
    job_description: Optional[str] = Form(None, description="Descrizione della posizione lavorativa per contesto RAG"),
):
    """Carica un CV, lo analizza con LLM, calcola lo score e lo salva nel database.

    Se viene specificato role_id, usa le istruzioni LLM, i pesi score e i CV di
    reference associati a quel ruolo.
    """
    ext = _validate_file_extension(file.filename)

    # Salva il file su disco con nome univoco
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = CV_STORAGE_DIR / unique_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        # 0. Se specificato un ruolo, carica i suoi dati
        role = None
        if role_id is not None:
            role = get_role_by_id(role_id)
            if role is None:
                raise HTTPException(status_code=404, detail=f"Ruolo con id {role_id} non trovato")

        # 1. Estrazione testo con Docling
        raw_text = extract_text_from_file(str(file_path))

        # 2. RAG context: priorità ai reference del ruolo, poi job_description
        rag_engine = None
        reference_context = None

        if role is not None:
            # Costruisci RAG engine dai CV di reference del ruolo (per nome)
            role_slug = name_to_slug(role["name"])
            role_refs_dir = storage.get_role_dir(role_slug)
            if role_refs_dir:
                try:
                    rag_engine = build_rag_query_engine_from_dir(role_refs_dir)
                    if rag_engine:
                        reference_context = retrieve_relevant_context(rag_engine, raw_text)
                except Exception as e:
                    logger.warning("RAG engine per ruolo '%s' non disponibile: %s", role["name"], e)

        if reference_context is None and job_description:
            # Fallback: RAG classico da job_description
            try:
                rag_engine = build_rag_query_engine_from_dir("rag_knowledge")
                if rag_engine:
                    reference_context = retrieve_relevant_context(rag_engine, job_description)
            except Exception as e:
                logger.warning("RAG engine classico non disponibile: %s", e)

        # 3. Analisi con LLM (Ollama) — con istruzioni personalizzate se ruolo
        instructions_override = role["instructions"] if role else None
        json_data = analize_cv_via_llm(
            raw_text,
            reference_context=reference_context,
            instructions_override=instructions_override,
        )

        # 4. Calcolo skill score — con configurazione pesi del ruolo se presente
        score_config_override = role["score_config"] if role and role.get("score_config") else None
        skill_score = calculate_skill_score(
            json_data,
            score_config_override=score_config_override,
        )

        # 5. Salvataggio in PostgreSQL (con role_id)
        cv_role_id = role["id"] if role else None
        cv_id = insert_cv_data(str(file_path), raw_text, json_data, skill_score, role_id=cv_role_id)

        return {
            "id": cv_id,
            "filename": file.filename,
            "role_id": role["id"] if role else None,
            "role_name": role["name"] if role else None,
            "status": "completed",
            "candidate_name": (json_data.get("candidate_data") or {}).get("name", "Unknown"),
            "current_role": (json_data.get("candidate_profile") or {}).get("current_role", ""),
            "skill_score": round(skill_score, 2),
            "dimension_scores": json_data.get("dimension_scores", {}),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Pulizia del file in caso di errore
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Errore durante l'elaborazione del CV: {str(e)}",
        )


# ── Endpoint: Lista CV (paginata e filtrata) ───────────────────────────────────

@app.get("/api/cvs", summary="Elenco CV con filtri e paginazione")
def list_cvs(
    page: int = Query(1, ge=1, description="Numero di pagina"),
    limit: int = Query(20, ge=1, le=100, description="Elementi per pagina"),
    search: Optional[str] = Query(None, description="Ricerca per nome o ruolo"),
    seniority: Optional[str] = Query(
        None, description="Filtra per seniority (junior, mid, senior, lead)"
    ),
    sort_by: str = Query(
        "skill_score", description="Campo per ordinamento (skill_score, created_at, id)"
    ),
    order: str = Query("desc", description="Direzione ordinamento (asc, desc)"),
):
    """Restituisce la lista dei CV con supporto di paginazione, ricerca e filtri."""
    items = fetch_cvs_paginated(
        page=page,
        limit=limit,
        search=search,
        seniority=seniority,
        sort_by=sort_by,
        order=order,
    )
    total = fetch_total_cvs(search=search, seniority=seniority)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": items,
    }


# ── Endpoint: Dettaglio CV ─────────────────────────────────────────────────────

@app.get("/api/cvs/{cv_id}", summary="Dettaglio completo di un CV")
def get_cv(cv_id: int):
    """Restituisce tutti i dati di un CV, incluso llm_data e raw_text."""
    cv = fetch_cv_by_id(cv_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="CV non trovato")
    return cv


@app.delete("/api/cvs/{cv_id}", summary="Elimina un CV")
def delete_cv(cv_id: int):
    """Elimina un CV dal database."""
    deleted = delete_cv_by_id(cv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="CV non trovato")
    return {"status": "deleted"}


# ── Endpoint: Score Breakdown ──────────────────────────────────────────────────

@app.get(
    "/api/cvs/{cv_id}/score-breakdown",
    summary="Dettaglio del calcolo dello score",
)
def get_score_breakdown(cv_id: int):
    """Restituisce la scomposizione dettagliata del punteggio di un CV."""
    cv = fetch_cv_by_id(cv_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="CV non trovato")

    llm_data = cv.get("llm_data", {})
    if not llm_data:
        raise HTTPException(status_code=400, detail="Dati LLM non disponibili")

    return calculate_skill_score_breakdown(llm_data)


# ── Endpoint: Statistiche Dashboard ────────────────────────────────────────────

@app.get("/api/stats", summary="Statistiche aggregate per la dashboard")
def stats():
    """Restituisce statistiche: totale CV, media score, distribuzioni, top skills."""
    return get_dashboard_stats()


# ── Endpoint: Configurazione Pesi ──────────────────────────────────────────────

@app.get("/api/config", summary="Leggi configurazione pesi score")
def get_config():
    """Restituisce la configurazione attuale dei pesi (skills e tools)."""
    return load_score_config()


@app.put("/api/config", summary="Aggiorna configurazione pesi score")
def update_config(config: dict):
    """Aggiorna la configurazione dei pesi. Invia JSON con skills e/o tools."""
    try:
        save_score_config(config)
        return {"status": "updated"}
    except (ValueError, OSError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Endpoint: Ricalcolo Score ──────────────────────────────────────────────────

@app.post("/api/recalculate", summary="Ricalcola tutti gli score nel database")
def recalculate_scores():
    """Ricalcola gli skill_score di tutti i CV presenti nel database."""
    try:
        updated = recalculate_skill_scores_in_db()
        return {"updated": updated, "status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: Health Check ─────────────────────────────────────────────────────

@app.get("/api/health", summary="Health check del server")
def health():
    """Verifica che il server sia attivo."""
    return {"status": "ok", "service": "RAG-CV-Ranker API"}


# ── Endpoint: Gestione Ruoli ───────────────────────────────────────────────────

@app.post("/api/roles", summary="Crea un nuovo ruolo")
def create_role_endpoint(
    name: str = Form(..., description="Nome del ruolo (es. Data Analyst)"),
    instructions: Optional[str] = Form(None, description="Istruzioni personalizzate per l'LLM"),
    score_config: Optional[str] = Form(None, description="JSON con pesi skills/tools per il ruolo"),
):
    """Crea un nuovo ruolo con istruzioni LLM e configurazione pesi personalizzate."""
    parsed_config = {}
    if score_config:
        import json as _json
        try:
            parsed_config = _json.loads(score_config)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="score_config non è un JSON valido")

    role_id = create_role(
        name=name,
        instructions=instructions or "",
        score_config=parsed_config,
    )
    return {"id": role_id, "name": name, "status": "created"}


@app.get("/api/roles", summary="Elenco di tutti i ruoli")
def list_roles():
    """Restituisce tutti i ruoli configurati."""
    return get_all_roles()


@app.get("/api/roles/{role_id}", summary="Dettaglio di un ruolo")
def get_role(role_id: int):
    """Restituisce i dati di un ruolo, incluse istruzioni e configurazione pesi."""
    role = get_role_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    return role


@app.put("/api/roles/{role_id}", summary="Aggiorna un ruolo")
def update_role_endpoint(
    role_id: int,
    name: Optional[str] = Form(None, description="Nuovo nome del ruolo"),
    instructions: Optional[str] = Form(None, description="Nuove istruzioni LLM"),
    score_config: Optional[str] = Form(None, description="Nuovo JSON con pesi skills/tools"),
):
    """Aggiorna i dati di un ruolo (nome, istruzioni, pesi).

    Se il nome cambia, rinomina anche la directory su disco con il nuovo slug.
    """
    parsed_config = None
    if score_config is not None:
        import json as _json
        try:
            parsed_config = _json.loads(score_config)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="score_config non è un JSON valido")

    # Se il nome viene cambiato, rinomina la directory su disco
    if name is not None:
        old_role = get_role_by_id(role_id)
        if old_role and old_role["name"] != name:
            old_slug = name_to_slug(old_role["name"])
            new_slug = name_to_slug(name)
            storage.rename_role_dir(old_slug, new_slug)

    updated = update_role(
        role_id=role_id,
        name=name,
        instructions=instructions,
        score_config=parsed_config,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Ruolo non trovato o nessuna modifica")
    return {"status": "updated"}


@app.delete("/api/roles/{role_id}", summary="Elimina un ruolo")
def delete_role_endpoint(role_id: int):
    """Elimina un ruolo e tutti i suoi CV di reference."""
    role = get_role_by_id(role_id)
    if role:
        # Pulisce i file su disco usando lo slug del nome
        role_slug = name_to_slug(role["name"])
        storage.delete_role_dir(role_slug)

    deleted = delete_role(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    return {"status": "deleted"}


# ── Endpoint: CV di Reference per Ruolo ────────────────────────────────────────

@app.post("/api/roles/{role_id}/references", summary="Carica un CV di reference per un ruolo")
async def upload_role_reference(
    role_id: int,
    file: UploadFile = File(..., description="File PDF di reference"),
):
    """Carica un CV di reference associato a un ruolo.

    Il file viene salvato su disco in role_references/<slug-role>/.
    Il testo estratto viene conservato nel DB come fallback e per RAG veloce.
    """
    role = get_role_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")

    ext = _validate_file_extension(file.filename)
    content = await file.read()

    # Salva su disco usando lo storage astratto (per nome ruolo)
    role_slug = name_to_slug(role["name"])
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = storage.save(role_slug, unique_name, content)

    # Estrai il testo per salvarlo nel DB
    text_content = None
    try:
        text_content = extract_text_from_file(file_path)
    except Exception as e:
        logger.warning("Impossibile estrarre testo da %s: %s", file.filename, e)

    # Registra nel database con il testo estratto
    ref_id = add_role_reference(
        role_id=role_id,
        file_reference=file_path,
        file_name=file.filename,
        text_content=text_content,
    )

    return {
        "id": ref_id,
        "role_id": role_id,
        "file_name": file.filename,
        "status": "uploaded",
        "text_extracted": text_content is not None,
    }


@app.get("/api/roles/{role_id}/references", summary="Elenco CV di reference per un ruolo")
def list_role_references(role_id: int):
    """Restituisce la lista dei CV di reference caricati per un ruolo."""
    role = get_role_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato")
    return get_role_references(role_id)


@app.delete("/api/roles/{role_id}/references/{ref_id}", summary="Elimina un CV di reference")
def delete_role_reference_endpoint(role_id: int, ref_id: int):
    """Elimina un CV di reference (file su disco e record nel DB)."""
    refs = get_role_references(role_id)
    target = next((r for r in refs if r["id"] == ref_id), None)

    deleted = delete_role_reference(ref_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reference non trovato")

    # Pulisce il file su disco usando lo storage astratto
    if target and target["file_reference"]:
        storage.delete(target["file_reference"])

    return {"status": "deleted"}


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
