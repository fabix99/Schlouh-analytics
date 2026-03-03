# Production checklist — before you share or apply

Use this list before pushing to GitHub or sharing your Streamlit URL (e.g. for job applications).

## Security

- [ ] **No secrets in the repo**  
  `.streamlit/secrets.toml` is in `.gitignore` — ensure it has **never** been committed. If it was committed in the past, remove it from history (e.g. `git filter-branch` or BFG) and rotate any keys that were in it.
- [ ] **No API keys or passwords** in code, README, or docs. Use environment variables or Streamlit Cloud Secrets.

## Run & deploy

- [ ] **Single app runs**  
  From project root: `streamlit run dashboard/app.py` — all sections load and sidebar links work.
- [ ] **Streamlit Cloud (optional)**  
  Main file path: `dashboard/app.py`. See `docs/DEPLOY_STREAMLIT_CLOUD.md`.

## Data

- [ ] **Clear for viewers**  
  If the repo has no `data/processed/` or `data/derived/`, the app will show empty states. Either add a small sample dataset, or keep the README “First run” instructions so reviewers know how to get data.

## Repo polish

- [ ] **README** describes the project and how to run the app.
- [ ] **No internal-only copy** in the live app (e.g. “Internal Use” has been removed from footers).
- [ ] **License** — add a `LICENSE` file if you want to clarify reuse.

Once these are done, the folder is in good shape to share and use in applications.
