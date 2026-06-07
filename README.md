# BAPI Explorer

A Python web application for exploring SAP RFC function modules (BAPIs) — search, inspect the parameter interface, drill into ABAP type structures, and execute calls directly from your browser.

Built with **FastAPI** + **pyrfc** (SAP NW RFC SDK wrapper), with a Bootstrap 5 UI served via Jinja2 templates.

---

## Features

### Search
| | |
|-|-|
| 🔍 **Wildcard search** | Find RFC function modules by SAP wildcard pattern (`BAPI_SALES*`, `*MATERIAL*`, `RFC_READ+TABLE`) |
| 🕒 **Recent searches** | Last 10 searches shown in a dropdown when you focus the search box; click to re-run |
| 🏷️ **Group filter** | Dropdown to narrow results by SAP function group, auto-populated from search results |
| ✏️ **Term highlighting** | Matching text highlighted in results (yellow) for quick scanning |
| 📋 **Instant filter** | Filter the results table by name, group, or description without re-querying SAP |
| 📄 **Pagination** | Results table paginated at 50 items per page with smart page-number navigation |

### Structure tab
| | |
|-|-|
| 📋 **Parameter interface** | All Import / Export / Changing / Table parameters and Exceptions with direction, ABAP type, optional flag, default, and description |
| 🔎 **Type drill-down** | Click any type badge (e.g. `BAPISDH1 ›`) to expand the full field list inline — name, data type, length, description; click again to collapse; cached per session |
| 🔁 **Parameter filter** | Instant filter bar above the parameter tables — type to filter all sections by name or description; sections with no matches are dimmed |
| 📋 **Copy field name** | Click any parameter name to copy it to clipboard; icon flashes green to confirm |

### Run tab
| | |
|-|-|
| ▶️ **Auto-generated form** | Import and Changing parameters rendered as typed inputs; Table parameters as JSON array textareas |
| 🧩 **Fill skeleton** | "Fill skeleton" button on structured params fetches all fields from SAP and inserts a `{"FIELD": "", ...}` template |
| 💾 **Saved inputs** | Last entered values automatically restored from `localStorage` when you revisit a function |
| 🔢 **Type coercion** | Numeric parameters auto-coerced from strings (`"5"` → `5`) based on ABAP EXID codes |
| 📝 **Raw JSON override** | Paste raw JSON to override generated fields entirely |

### Result tab
| | |
|-|-|
| ✅ **Status + timing** | Success/error banner with execution time (ms or s) |
| 💬 **BAPIRET2 messages** | Return messages displayed with type badge (E/W/S/I) and message text |
| 📊 **CSV export** | Table outputs (arrays of objects) detected automatically; one-click CSV download per table |
| 📋 **Copy JSON** | Copy full raw output to clipboard |

### History tab
| | |
|-|-|
| 🕒 **Per-function history** | Last 20 runs recorded per function (timestamp, success/fail, duration, params) |
| 🔁 **Replay** | Click Replay to fill the Run form with stored parameters and switch back to Run tab |

### Multi-system profiles
| | |
|-|-|
| 🔗 **Profile switcher** | Navbar dropdown to switch between named SAP connection profiles without restarting |
| ⚙️ **`profiles.json`** | Define DEV/QAS/PRD profiles in the project root; each profile overrides `.env` connection settings |

### AI Assistant
| | |
|-|-|
| 🤖 **GitHub Copilot integration** | Floating AI button on every BAPI detail page — opens a slide-in chat panel powered by GitHub Copilot SDK |
| 💬 **SAP expert context** | Assistant is pre-primed with the current BAPI name, description, and parameter list for targeted answers |
| ⚡ **Streaming responses** | Responses stream in token-by-token via Server-Sent Events — no waiting for the full answer |
| 🔄 **Multi-turn chat** | Conversation history is preserved per browser session; click 🗑 to clear and start fresh |
| 📝 **Markdown rendering** | Code blocks, inline code, bold, and bullet points rendered in assistant messages |

### Theme
| | |
|-|-|
| 🌗 **Light / Dark / System** | Three-way theme switcher in the navbar; follows OS preference in System mode; choice persisted in `localStorage` |

---

## Prerequisites

1. **SAP NW RFC SDK** — `sapnwrfc.dll` must be loadable at runtime  
   Either install it to a directory and set `SAPNWRFC_HOME`, or ensure the DLLs are on the system `PATH` (e.g. copied to `C:\Windows\System32`)
2. **Python 3.11 – 3.12** on Windows (pyrfc is Windows-only; Python 3.13+ not yet supported due to `pydantic-core` wheel availability)
3. Network access to the SAP system
4. **GitHub Copilot subscription** (for AI assistant) — must be logged in via `copilot` CLI (`copilot auth login`). The Copilot CLI is bundled with `github-copilot-sdk`; no separate install needed.

---

## Setup

```powershell
# 1. Clone / copy the project
cd bapi-explorer

# 2. Create a virtual environment — must use Python 3.11 or 3.12 explicitly
py -3.12 -m venv .venv

# 3. If the SAP NW RFC SDK is NOT on the system PATH, set SAPNWRFC_HOME first
$env:SAPNWRFC_HOME = "C:\Program Files\SAP\FrontEnd\SapGui\nwrfcsdk"

# 4. Install dependencies
.venv\Scripts\pip install -r requirements.txt

# 5. Configure SAP connection
copy .env.example .env
# Edit .env with your SAP system details
```

---

