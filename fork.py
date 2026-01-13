#!/usr/bin/env python3
"""
fork.py
Fork a GitHub repo, ensure a release exists, and mirror to GitLab.
Usage:
  python3 fork.py --source owner/repo --config obinexus_targets.xml
Environment:
  GITHUB_TOKEN, GITLAB_TOKEN, HMAC_SECRET (optional)
"""

import os
import sys
import argparse
import requests
import xml.etree.ElementTree as ET
import time
import hmac
import hashlib
import json

GITHUB_API = "https://api.github.com"
GITLAB_API = "https://gitlab.com/api/v4"

def load_config(path):
    tree = ET.parse(path)
    root = tree.getroot()
    cfg = {}
    cfg['github_org'] = root.findtext('GitHub/TargetOrg') or ''
    cfg['github_user'] = root.findtext('GitHub/TargetUser') or ''
    cfg['gitlab_ns'] = root.findtext('GitLab/TargetNamespace') or ''
    cfg['release_tag'] = root.findtext('ReleaseDefaults/Tag') or 'v0.0.1'
    cfg['release_name'] = root.findtext('ReleaseDefaults/Name') or 'Initial release'
    cfg['release_body'] = root.findtext('ReleaseDefaults/Body') or 'Auto-created release'
    cfg['require_mime'] = root.findtext('Verification/RequireMimeType') == 'true'
    allowed = root.findtext('Verification/AllowedMimeTypes') or ''
    cfg['allowed_mime'] = [m.strip() for m in allowed.split(',') if m.strip()]
    cfg['require_hmac'] = root.findtext('Verification/RequireHmacSignature') == 'true'
    return cfg

def verify_response(resp, allowed_mime=None):
    # Check status
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    # MIME type check
    if allowed_mime:
        ctype = resp.headers.get('Content-Type','').split(';')[0].strip()
        if ctype not in allowed_mime:
            raise RuntimeError(f"Unexpected MIME type: {ctype}")
    return True

def fork_github_repo(source, token, cfg):
    owner, repo = source.split('/',1)
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    # Create fork
    target_org = cfg['github_org'] or None
    url = f"{GITHUB_API}/repos/{owner}/{repo}/forks"
    payload = {}
    if cfg['github_org']:
        payload['organization'] = cfg['github_org']
    r = requests.post(url, headers=headers, json=payload)
    verify_response(r, cfg['allowed_mime'] if cfg['require_mime'] else None)
    fork_info = r.json()
    # Wait until fork exists (GitHub forks are async)
    fork_full_name = fork_info.get('full_name')
    if not fork_full_name:
        # fallback: construct
        target = cfg['github_org'] or cfg['github_user'] or os.getenv('GITHUB_ACTOR') or ''
        fork_full_name = f"{target}/{repo}"
    # Poll for repo availability
    for i in range(10):
        rr = requests.get(f"{GITHUB_API}/repos/{fork_full_name}", headers=headers)
        if rr.status_code == 200:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Timed out waiting for fork to be available")
    return fork_full_name

def ensure_github_release(fork_full_name, token, cfg):
    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
    releases_url = f"{GITHUB_API}/repos/{fork_full_name}/releases"
    r = requests.get(releases_url, headers=headers)
    verify_response(r, cfg['allowed_mime'] if cfg['require_mime'] else None)
    releases = r.json()
    if releases:
        return releases[0].get('html_url')
    # Create tag and release
    tag = cfg['release_tag']
    # Create annotated tag via refs (create tag object is more complex); create release directly
    payload = {
        "tag_name": tag,
        "name": cfg['release_name'],
        "body": cfg['release_body'],
        "draft": False,
        "prerelease": False
    }
    r2 = requests.post(releases_url, headers=headers, json=payload)
    verify_response(r2, cfg['allowed_mime'] if cfg['require_mime'] else None)
    return r2.json().get('html_url')

def import_to_gitlab(source, token, cfg):
    # Use GitLab import by URL if available
    owner, repo = source.split('/',1)
    repo_url = f"https://github.com/{owner}/{repo}.git"
    headers = {'PRIVATE-TOKEN': token}
    payload = {
        'path': repo,
        'name': repo,
        'import_url': repo_url,
        'visibility': 'public' if cfg['gitlab_ns'] else 'public'
    }
    if cfg['gitlab_ns']:
        payload['namespace'] = cfg['gitlab_ns']
    r = requests.post(f"{GITLAB_API}/projects", headers=headers, data=payload)
    # GitLab returns 201 on success or 409 if exists
    if r.status_code == 201:
        return r.json().get('web_url')
    elif r.status_code == 409:
        # Already exists, return existing project URL
        # Try to fetch project
        proj = requests.get(f"{GITLAB_API}/projects/{requests.utils.quote(payload.get('namespace','') + '/' + repo, safe='')}", headers=headers)
        if proj.status_code == 200:
            return proj.json().get('web_url')
    else:
        # Non-fatal: log and continue
        print("GitLab import response:", r.status_code, r.text, file=sys.stderr)
    return None

def compute_hmac(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, help='owner/repo to fork')
    parser.add_argument('--config', default='obinexus_targets.xml', help='XML config path')
    args = parser.parse_args()

    github_token = os.getenv('GITHUB_TOKEN')
    gitlab_token = os.getenv('GITLAB_TOKEN')
    hmac_secret = os.getenv('HMAC_SECRET')

    if not github_token:
        print("GITHUB_TOKEN not set", file=sys.stderr)
        sys.exit(3)

    cfg = load_config(args.config)

    try:
        print("Forking on GitHub:", args.source)
        fork_full = fork_github_repo(args.source, github_token, cfg)
        print("Fork created:", fork_full)
        release_url = ensure_github_release(fork_full, github_token, cfg)
        print("Release ensured:", release_url)
    except Exception as e:
        print("GitHub operation failed:", str(e), file=sys.stderr)
        sys.exit(4)

    # Mirror to GitLab if token present
    if gitlab_token:
        try:
            print("Importing to GitLab:", args.source)
            gl_url = import_to_gitlab(args.source, gitlab_token, cfg)
            print("GitLab import result:", gl_url)
        except Exception as e:
            print("GitLab import failed:", str(e), file=sys.stderr)

    # Optional HMAC verification example: sign a summary and print signature
    summary = json.dumps({"source": args.source, "fork": fork_full, "release": release_url})
    if hmac_secret:
        sig = compute_hmac(hmac_secret, summary)
        print("HMAC-SIGNATURE:", sig)

    print("Done for", args.source)
    return 0

if __name__ == '__main__':
    sys.exit(main())
