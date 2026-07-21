import json
from pathlib import Path
from typing import Optional
from src.config import DATABASE_URL

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def _require_psycopg():
    if psycopg is None:
        raise RuntimeError(
            "psycopg is required for database operations. Install it before using database functions."
        )


def initialize_database():
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        with conn.cursor() as cur:
            # Tabella curricula (già esistente)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS curricula (
                    id SERIAL PRIMARY KEY,
                    file_reference TEXT,
                    raw_text TEXT,
                    llm_data JSONB,
                    skill_score REAL,
                    role_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("ALTER TABLE curricula ADD COLUMN IF NOT EXISTS skill_score REAL;")
            conn.execute("ALTER TABLE curricula ADD COLUMN IF NOT EXISTS role_id INTEGER;")

            # Nuova tabella: ruoli
            cur.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    instructions TEXT NOT NULL DEFAULT '',
                    score_config JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Nuova tabella: CV di reference per ruolo
            cur.execute("""
                CREATE TABLE IF NOT EXISTS role_references (
                    id SERIAL PRIMARY KEY,
                    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    file_reference TEXT NOT NULL,
                    file_name TEXT,
                    text_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("ALTER TABLE role_references ADD COLUMN IF NOT EXISTS text_content TEXT;")

            conn.commit()

# adds a new CV entry to the database and returns the generated ID
def insert_cv_data(
    file_path: str,
    raw_text: str,
    llm_data: dict,
    skill_score: float | None = None,
    role_id: int | None = None,
) -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO curricula (file_reference, raw_text, llm_data, skill_score, role_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (file_path, raw_text, json.dumps(llm_data), skill_score, role_id))
            cv_id = cur.fetchone()[0]
            conn.commit()
    return cv_id


def fetch_all_llm_rows() -> list[tuple[int, dict]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, llm_data FROM curricula;")
            rows = cur.fetchall()
    return rows


def update_skill_score(cv_id: int, skill_score: float) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE curricula SET skill_score = %s WHERE id = %s;",
                (skill_score, cv_id),
            )
            conn.commit()


# ─── Nuove funzioni per API ─────────────────────────

def fetch_cv_by_id(cv_id: int) -> Optional[dict]:
    """Restituisce un CV completo dal database, o None se non trovato."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_reference, raw_text, llm_data, skill_score, created_at "
                "FROM curricula WHERE id = %s",
                (cv_id,)
            )
            row = cur.fetchone()

    if row is None:
        return None

    llm_data_raw = row[3]
    if isinstance(llm_data_raw, str):
        llm_data = json.loads(llm_data_raw)
    elif isinstance(llm_data_raw, dict):
        llm_data = llm_data_raw
    else:
        llm_data = {}

    return {
        "id": row[0],
        "file_reference": row[1],
        "raw_text": row[2],
        "llm_data": llm_data,
        "skill_score": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
    }


