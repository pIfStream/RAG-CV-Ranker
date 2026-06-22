# RAG-CV-Ranker

Un sistema automatizzato e sequenziale per il parsing, l'analisi semantica e l'indicizzazione di Curricula Vitae (CV) in formato PDF. Il progetto utilizza **Docling** per un'estrazione accurata del testo in Markdown, un modello LLM locale tramite **Ollama** per la strutturazione dei dati in JSON, e **PostgreSQL (con estensione pgvector)** all'interno di Docker per la persistenza dei dati e la futura ricerca semantica (RAG).

L'applicazione è progettata per gestire i file in modalità **FIFO (First In, First Out)**, elaborando rigorosamente un CV alla volta per ottimizzare l'uso delle risorse hardware (CPU/GPU) durante l'inferenza del modello locale.

---

## 🏗️ Architettura del Sistema

Il flusso di elaborazione segue una pipeline lineare e protetta da eccezioni:

```
[ Cartella CV ] ──> ( Coda FIFO ) ──> [ Docling Parser ] ──> [ Ollama LLM ] ──> [ Postgres + pgvector ]
                                             │                                          │
                                             └──> [ Spostamento in /elaborati ] ────────┘

```

1. **Coda Sequenziale:** Lo script scansiona la cartella dei file e crea una coda ordinata.
2. **Parsing (Docling):** Il PDF viene convertito in testo strutturato Markdown.
3. **Analisi (Ollama):** L'LLM analizza il Markdown ed estrae le informazioni chiave in un formato JSON strutturato.
4. **Persistenza (Postgres):** Il database memorizza il percorso del file, il testo grezzo e il JSON (tramite tipo di dato `JSONB`).
5. **Svuotamento Coda:** Il file originale viene spostato in una sottocartella per evitare ri-elaborazioni al riavvio del container.

---

## 🛠️ Prerequisiti

Prima di avviare il progetto, assicurati di avere installato sul tuo sistema host (Windows 11):

* **Python 3.8 o superiore**
* **Docker Desktop** (con supporto WSL2 attivo)
* **Ollama** (avviato localmente e con il modello di riferimento già scaricato, es. `gemma4:latest`)

---

## 🚀 Setup e Installazione

Segui questi passaggi per configurare l'ambiente locale.

### 1. Clonare la Repository

```powershell
git clone https://github.com/tuo-username/RAG-CV-Ranker.git
cd RAG-CV-Ranker

```

### 2. Configurare l'Ambiente Virtuale Python

Crea e attiva l'ambiente virtuale sul tuo terminale Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

```

### 3. Configurare le Variabili d'Ambiente (`.env`)

Duplica il file modello presente nella repository e nominalo `.env`:

```powershell
cp .env.example .env

```

Apri il file `.env` appena creato e adatta i parametri se necessario. Di base è configurato per puntare al database Docker locale e a Ollama su Windows:

```env
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=gemma4:latest

DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/cv_db
IS_DOCKER=false

```

### 4. Avviare l'Infrastruttura Docker (PostgreSQL)

Assicurati che Docker Desktop sia aperto e in esecuzione, quindi avvia il container del database in modalità background:

```powershell
docker compose up -d

```

*Nota: Docker scaricherà l'immagine `ankane/pgvector:latest` ed esporrà automaticamente la porta `5432` sul tuo localhost.*

---

## 💻 Modalità di Esecuzione e Test

### Test di Singolo File (Interfaccia Grafica Windows)

Per testare la pipeline di parsing e analisi su un singolo file senza toccare la coda globale, puoi lanciare lo script di test integrato. Si aprirà una finestra nativa di Windows per farti selezionare manualmente un file PDF:

```powershell
python -m tests.single_file_parsing

```

I risultati del parsing e l'output JSON dell'LLM verranno salvati rispettivamente in `test/raw_text.txt` e `test/llm_result.txt` per una rapida ispezione.

### Esecuzione della Coda Completa

Per avviare l'elaborazione sequenziale di tutti i CV presenti nella cartella di input (sia in locale che nel container Docker):

```powershell
python -m src.main

```

---

## 🗄️ Ispezione del Database

Grazie alla mappatura delle porte del container, puoi connetterti al database PostgreSQL direttamente da Windows utilizzando un client grafico (es. TablePlus, DBeaver) o l'estensione **PostgreSQL** di VS Code.

### Parametri di Connessione:

* **Host:** `127.0.0.1` (o `localhost`)
* **Port:** `5432`
* **User:** `myuser`
* **Password:** `mypassword`
* **Database:** `cv_db`

### Struttura della Tabella `curricula`:

L'inizializzazione del database crea automaticamente la seguente tabella abilitata per dati semantici:

* `id` (SERIAL, Primary Key)
* `file_reference` (TEXT): Il percorso del file sul disco.
* `raw_text` (TEXT): Il testo Markdown estratto da Docling.
* `llm_data` (JSONB): Il JSON strutturato generato dall'LLM, indicizzato binariamente per query rapide sulle chiavi.
* `created_at` (TIMESTAMP): Timestamp di inserimento.

---

## 🔍 Risoluzione dei Problemi Comuni (Troubleshooting)

#### ❌ `ModuleNotFoundError: No module named 'src'`

* **Causa:** Stai lanciando lo script usando i percorsi relativi delle cartelle (es. `python src/main.py`), rompendo la risoluzione degli import di Python.
* **Soluzione:** Lancia sempre gli script dalla root del progetto utilizzando il flag `-m` e i punti come separatori: `python -m src.main`.

#### ❌ `getaddrinfo ENOTFOUND localhost:5432` o `127.0.0.1:5432` nell'estensione di VS Code

* **Causa:** L'estensione ha unito l'indirizzo IP e la porta in un unico blocco nel campo Hostname.
* **Soluzione:** Rimuovi l'estensione della porta dal campo Hostname. Scrivi solo `127.0.0.1` nel primo campo, premi Invio, e inserisci `5432` solo quando viene esplicitamente richiesto il campo *Port*.

#### ❌ `Failed to connect to Ollama`

* **Causa:** L'applicazione Ollama non è avviata su Windows o l'URL nel file `.env` punta al sito web anziché all'endpoint locale.
* **Soluzione:** Verifica che l'icona di Ollama sia presente nella barra delle applicazioni di Windows e che nel `.env` sia configurato `OLLAMA_HOST=http://localhost:11434`.

#### ❌ Modifiche strutturali alla tabella SQL non applicate

* **Causa:** Il comando `CREATE TABLE IF NOT EXISTS` non modifica le tabelle già esistenti se aggiungi nuove colonne nel codice Python.
* **Soluzione:** Se sei in fase di test e vuoi resettare il database per applicare le nuove colonne, esegui:
```powershell
docker compose down -v
docker compose up -d

```


*(Il flag `-v` cancellerà il volume e i vecchi dati, permettendo a Python di ricreare la tabella da zero al prossimo avvio).*