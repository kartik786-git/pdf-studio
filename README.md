# PDF Studio — Offline PDF Toolkit

A **Sejda-like** offline PDF processing desktop application built with **FastAPI** and **Python**. Process PDFs locally with no cloud uploads. Includes 43 tools for merging, splitting, rotating, converting, compressing, OCR, editing, securing, and more.

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Prerequisites](#-prerequisites)
- [Manual Installation](#-manual-installation)
- [Using the Startup Batch File](#-using-the-startup-batch-file)
- [Running the App Manually](#-running-the-app-manually)
- [Using the Application](#-using-the-application)
- [Available Tools](#-available-tools)
- [API Endpoints](#-api-endpoints)
- [Project Structure](#-project-structure)
- [License](#license)

---

## 🚀 Quick Start (using Batch File)

1. **Double‑click** `run.bat` in the project root folder.
2. A terminal window opens, activates the virtual environment, and starts the server.
3. Open your browser at `http://127.0.0.1:8000` to access the UI.

---

## ⚙️ Prerequisites

- **Git** (to clone the repository)
- **Python 3.9 or higher**
- ** pip ** (Python package installer)

---

## 📂 Manual Installation

If you prefer not to use the batch file, follow these steps:

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-username/pdf-studio.git
   cd pdf-studio
   ```

2. **Create and activate a virtual environment**

   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate.bat

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the application**

   ```bash
   python app.py
   ```

   The server will start at `http://127.0.0.1:8000`.

---

## 🛠️ Using the Startup Batch File

A convenient `run.bat` is included so non‑technical users can start the app with a single double‑click.

- **Location**: `run.bat` at the project root.
- **What it does**:
  1. Changes directory to the project folder.
  2. Activates the built‑in `venv\Scripts\activate.bat`.
  3. Runs `python app.py` to start FastAPI/Uvicorn.

- **To use**: Simply double‑click `run.bat`. A command prompt will stay open showing the server logs. Keep it open; the app runs in that window.

---

## 🏃 Running the App Manually

If you installed manually (see above), start the server:

```bash
python app.py
```

or, equivalently, use Uvicorn directly:

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --log-level info
```

The console will display something like:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Press CTRL+C to quit
```

---

## 🌐 Using the Application

Once the server is running:

1. Open your web browser and go to:

   - **API docs (Swagger UI)**: <http://127.0.0.1:8000/api>
   - **Alternative docs (ReDoc)**: <http://127.0.0.1:8000/api/redoc>
   - **Root (static UI)**: <http://127.0.0.1:8000/> (serves `static/index.html`)

2. The home page provides a file‑upload interface to select a PDF and choose from the 43 available tools.

3. **Typical workflow**:

   1. **Upload** one or more PDFs (or images, Office docs, HTML) via the form.
   2. The server returns a **`job_id`**.
   3. **Poll** the status endpoint `GET /api/jobs/{job_id}` until the status becomes `done`.
   4. **Download** the result via `GET /api/download/{job_id}`.

---

## 🛠️ Available Tools (43 total)

The tool categories and a subset of tools are:

| Category | Tools |
|---|---|
| **Files** | Merge, Alternate Mix, Organize, Split, Split Bookmarks, Split Half, Split Size, Split Text, Extract Pages, Delete Pages |
| **Pages** | Rotate, Crop, Resize, Flip, N-up, Grayscale, Remove Annotations |
| **Edit** | PDF Editor (canvas overlay), Create Forms |
| **Convert** | PDF to Text/JPG/PNG/Word/PPT/Excel, JPG to PDF, HTML to PDF, Extract Images |
| **Scans** | Compress, Deskew, OCR |
| **Security** | Protect, Unlock, Watermark, Flatten, Bates Numbering, Edit Metadata |
| **Misc** | Page Numbers, Header/Footer, Rename, Repair, Create Bookmarks |

Use `GET /api/tools` to retrieve the full list with parameter schemas.

---

## 🔗 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/tools` | `GET` | List all 43 tools with schemas |
| `/api/categories` | `GET` | List the 7 tool categories |
| `/api/tools/{tool_id}` | `POST` | Run a PDF tool (multipart/form-data: `files`, `options`, optional `overlay`) |
| `/api/jobs/{job_id}` | `GET` | Poll job status (`queued`/`running`/`done`/`error`) |
| `/api/download/{job_id}` | `GET` | Download the result file (PDF or ZIP) |
| `/api/jobs/{job_id}` | `DELETE` | Delete a job and clean up its files |
| `/api/editor/render` | `POST` | Render PDF pages to preview PNG images |
| `/api/preview/{job_id}` | `GET` | Check preview render status |
| `/api/preview/result/{job_id}` | `POST` | Render completed job output as thumbnails |

---

## 📁 Project Structure

```
pdf-studio/
├─ app.py                 # FastAPI entry point
├─ requirements.txt       # Python dependencies
├─ run.bat               # Double‑click launcher (activates venv & runs app.py)
├─ static/                # Static web assets (index.html, css, js)
├─ data/
│   ├─ uploads/           # Temporary uploaded files
│   └─ results/           # Processed output files
├─ services/
│   ├─ jobs.py            # Job submission & status tracking
│   └─ storage.py         # File storage helpers
└─ pdf_tools/
    ├─ __init__.py
    ├─ base.py            # Core processing base
    ├─ convert.py         # Convert tool implementations
    ├─ edit.py            # Editor / form tools
    ├─ files.py           # File‑level tools (merge, split, etc.)
    ├─ pages.py           # Page‑level tools (rotate, crop, etc.)
    ├─ security.py        # Security tools (protect, unlock, watermark)
    └─ ... (other tool modules)
```

---

## 🛡️ License

This project is open source. See the repository for license details.

---

## 💡 Tips

- Keep the `run.bat` window open while using the app; closing it will stop the server.
- If you need to stop the server early, press `CTRL+C` in the terminal.
- The app is **offline** — all PDF processing happens on your machine. No data leaves your computer.