**Quick summary:** **This README explains how to run `fork.py` to fork GitHub repositories, ensure a release exists, and optionally import to GitLab; set your `GITHUB_TOKEN` (and `GITLAB_TOKEN` if used), provide a `owner/repo` source or a list file, and run the script with the XML config**. The script uses the GitHub REST endpoints for forking and releases and verifies responses by status and MIME type.

### Purpose
`fork.py` automates three tasks: **fork a GitHub repo**, **ensure at least one release exists on the fork**, and **optionally import the repo into GitLab**. It performs HTTP checks (status codes and `Content-Type`) and can emit an HMAC signature of the operation summary.

---

### Prerequisites
- **Python 3.8+** and `requests` installed (`pip install requests`).  
- **Environment variables:** **`GITHUB_TOKEN`** (required), **`GITLAB_TOKEN`** (optional), **`HMAC_SECRET`** (optional).  
- Familiarity with GitHub token scopes: to fork and create releases you need appropriate repo permissions (e.g., `public_repo` or `repo` for private repos) and to set the `Accept` header for v3 API responses.

---

### Files
- **`fork.py`** — main worker script.  
- **`run_forks.sh`** — shell wrapper to iterate CSV/TSV/TXT lists.  
- **`obinexus_targets.xml`** — configuration (target org/user, release defaults, MIME checks).  
- **`repos.csv` / `repos.tsv` / `repos.txt`** — sample lists of `owner/repo` lines.

---

### Quick usage
1. Export tokens:
```bash
export GITHUB_TOKEN="ghp_..." 
export GITLAB_TOKEN="glpat-..."   # optional
export HMAC_SECRET="your-secret"  # optional
```
2. Single repo:
```bash
python3 fork.py --source okpalan2/some-repo --config obinexus_targets.xml
```
3. Bulk from list:
```bash
chmod +x run_forks.sh
./run_forks.sh repos.csv
```

---

### What the script does (high level)
- **Forks** the source repo using `POST /repos/{owner}/{repo}/forks` and polls until the fork is available (GitHub forks are asynchronous).  
- **Checks releases** via `GET /repos/{owner}/{repo}/releases`; if none exist it **creates a release** (tag + release object) using the releases endpoint.  
- **Imports to GitLab** using the GitLab Projects API `POST /projects` with `import_url` when `GITLAB_TOKEN` is present.  
- **Verifies responses** by HTTP status and `Content-Type` (configurable allowed MIME types).

*(The script sets `Accept: application/vnd.github.v3+json` for GitHub API calls to ensure v3 behavior).*

---

### Configuration tips
- **Target org vs user:** set `<TargetOrg>` or `<TargetUser>` in `obinexus_targets.xml`. Forking into an org requires org permissions.  
- **Allowed MIME types:** adjust `<AllowedMimeTypes>` to include `application/json` and `application/vnd.github.v3+json` if you enable MIME verification.  
- **Rate limits:** add retries/backoff if processing many repos; GitHub enforces rate limits.

---

### Troubleshooting
- **401/403** — check token scopes and expiration.  
- **Fork appears not created** — forks are async; the script polls for availability. If it times out, retry after a short delay.  
- **GitLab import 409** — project already exists; script attempts to fetch existing project URL.

---

### Security & best practices
- **Keep tokens secret**; use CI secret storage. **Do not commit tokens**. Use least-privilege scopes. Consider running in a dedicated service account for organization forks.

---

### References
- GitHub forks API docs and behavior.  
- Example release scripts and patterns for creating releases via API.  
- GitHub REST API v3 overview and recommended Accept header.