def fetch_cvs_paginated(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    seniority: Optional[str] = None,
    sort_by: str = "skill_score",
    order: str = "desc",
) -> list[dict]:
    """Restituisce una lista paginata di CV con filtro e ordinamento."""
    _require_psycopg()
    offset = (page - 1) * limit

    conditions: list[str] = []
    params: list = []

    if search:
        conditions.append(
            "(llm_data->'candidate_data'->>'name' ILIKE %s OR "
            "llm_data->'candidate_profile'->>'current_role' ILIKE %s)"
        )
        params.extend([f"%{search}%", f"%{search}%"])

    if seniority:
        conditions.append("llm_data->'feature_index'->>'seniority' = %s")
        params.append(seniority)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    allowed_sort = {"skill_score", "created_at", "id"}
    if sort_by not in allowed_sort:
        sort_by = "skill_score"
    if order not in ("asc", "desc"):
        order = "desc"

    query = f"""
        SELECT id, file_reference, llm_data, skill_score, created_at
        FROM curricula
        WHERE {where_clause}
        ORDER BY {sort_by} {order}
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        llm_data_raw = row[2]
        if isinstance(llm_data_raw, str):
            ld = json.loads(llm_data_raw)
        elif isinstance(llm_data_raw, dict):
            ld = llm_data_raw
        else:
            ld = {}

        results.append({
            "id": row[0],
            "file_reference": Path(row[1]).name if row[1] else "",
            "candidate_name": (ld.get("candidate_data") or {}).get("name", "Unknown"),
            "current_role": (ld.get("candidate_profile") or {}).get("current_role", ""),
            "seniority": (ld.get("feature_index") or {}).get("seniority", ""),
            "top_skills": (ld.get("candidate_profile") or {}).get("top_skills", []),
            "skill_score": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
        })

    return results


def fetch_total_cvs(search: Optional[str] = None, seniority: Optional[str] = None) -> int:
    """Restituisce il numero totale di CV, opzionalmente filtrati."""
    _require_psycopg()
    conditions: list[str] = []
    params: list = []

    if search:
        conditions.append(
            "(llm_data->'candidate_data'->>'name' ILIKE %s OR "
            "llm_data->'candidate_profile'->>'current_role' ILIKE %s)"
        )
        params.extend([f"%{search}%", f"%{search}%"])

    if seniority:
        conditions.append("llm_data->'feature_index'->>'seniority' = %s")
        params.append(seniority)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM curricula WHERE {where_clause}", params)
            return cur.fetchone()[0]


def delete_cv_by_id(cv_id: int) -> bool:
    """Elimina un CV dal database. Restituisce True se è stato rimosso."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM curricula WHERE id = %s", (cv_id,))
            deleted = cur.rowcount > 0
            conn.commit()
    return deleted


def get_dashboard_stats() -> dict:
    """Calcola le statistiche per la dashboard."""
    _require_psycopg()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Statistiche aggregate
            cur.execute("""
                SELECT
                    COUNT(*)::int as total,
                    COALESCE(ROUND(AVG(skill_score)::numeric, 2), 0) as avg_score,
                    COALESCE(ROUND(MAX(skill_score)::numeric, 2), 0) as max_score,
                    COALESCE(ROUND(MIN(skill_score)::numeric, 2), 0) as min_score
                FROM curricula
            """)
            agg = cur.fetchone()

            # Distribuzione punteggi
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE skill_score < 4)::int as range_0_4,
                    COUNT(*) FILTER (WHERE skill_score >= 4 AND skill_score < 6)::int as range_4_6,
                    COUNT(*) FILTER (WHERE skill_score >= 6 AND skill_score < 8)::int as range_6_8,
                    COUNT(*) FILTER (WHERE skill_score >= 8)::int as range_8_10
                FROM curricula
            """)
            dist = cur.fetchone()

            # CV recenti
            cur.execute("""
                SELECT id, llm_data->'candidate_data'->>'name' as name,
                       skill_score, created_at
                FROM curricula
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent_rows = cur.fetchall()

            # Per top skills e seniority: prendiamo tutti i llm_data
            cur.execute("SELECT llm_data FROM curricula")
            all_llm = cur.fetchall()

    # Conteggio skills
    skill_counter: dict[str, int] = {}
    seniority_counter: dict[str, int] = {}

    for row in all_llm:
        llm_raw = row[0]
        if isinstance(llm_raw, str):
            ld = json.loads(llm_raw)
        elif isinstance(llm_raw, dict):
            ld = llm_raw
        else:
            continue

        # Top skills
        top_skills = (ld.get("candidate_profile") or {}).get("top_skills", [])
        for skill in top_skills:
            if isinstance(skill, str):
                skill_counter[skill.lower()] = skill_counter.get(skill.lower(), 0) + 1

        # Seniority
        seniority = (ld.get("feature_index") or {}).get("seniority", "unknown")
        seniority_counter[seniority] = seniority_counter.get(seniority, 0) + 1

    # Ordina top skills per frequenza
    top_skills_sorted = sorted(skill_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    top_skills_list = [{"skill": skill, "count": count} for skill, count in top_skills_sorted]

    recent_list = []
    for r in recent_rows:
        recent_list.append({
            "id": r[0],
            "candidate_name": r[1] or "Unknown",
            "skill_score": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
        })

    return {
        "total_cvs": agg[0],
        "avg_score": float(agg[1]),
        "max_score": float(agg[2]),
        "min_score": float(agg[3]),
        "score_distribution": {
            "0-4": dist[0],
            "4-6": dist[1],
            "6-8": dist[2],
            "8-10": dist[3],
        },
        "top_skills": top_skills_list,
        "seniority_distribution": seniority_counter,
        "recent_uploads": recent_list,
    }


# ─── CRUD Ruoli ─────────────────────────────────────

def create_role(name: str, instructions: str = "", score_config: Optional[dict] = None) -> int:
    """Crea un nuovo ruolo. Restituisce l'id generato."""
    _require_psycopg()
    if score_config is None:
        score_config = {}
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO roles (name, instructions, score_config) VALUES (%s, %s, %s) RETURNING id;",
                (name, instructions, json.dumps(score_config)),
            )
            role_id = cur.fetchone()[0]
            conn.commit()
    return role_id


