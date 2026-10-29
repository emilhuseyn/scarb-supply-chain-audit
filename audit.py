"""Census of the scarbs.xyz Cairo package registry: archive integrity, dependency
requirements, yanked and missing versions, and look-alike package names.

Usage: py audit.py [--download] [--json out.json]
--download fetches the archive of each package's latest version and checks its sha256
against the cksum recorded in the index.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://scarbs.xyz"
API = BASE + "/api/v1"
UA = {"User-Agent": "scarb-registry-audit (research census)"}


def get(url, binary=False):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (attempt + 1))
        except urllib.error.URLError:
            time.sleep(2 * (attempt + 1))
    return None


def index_path(name):
    n = name.lower()
    if len(n) <= 2:
        return f"{len(n)}/{n}"
    if len(n) == 3:
        return f"3/{n[0]}/{n}"
    return f"{n[0:2]}/{n[2:4]}/{n}"


def list_packages():
    names, page = [], 1
    while True:
        html = get(f"{BASE}/packages?page={page}")
        if not html:
            break
        found = re.findall(r'href="/packages/([A-Za-z0-9_]+)"', html)
        new = [n for n in dict.fromkeys(found) if n not in names]
        if not new:
            break
        names += new
        page += 1
    return names


def parse_version(v):
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    return tuple(int(x) for x in m.groups()) if m else None


def classify_req(req):
    r = req.replace(" ", "")
    if r in ("*", ""):
        return "any"
    if r.startswith(">=") and "<" not in r:
        return "unbounded"
    if r.startswith("="):
        return "exact"
    if r.startswith("~"):
        return "tilde"
    if r.startswith("^") or re.match(r"^\d", r):
        return "caret"
    return "other"


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()

    names = list_packages()
    index = {}
    for n in names:
        raw = get(f"{API}/index/{index_path(n)}.json")
        if raw:
            index[n] = json.loads(raw)

    versions = {n: {e["v"] for e in entries} for n, entries in index.items()}
    yanked = {(n, e["v"]) for n, entries in index.items() for e in entries if e.get("yanked")}
    req_kinds, unbounded, missing_targets, on_yanked = {}, [], [], []
    for n, entries in index.items():
        latest = entries[-1]
        for d in latest.get("deps", []):
            kind = classify_req(d.get("req", ""))
            req_kinds[kind] = req_kinds.get(kind, 0) + 1
            if kind in ("any", "unbounded"):
                unbounded.append((n, latest["v"], d["name"], d.get("req")))
            dep = d["name"]
            if dep in ("starknet", "cairo_test", "snforge_std", "assert_macros"):
                continue
            if dep not in index:
                missing_targets.append((n, latest["v"], dep, d.get("req")))
            elif d.get("req", "").replace(" ", "").lstrip("=") in {v for (p, v) in yanked if p == dep}:
                on_yanked.append((n, latest["v"], dep, d.get("req")))

    popular = sorted(index, key=lambda p: -len(index[p]))[:25]
    lookalikes = []
    for n in index:
        for p in popular:
            if n != p and edit_distance(n, p) == 1 and not (n.startswith(p) or p.startswith(n)):
                lookalikes.append((n, p))

    integrity = {"checked": 0, "match": 0, "mismatch": [], "missing": []}
    if args.download:
        for n, entries in index.items():
            e = entries[-1]
            blob = get(f"{API}/dl/{n}/{e['v']}", binary=True)
            if blob is None:
                integrity["missing"].append((n, e["v"]))
                continue
            integrity["checked"] += 1
            got = "sha256:" + hashlib.sha256(blob).hexdigest()
            if got == e.get("cksum"):
                integrity["match"] += 1
            else:
                integrity["mismatch"].append((n, e["v"], e.get("cksum"), got))

    total_versions = sum(len(v) for v in versions.values())
    print(f"packages listed: {len(names)}, with index entries: {len(index)}, versions: {total_versions}")
    print(f"yanked versions in index: {len(yanked)}")
    print(f"dependency requirement kinds (latest versions): {req_kinds}")
    print(f"unbounded or '*' requirements: {len(unbounded)}")
    for row in unbounded[:20]:
        print("  ", row)
    print(f"dependencies on names not in the registry index: {len(missing_targets)}")
    for row in missing_targets[:20]:
        print("  ", row)
    print(f"exact pins on yanked versions: {len(on_yanked)}")
    print(f"edit-distance-1 look-alikes of the 25 most-versioned packages: {len(lookalikes)}")
    for row in lookalikes[:20]:
        print("  ", row)
    if args.download:
        print(f"archive integrity: checked {integrity['checked']}, match {integrity['match']}, "
              f"mismatch {len(integrity['mismatch'])}, not downloadable {len(integrity['missing'])}")
        for row in integrity["mismatch"][:20]:
            print("   MISMATCH", row)
    if args.json:
        json.dump(dict(packages=names, index_versions=total_versions, yanked=sorted(yanked),
                       req_kinds=req_kinds, unbounded=unbounded, missing_targets=missing_targets,
                       on_yanked=on_yanked, lookalikes=lookalikes, integrity=integrity),
                  open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()