## Configuration (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `SAP_CONN_TYPE` | ✔ | `msgserver` or `direct` |
| `SAP_AUTH_MODE` | ✔ | `snc` (SSO) or `password` |
| `SAP_MSHOST` | msgserver | Message server hostname |
| `SAP_MSSERV` | msgserver | Message server port/service |
| `SAP_SYSID` | msgserver | SAP System ID |
| `SAP_HOST` | direct | Application server hostname |
| `SAP_SYSNR` | direct | System number |
| `SAP_CLIENT` | ✔ | Client number |
| `SAP_LANG` | | Logon language (default: `EN`) |
| `SAP_GROUP` | | Logon group (default: `SPACE`) |
| `SAP_SNC_NAME` | snc | SNC partner name |
| `SNC_LIB` | snc | Path to `sapcrypto.dll` |
| `SAP_USER` | password | SAP user name |
| `SAP_PASSWORD` | password | SAP password |
| `APP_HOST` | | Bind address (default: `127.0.0.1`) |
| `APP_PORT` | | HTTP port (default: `8000`) |

> **Note:** real environment variables always take precedence over `.env` values (loaded with `override=False`).  
> If `SNC_LIB` is set system-wide, it will be used even if `.env` specifies a different path.

---

## Multi-system profiles (`profiles.json`)

Create a `profiles.json` in the project root to define additional SAP systems. A "default" entry is created automatically and uses the `.env` / environment variables.

```json
{
  "default": {
    "label": "Default (from .env)",
    "description": "Loaded from environment variables / .env file"
  },
  "dev": {
    "label": "Development",
    "description": "DEV system",
    "SAP_CONN_TYPE": "msgserver",
    "SAP_AUTH_MODE": "snc",
    "SAP_MSHOST": "dev-msg.example.com",
    "SAP_MSSERV": "3601",
    "SAP_SYSID": "DEV",
    "SAP_CLIENT": "100",
    "SAP_SNC_NAME": "p:CN=DEV, O=Example"
  }
}
```

Switch profiles from the navbar dropdown. The active profile is reset to "default" on server restart.

---

## Running

```powershell
# Development (auto-reload) — always use the venv Python, not the system one
.venv\Scripts\python -m app.main

# Or via uvicorn directly
.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser.  
Interactive API docs: **http://127.0.0.1:8000/docs**

### Stopping the app

```powershell
# Find PID listening on the port
netstat -ano | findstr ":8000 " | findstr LISTENING

# Stop it
Stop-Process -Id <PID> -Force
```

> If `Stop-Process` reports "Cannot find a process", the PID is owned by another session. Run the same commands in an **elevated (Administrator) PowerShell**.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/bapi/search?q=BAPI_SALES*&max=100` | Search function modules |
| `GET` | `/api/bapi/{name}/structure` | Get parameter interface + function description |
| `GET` | `/api/bapi/type-info?name=BAPISDH1` | Get field list of an ABAP structure/type |
| `POST` | `/api/bapi/{name}/run` | Execute a BAPI |
| `GET` | `/api/profiles` | List all configured profiles |
| `GET` | `/api/profiles/active` | Get the currently active profile |
| `POST` | `/api/profiles/active` | Switch active profile — body: `{"name": "dev"}` |
| `POST` | `/api/ai/chat` | Stream an AI assistant response (SSE). Body: `{message, session_id, bapi_name?, bapi_description?, bapi_params?}` |
| `DELETE` | `/api/ai/sessions/{id}` | Destroy a chat session and free Copilot SDK resources |

> Function names containing `/` (namespace prefixes like `/PGX/S_AM_RFC_READ_TABLE`) are fully supported.

### Run request body

Import and Changing parameters are key-value pairs. Table parameters are JSON arrays of row objects. String values for numeric parameters are automatically coerced to the correct Python type.

```json
{
  "parameters": {
    "SALESDOCUMENT": "0000012345",
    "ORDER_HEADER_INX": {"UPDATEFLAG": "U"},
    "ORDER_ITEM_IN": [
      {"ITM_NUMBER": "000010", "TARGET_QTY": "5"}
    ]
  }
}
```

---

## Project Structure

```
bapi-explorer/
├── app/
│   ├── main.py              FastAPI app, router wiring, static files
│   ├── sap/
│   │   ├── config.py        SapConfig — reads from env or profile dict
│   │   ├── client.py        SapRfcClient — search / structure / run / type-info
│   │   └── models.py        Pydantic models for all API responses
│   ├── routers/
│   │   ├── bapi.py          REST API routes (/api/bapi/*)
│   │   ├── profiles.py      Profile management (/api/profiles/*)
│   │   ├── ai.py            AI assistant via GitHub Copilot SDK (/api/ai/*)
│   │   └── ui.py            UI page routes (/, /bapi/{name})
│   └── templates/
│       ├── base.html        Navbar with profile switcher, Bootstrap 5
│       ├── index.html       Search page with recent searches, group filter, highlighting
│       └── bapi_detail.html Structure / Run / Result / History tabs
├── static/
│   ├── css/app.css
│   ├── js/app.js
│   └── vendor/              Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 (local, no CDN)
├── profiles.json            Named SAP connection profiles — **gitignored** (auto-created on first run)
├── .env.example
├── requirements.txt
└── README.md
```

---

## SAP RFC Functions Used

| RFC | Purpose |
|-----|---------|
| `RFC_FUNCTION_SEARCH` | Search by wildcard pattern; fetch function short description (`STEXT`) |
| `RFC_GET_FUNCTION_INTERFACE` | Get parameter interface (direction, ABAP type, EXID, optional flag); also used at run-time for type coercion |
| `DDIF_FIELDINFO_GET` | Fetch field definitions (name, data type, length, description) for any ABAP structure or table type |
| Direct `pyrfc.Connection.call()` | Execute any BAPI/RFC function with given parameters |

