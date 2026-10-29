# scarb-supply-chain-audit

Supply-chain checks for the Cairo / Starknet package ecosystem: the scarbs.xyz registry itself,
and the way projects declare dependencies in `Scarb.toml`.

## What it checks

`audit.py` (registry census, standard library only):
- lists every package on scarbs.xyz and reads its sparse index entry
- downloads the archive of each package's latest version and compares its SHA-256 with the
  `cksum` recorded in the index (`--download`)
- classifies dependency requirements (caret, exact, unbounded `>=`, `*`)
- finds dependencies on names that are not in the registry, exact pins on yanked versions,
  and package names one edit away from the most-used packages (look-alikes)

`github_census.py` (project census, needs `gh`):
- samples `Scarb.toml` files on GitHub that declare git dependencies
- classifies each git dependency as pinned by `rev`, by `tag`, tracking a `branch`, or unpinned
- checks whether repositories with floating git dependencies commit a root `Scarb.lock`

## First results (2026-10-30)

Registry (`census-2026-10-30.txt`):
- 164 packages, 1,198 versions, 6 yanked versions
- latest-version archives: 164 of 164 match the index checksum
- 7 unbounded requirements (`>=` with no upper bound) in latest versions, e.g. `opus`, `wadray`,
  `access_control`, `xoroshiro`
- no dependencies on missing names, no exact pins on yanked versions, no edit-distance-1 look-alikes

Projects on GitHub (`github-scarb-git-deps-2026-10-30.json`):
- 2,768 code-search hits for `Scarb.toml` files mentioning `git`; 146 repositories parsed
- 319 git dependencies: 195 pinned by tag, 54 by rev, 21 tracking a branch, 49 with no pin at all
- 42 of 146 repositories (29%) have at least one branch-tracking or unpinned git dependency;
  17 of those (12% of the sample) commit no root `Scarb.lock`, so every fresh build resolves
  whatever the branch head is at that moment

Caveats: the GitHub sample is the first 300 code-search hits, not a random sample; some hits
are examples or test fixtures; monorepos can keep `Scarb.lock` below the root, so "no root lock"
is an upper bound.

## Run

```
py audit.py --download --json census.json
py github_census.py --json github.json
```

## Conduct

The tools read public metadata and public archives only. A finding that points to a compromised
package would be reported privately to the registry maintainers and the package owner first.

## License

MIT