def get_all_roles() -> list[dict]:
    """Restituisce tutti i ruoli."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, instructions, score_config, created_at, updated_at "
                "FROM roles ORDER BY name;"
            )
            rows = cur.fetchall()
    results = []
    for row in rows:
        sc_raw = row[3]
        if isinstance(sc_raw, str):
            sc = json.loads(sc_raw)
        elif isinstance(sc_raw, dict):
            sc = sc_raw
        else:
            sc = {}
        results.append({
            "id": row[0],
            "name": row[1],
            "instructions": row[2],
            "score_config": sc,
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        })
    return results


def get_role_by_id(role_id: int) -> Optional[dict]:
    """Restituisce un ruolo per id, o None se non trovato."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, instructions, score_config, created_at, updated_at "
                "FROM roles WHERE id = %s;",
                (role_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    sc_raw = row[3]
    if isinstance(sc_raw, str):
        sc = json.loads(sc_raw)
    elif isinstance(sc_raw, dict):
        sc = sc_raw
    else:
        sc = {}
    return {
        "id": row[0],
        "name": row[1],
        "instructions": row[2],
        "score_config": sc,
        "created_at": row[4].isoformat() if row[4] else None,
        "updated_at": row[5].isoformat() if row[5] else None,
    }


def update_role(role_id: int, name: Optional[str] = None, instructions: Optional[str] = None,
                score_config: Optional[dict] = None) -> bool:
    """Aggiorna un ruolo. Restituisce True se è stato modificato."""
    _require_psycopg()
    updates: list[str] = []
    params: list = []
    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if instructions is not None:
        updates.append("instructions = %s")
        params.append(instructions)
    if score_config is not None:
        updates.append("score_config = %s")
        params.append(json.dumps(score_config))
    if not updates:
        return False
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(role_id)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE roles SET {', '.join(updates)} WHERE id = %s;",
                params,
            )
            updated = cur.rowcount > 0
            conn.commit()
    return updated


def delete_role(role_id: int) -> bool:
    """Elimina un ruolo e i suoi reference. Restituisce True se rimosso."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM roles WHERE id = %s;", (role_id,))
            deleted = cur.rowcount > 0
            conn.commit()
    return deleted


# ─── Reference CV per ruolo ─────────────────────────

def add_role_reference(role_id: int, file_reference: str, file_name: str,
                       text_content: Optional[str] = None) -> int:
    """Aggiunge un CV di reference a un ruolo. Restituisce l'id generato."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO role_references (role_id, file_reference, file_name, text_content) "
                "VALUES (%s, %s, %s, %s) RETURNING id;",
                (role_id, file_reference, file_name, text_content),
            )
            ref_id = cur.fetchone()[0]
            conn.commit()
    return ref_id


def get_role_references(role_id: int) -> list[dict]:
    """Restituisce la lista dei CV di reference per un ruolo."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role_id, file_reference, file_name, text_content, created_at "
                "FROM role_references WHERE role_id = %s ORDER BY created_at;",
                (role_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "role_id": r[1],
            "file_reference": r[2],
            "file_name": r[3],
            "text_content": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]


def delete_role_reference(ref_id: int) -> bool:
    """Elimina un CV di reference."""
    _require_psycopg()
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM role_references WHERE id = %s;", (ref_id,))
            deleted = cur.rowcount > 0
            conn.commit()
    return deleted

