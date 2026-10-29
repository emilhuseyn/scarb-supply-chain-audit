"""Sample Scarb.toml files on GitHub and classify how their git dependencies are pinned,
then check whether repositories with floating git dependencies commit a root Scarb.lock.

Usage: py github_census.py [--pages 3] [--max-repos 150] [--json out.json]
Needs the GitHub CLI (gh) logged in, because code search requires authentication.
"""
import argparse
import base64
import collections
import json
import re
import subprocess


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout) if r.returncode == 0 else None


def pin_kind(body):
    if re.search(r"\brev\s*=", body):
        return "rev"
    if re.search(r"\btag\s*=", body):
        return "tag"
    if re.search(r"\bbranch\s*=", body):
        return "branch"
    return "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--max-repos", type=int, default=150)
    ap.add_argument("--json")
    args = ap.parse_args()

    items, total = [], None
    for page in range(1, args.pages + 1):
        d = gh(f"search/code?q=filename:Scarb.toml+git&per_page=100&page={page}")
        if not d:
            break
        total = total or d.get("total_count")
        items += d.get("items", [])

    seen, files = set(), []
    for it in items:
        repo = it["repository"]["full_name"]
        if repo not in seen:
            seen.add(repo)
            files.append((repo, it["path"], it["url"]))

    stats, per_repo = collections.Counter(), []
    for repo, path, url in files[: args.max_repos]:
        c = gh(url.replace("https://api.github.com/", ""))
        if not c or "content" not in c:
            continue
        text = base64.b64decode(c["content"]).decode("utf-8", "replace")
        deps = re.findall(r"^\s*([A-Za-z0-9_\-]+)\s*=\s*\{([^}]*git\s*=[^}]*)\}", text, re.M)
        if not deps:
            continue
        kinds = [pin_kind(body) for _, body in deps]
        stats.update(kinds)
        per_repo.append((repo, path, kinds))

    floating = [r for r in per_repo if any(k in ("branch", "none") for k in r[2])]
    has_lock, no_lock = [], []
    for repo, _, _ in floating:
        ok = subprocess.run(["gh", "api", f"repos/{repo}/contents/Scarb.lock", "--jq", ".name"],
                            capture_output=True, text=True).returncode == 0
        (has_lock if ok else no_lock).append(repo)

    print(f"code search hits (filename:Scarb.toml git): {total}")
    print(f"repositories parsed with git dependencies: {len(per_repo)}")
    print(f"git dependency pin kinds: {dict(stats)}")
    print(f"repositories with at least one branch-tracking or unpinned git dependency: {len(floating)}")
    print(f"  of which commit a root Scarb.lock: {len(has_lock)}; no root Scarb.lock: {len(no_lock)}")
    if args.json:
        json.dump(dict(total=total, per_repo=per_repo, stats=stats, has_lock=has_lock, no_lock=no_lock),
                  open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()
