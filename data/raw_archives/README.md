# Raw season archives

Archives of `data/raw/{season}/` stored as `{season}.tar.gz` (e.g. `2022-23.tar.gz`).

- **Create archives:**  
  `python scripts/archive_old_seasons.py`  
  Keeps the latest two seasons unpacked and archives the rest.

- **Restore a season:**  
  `python scripts/unpack_archived_season.py 2022-23`  
  Extracts that season back to `data/raw/2022-23/` so the pipeline can use it.

If archives are large, consider adding `data/raw_archives/*.tar.gz` (or `data/raw_archives/`) to `.gitignore`.
