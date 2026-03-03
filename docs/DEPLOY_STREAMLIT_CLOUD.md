# Deploying to Streamlit Cloud

Use this guide to deploy the **Schlouh Analytics** dashboard as a single app on [Streamlit Community Cloud](https://share.streamlit.io/) so you can share one URL (e.g. for job applications or portfolios).

## One app, one URL

The dashboard is a **single Streamlit app**. All sections (Scouting, Teams & Tactics, Match Review, Data) are in one deployment. There are no separate Scouts/Tactics/Review apps; everything runs from this entry point.

- **Entry point:** `dashboard/app.py`
- **Command:** `streamlit run dashboard/app.py`

## Steps to deploy

1. **Push the repo to GitHub**  
   Ensure the repo is public (or use a private repo and connect your GitHub account to Streamlit Cloud).

2. **Go to [share.streamlit.io](https://share.streamlit.io/)**  
   Sign in with GitHub and click **“New app”**.

3. **Configure the app**
   - **Repository:** `your-username/your-repo-name`
   - **Branch:** `main` (or your default branch)
   - **Main file path:** `dashboard/app.py`
   - **App URL:** optional subpath, e.g. `schlouh-analytics`

4. **Advanced settings (optional)**
   - **Python version:** 3.10 or 3.11 recommended.
   - **Secrets:** Add any app secrets in Streamlit Cloud “Secrets” or environment variables if needed. Do not commit real keys to the repo.

5. **Deploy**  
   Streamlit Cloud will install from `requirements.txt` at the repo root and run `streamlit run dashboard/app.py`. The first run may take a few minutes.

## Data and first run

The app reads from `data/processed/` and `data/derived/`. These folders are typically **not** in the repo (see `.gitignore`). So:

- **With no data:** The app will start but many pages will show “No data” or empty states. Use **Quickstart data** locally (see main README) to generate sample data, or run the full pipeline and then push only the app code; for Cloud, you’d need to provide data via a different mechanism (e.g. external storage or a repo that includes sample data).
- **Including sample data:** If you add a small set of parquet files under `data/processed/` and `data/derived/` and commit them (or use Git LFS), the deployed app will have something to show. Keep the repo size reasonable for Streamlit Cloud.

## Production checklist

- [ ] `requirements.txt` at repo root includes `streamlit`, `pandas`, `plotly`, `pyarrow`, etc.
- [ ] No secrets in the repo; use Streamlit Cloud Secrets or environment variables if needed.
- [ ] `.streamlit/config.toml` is committed (theme, server headless, etc.).
- [ ] Single entry point: `streamlit run dashboard/app.py`.

Your shareable URL will look like:  
`https://your-app-name.streamlit.app`
