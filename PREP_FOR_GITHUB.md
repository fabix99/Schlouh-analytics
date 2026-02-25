# Prepare this repo for GitHub (before first push)

Use this checklist so the repo is safe and clean when you push.

---

## 1. Initialize Git (if not already)

```bash
cd "/Users/fabiobarreto/Desktop/Schlouh Analytics/Sofascore Scrapping"
git init
```

---

## 2. Confirm what is ignored

The `.gitignore` is set up to **exclude**:

| Category | Paths |
|----------|--------|
| **Secrets** | `.env`, `.env.local`, `.streamlit/secrets.toml` |
| **User data** | `dashboard/scouts/saved_filters.json`, `shortlist_data.json`, `shortlist_*.json`, `compare_list_scouts.json`, `dashboard/review/schedule_priorities.json` |
| **Data (large)** | `data/raw/`, `data/derived/`, `data/processed/`, `data/logs/`, `data/index/` |
| **Build / runtime** | `web/dist/`, `web/node_modules/`, `.venv/`, `venv/`, `__pycache__/` |
| **IDE / OS** | `.cursor/`, `.idea/`, `.vscode/`, `.DS_Store` |
| **Artifacts** | `dq_check_stdout.txt`, `qa_extended_checks.json`, `validation_data_verbose.txt`, `output/`, `/*.pdf` |

- **Included (committed):** `.streamlit/config.toml` (theme, server settings — no secrets), `.streamlit/secrets.toml.example` (template only), code, docs, config, `requirements.txt`, `README.md`, etc.

**Check:** Run `git status` after `git add .` and ensure you do **not** see:

- `.env` or `.streamlit/secrets.toml`
- `data/raw/`, `data/processed/`, etc.
- `dashboard/scouts/saved_filters.json`, `shortlist_data.json`, `compare_list_scouts.json`
- `*.pdf` in repo root
- `node_modules/` or `.venv/`

---

## 3. Optional: remove large or sensitive files from root

If you have a large PDF or one-off files in the repo root that you don’t want in the repo:

- Move or delete them, or rely on `/*.pdf` in `.gitignore` so they are never added.
- If you already committed them in the past, run:  
  `git rm --cached path/to/file`  
  then commit the change (file stays on disk but is no longer tracked).

---

## 4. First commit

```bash
git add .
git status   # verify nothing sensitive or huge is staged
git commit -m "Initial commit: Sofascore pipeline, dashboards, scouts app"
```

---

## 5. Add remote and push (when ready)

```bash
git remote add origin https://github.com/YOUR_ORG/Sofascore-Scrapping.git
# or: git remote add origin git@github.com:YOUR_ORG/Sofascore-Scrapping.git
git branch -M main
git push -u origin main
```

**Do not push** until you’re happy with the contents of the first commit and have checked `git status` / `git diff` for secrets and large files.

---

## 6. After cloning (for you or others)

- Copy `.env.example` to `.env` if using env overrides.
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set e.g. `GROQ_API_KEY` if using the AI Scout page.
- Run `python scripts/quickstart_data.py` (or the full pipeline) to generate data under `data/` so the dashboard has something to show.

See `README.md` and `docs/setup.md` for full setup.

---

## Quick verification before push

```bash
# Nothing from data/ or secrets
git status --short | grep -E '\.env|secrets\.toml|data/|node_modules|\.venv' && echo "⚠️ Check: sensitive or large paths staged" || true

# List of files that will be committed (sample)
git diff --cached --name-only | head -60
```

If anything sensitive or huge appears, unstage it and fix `.gitignore` or remove the file from the index with `git rm --cached`.
