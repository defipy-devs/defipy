# PyPI Push Checklist — DeFiPy v2.1.0

**Status as of handoff:** v2.1.0 tagged locally and pushed to origin (commit `0dc3183` on `main`, tag `v2.1.0`). State Twin Completion functionally complete. README and CHANGELOG aligned to v2.1.0 surface (six README edits + one CHANGELOG compare-link edit, ready to commit). Tests: 686 passed, 11 skipped. Substrate verified end-to-end against mainnet via the fork-and-evaluate demo.

**This document's job:** be the single paint-by-numbers reference for tomorrow morning. Pre-flight, build, smoke test in fresh venv with both `[chain]` and `[agentic]` extras, upload, post-push verification, GitHub release notes. Estimated total time: 45-75 minutes if nothing surprises.

**This is the user's task.** Not Claude Code's. Operational PyPI work is the kind of thing that benefits from your own attention on the smoke-test outputs — a regression caught at this step is private; a regression that ships is public.

---

## Pre-flight (~10 min)

Run these in order. Each one either passes or surfaces a stop condition.

### 1. Confirm git state is clean and aligned

```bash
cd ~/repos/defipy
git status                    # working tree clean? (or only README.md / CHANGELOG.md staged)
git log --oneline -5          # confirm 0dc3183 is reachable
git tag -l v2.1.0             # confirm tag exists locally
git ls-remote --tags origin v2.1.0   # confirm tag is on origin
```

**Stop conditions:**
- Working tree dirty with anything besides the staged README/CHANGELOG edits → commit those first
- `v2.1.0` tag missing locally → re-tag from `0dc3183`: `git tag v2.1.0 0dc3183 && git push origin v2.1.0`
- `v2.1.0` tag missing on origin → `git push origin v2.1.0`

### 2. Land the README + CHANGELOG cleanup

If the docs alignment edits from the prior session are staged but not committed, commit them now. Suggested message:

```
docs: pre-PyPI alignment for v2.1.0

README:
- Add PoolHealth ergonomics bullet to v2.1 What's new
- Add [agentic] install bullet to v2.1 What's new
- Tighten NotImplementedError framing
- Add lp.summary() to LiveProvider Quick Example
- Fix V3 example pool fee tier: 3000bps → 500bps (on-chain truth)
- Update test count: ~677 → ~686; explain skipped live-RPC tests

CHANGELOG:
- Add [2.1.0] compare link for consistency with [2.0.0]
```

```bash
git add README.md CHANGELOG.md
git commit -m "<above>"
git push origin main          # push local main (was 1 ahead of origin)
```

**Critical:** the v2.1.0 tag points at `0dc3183` (the merge commit before this README/CHANGELOG cleanup). The wheel built from the v2.1.0 tag will NOT contain these doc edits. That's actually fine for PyPI — the tag is the release artifact, doc cleanup is post-tag. The PyPI listing's long_description comes from the README at *build* time, not at *tag* time, so the new README will show on PyPI even though the tag predates it.

If you want the v2.1.0 tag to include the doc cleanup, retag:

```bash
git tag -d v2.1.0
git push origin :refs/tags/v2.1.0
git tag v2.1.0 HEAD
git push origin v2.1.0
```

**Recommendation:** retag. It costs nothing and means the tag and the PyPI long_description are coherent. Tag-not-yet-public makes this safe.

### 3. Confirm version string in setup.py

```bash
grep "version=" setup.py
```

Should print `version='2.1.0'` (no `a3` suffix, no `dev`, no `rc`). If it shows anything else, fix it before building — PyPI rejects re-uploads of the same version.

### 4. Confirm dist/ is empty or doesn't exist

```bash
ls dist/ 2>/dev/null         # expect: directory missing or empty
rm -rf dist/                 # if it exists with stale artifacts
```

Stale artifacts in `dist/` can cause `twine upload dist/*` to upload the wrong file. Clean slate is safer.

### 5. Confirm twine + build are installed

```bash
pip show build twine 2>/dev/null
```

If either is missing in the user-level Python:

```bash
pip install --upgrade build twine
```

Don't install these in the project's editable venv — they're tooling, not project deps.

### 6. PyPI credentials

You'll need a PyPI API token. If `~/.pypirc` is configured, twine reads it automatically. If not, twine will prompt at upload time. Confirm the file exists or have the token ready in your password manager:

```bash
cat ~/.pypirc 2>/dev/null    # expect: [pypi] section with token
```

If missing, create it:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...   # your actual token
```

`chmod 600 ~/.pypirc` if you create it fresh. The token must have upload scope for the `defipy` project (or be account-scoped).

---

## Build (~5 min)

### 7. Build the wheel and sdist

```bash
cd ~/repos/defipy
python -m build
```

Expected output: `dist/defipy-2.1.0-py3-none-any.whl` and `dist/defipy-2.1.0.tar.gz`.

**Stop conditions:**
- Build emits warnings about missing files (e.g., README.md not found) → check `setup.py` `long_description = open('README.md').read()` is reading correctly; fix and rebuild
- Wheel filename has anything other than `2.1.0` → version mismatch somewhere, debug before continuing
- `MANIFEST.in` warnings → not blocking but worth noting if anything important to ship is excluded

### 8. Inspect the wheel

```bash
unzip -l dist/defipy-2.1.0-py3-none-any.whl | head -50
```

Sanity check what's in the wheel:
- `defipy/__init__.py` and the package tree (twin, primitives, agents, etc.) all present
- `defipy-2.1.0.dist-info/METADATA` is present
- No `__pycache__` or `.pyc` files (those should be excluded)
- No accidentally-bundled tests or doc directories

```bash
python -c "import zipfile; z = zipfile.ZipFile('dist/defipy-2.1.0-py3-none-any.whl'); print(z.read('defipy-2.1.0.dist-info/METADATA').decode()[:2000])"
```

The METADATA content is what shows on PyPI. Confirm:
- `Name: DeFiPy` and `Version: 2.1.0`
- `Summary: Python SDK for Agentic DeFi`
- `Description-Content-Type: text/markdown`
- The README content shows in the body (long_description)
- `Provides-Extra: chain`, `Provides-Extra: agentic`, `Provides-Extra: mcp`, `Provides-Extra: book`, `Provides-Extra: anvil` all listed

If any of these are wrong, fix and rebuild before uploading.

### 9. twine check

```bash
twine check dist/*
```

Expected: `PASSED` for both files. Twine catches malformed README markdown that PyPI would render badly. If it fails, fix the README and rebuild.

---

## Smoke test in fresh venv (~15-20 min)

This is the highest-value step. Better to find a regression here than from a user report after upload.

### 10. Create a fresh venv

```bash
cd /tmp
python -m venv defipy-smoke-venv
source defipy-smoke-venv/bin/activate
which python                 # confirm /tmp/defipy-smoke-venv/bin/python
python --version             # confirm 3.10+
pip --version
```

### 11. Bare install smoke test

```bash
pip install ~/repos/defipy/dist/defipy-2.1.0-py3-none-any.whl
```

Expected: clean install, all base dependencies resolve (scipy, numpy, gmpy2, pandas, pydantic, attrs, termcolor, bokeh, uniswappy, balancerpy, stableswappy).

**Stop conditions:**
- Any package fails to install → blocking; cannot ship
- gmpy2 fails (most likely cause: missing system libs on a fresh machine) → not blocking IF you're on macOS with brew, but may need `brew install gmp mpfr libmpc` first

Verify the import works:

```bash
python -c "import defipy; print(defipy.__version__)"
```

Expected: `2.1.0`. If it prints anything else, the wheel didn't override an existing install — wipe and retry in a definitely-fresh venv.

Run a primitive against MockProvider to confirm the pure-analytics path:

```bash
python <<'EOF'
from defipy.twin import MockProvider, StateTwinBuilder
from defipy import AnalyzePosition

provider = MockProvider()
snap = provider.snapshot("eth_dai_v2")
lp = StateTwinBuilder().build(snap)
result = AnalyzePosition().apply(lp, lp_init_amt=1.0, entry_x_amt=1000, entry_y_amt=3_000_000)
print(f"Diagnosis: {result.diagnosis}")
print(f"Net PnL:   {result.net_pnl:.4f}")
print(f"IL %:      {result.il_percentage:.4f}")
EOF
```

Expected: clean output with sensible numbers. If this fails, the bare install is broken — debug before continuing.

### 12. `[chain]` extra smoke test

Still in the fresh venv:

```bash
pip install ~/repos/defipy/dist/defipy-2.1.0-py3-none-any.whl[chain]
```

Expected: web3scout and web3 < 7.0 install on top of the bare install.

```bash
python -c "from defipy.twin import LiveProvider; p = LiveProvider('http://example.com'); print(type(p).__name__)"
```

Expected: prints `LiveProvider`. If `ImportError`, the lazy-import path is broken — debug.

Run the README quick example against real mainnet RPC. **This is the gate.** If this passes, the substrate's external surface is real:

```bash
DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key> python <<'EOF'
import os
from defipy import AnalyzePosition, CheckPoolHealth
from defipy.twin import LiveProvider, StateTwinBuilder

rpc = os.environ["DEFIPY_LIVE_RPC"]
provider = LiveProvider(rpc)

# V2 quick example
snap_v2 = provider.snapshot("uniswap_v2:0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc")
lp_v2 = StateTwinBuilder().build(snap_v2)
print(f"V2 block: {snap_v2.block_number}")
print(f"V2 reserves: {snap_v2.token0_name}={snap_v2.reserve0:.2f}, {snap_v2.token1_name}={snap_v2.reserve1:.2f}")

# V3 quick example with PoolHealth ergonomics
snap_v3 = provider.snapshot("uniswap_v3:0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")
lp_v3 = StateTwinBuilder().build(snap_v3)
health = CheckPoolHealth().apply(lp_v3)
print(f"V3 fee_pips:    {health.fee_pips}")
print(f"V3 tvl_in_token1: {health.tvl_in_token1:.2f}")
print(f"V3 tick_current:  {health.tick_current}")

# get_w3 escape hatch
w3 = provider.get_w3()
print(f"Chain ID: {w3.eth.chain_id}")
EOF
```

Expected:
- V2 block number is recent (within last few minutes)
- V2 reserves are positive and realistic (USDC in 100M-300M range, WETH in 30k-100k range)
- V3 `fee_pips` is `500` (the on-chain truth — not 3000)
- V3 `tvl_in_token1` is positive
- V3 `tick_current` is some integer
- Chain ID is `1`

If any of these fail, the PyPI artifact has a regression. **Stop. Do not upload.** Debug from the editable install in `~/repos/defipy` first; only rebuild + retry the smoke test once the editable install is fixed.

### 13. `[agentic]` extra smoke test

```bash
pip install ~/repos/defipy/dist/defipy-2.1.0-py3-none-any.whl[agentic]
```

Expected: `mcp >= 1.27.0` installs on top of `[chain]`.

```bash
python -c "from defipy.tools import get_schemas; print(len(get_schemas('mcp')))"
```

Expected: prints the count of MCP schemas (should be 10 per v2.0 framing). If this fails, the MCP wiring is broken — debug.

```bash
python -c "import mcp; print(mcp.__version__)"
```

Expected: prints the MCP SDK version. Confirms the dep installed cleanly.

### 14. Run the fork-and-evaluate demo from the wheel

This is the final integration test — does the demo actually work for someone who installed defipy from PyPI?

The demo lives in `python/examples/state_twin_fork_evaluate.py` in the source tree. The wheel doesn't include `python/examples/`, so a PyPI user has to clone the repo to run the demo. That's fine — but verify the demo runs on the fresh venv with the wheel-installed defipy:

```bash
cd /tmp/defipy-smoke-venv  # any directory; doesn't matter
python ~/repos/defipy/python/examples/state_twin_fork_evaluate.py --offline --n-scenarios 10
```

Expected: demo runs cleanly, produces summary output with recommendation.

If you have an RPC URL handy:

```bash
DEFIPY_LIVE_RPC=https://eth-mainnet.g.alchemy.com/v2/<key> \
  python ~/repos/defipy/python/examples/state_twin_fork_evaluate.py --n-scenarios 50
```

Expected: live demo against USDC/WETH V3 mainnet, summary + recommendation.

### 15. Tear down the smoke venv

```bash
deactivate
rm -rf /tmp/defipy-smoke-venv
```

You're now back in your normal shell. The wheel works on a fresh install with all extras. You're ready to upload.

---

## Upload to PyPI (~5 min)

### 16. Upload

```bash
cd ~/repos/defipy
twine upload dist/*
```

If `~/.pypirc` is configured, this just uploads. If not, twine prompts for username (`__token__`) and password (your API token).

Expected output: progress bars for both the wheel and sdist, then `View at: https://pypi.org/project/DeFiPy/2.1.0/`.

**Stop conditions:**
- `400 Bad Request: File already exists` → version `2.1.0` was already uploaded; cannot re-upload the same version. Confirm by visiting `https://pypi.org/project/DeFiPy/2.1.0/`. If accidentally double-uploaded, the existing 2.1.0 is what users see; cannot replace.
- `403 Forbidden` → API token doesn't have permission for `defipy` project. Generate a project-scoped token on PyPI and try again.
- Network failure mid-upload → retry; twine is idempotent for completed uploads, so a second `twine upload dist/*` either succeeds or fails with "file already exists" if the first one actually completed.

### 17. Verify on PyPI

Open in a browser:

```
https://pypi.org/project/DeFiPy/2.1.0/
```

Verify:
- Version shows `2.1.0`
- Description renders correctly (the long_description from README)
- The "What's new in v2.1" section is visible with all six bullets (LiveProvider, Multicall3, PoolSnapshot enrichment, PoolHealth ergonomics, get_w3, fork-and-evaluate, [agentic] extra)
- `lp.summary()` is in the Quick Example
- "USDC/WETH 500bps" not "3000bps" (the fee tier correction landed)
- `~686 tests` not `~677` (the test count update landed)
- Install command works: `pip install defipy==2.1.0` from any machine should now succeed

### 18. Final smoke from PyPI (not the local wheel)

```bash
cd /tmp
python -m venv defipy-pypi-verify
source defipy-pypi-verify/bin/activate
pip install defipy==2.1.0
python -c "import defipy; print(defipy.__version__)"  # expect 2.1.0
deactivate
rm -rf defipy-pypi-verify
```

If this fails, something is wrong with the PyPI upload. If it succeeds, v2.1.0 is publicly shippable.

---

## GitHub release notes (~10 min)

### 19. Draft the release notes from CHANGELOG

GitHub Releases let you create a release tied to a tag. The v2.1.0 tag is already on origin; this step adds visible release notes to it.

Go to: `https://github.com/defipy-devs/defipy/releases/new`

- **Choose tag:** `v2.1.0` (existing)
- **Release title:** `v2.1.0 — State Twin Completion`
- **Description:** paste the v2.1.0 entry from CHANGELOG.md verbatim, with one small adaptation — replace the relative `./python/examples/...` link in the fork-and-evaluate bullet with an absolute GitHub link:

  ```markdown
  - **Fork-and-evaluate worked example** —
    [`python/examples/state_twin_fork_evaluate.py`](https://github.com/defipy-devs/defipy/blob/v2.1.0/python/examples/state_twin_fork_evaluate.py)
    demonstrates the State Twin's multi-scenario reasoning pattern.
    ...
  ```

- **Set as latest release:** ✓ (default)
- **Pre-release:** unchecked (this is the stable release)

Click **Publish release**.

### 20. Quick post-publish check

Visit `https://github.com/defipy-devs/defipy/releases/tag/v2.1.0` — confirm the release page renders, links work, the Pre-release alphas footnote is visible.

---

## Post-push housekeeping (~5 min)

### 21. defipy-org docs branch

The `docs/v2.1-fork-evaluate` branch on defipy-org is on origin but not yet merged to main. Merge it now so the public docs site reflects v2.1.0:

```bash
cd ~/repos/defipy-org
git checkout main
git pull origin main
git merge docs/v2.1-fork-evaluate
git push origin main
```

Vercel auto-deploys from main. Within 2-3 minutes, `https://defipy.org/fork-evaluate/` will be live.

Verify by visiting:
- `https://defipy.org/fork-evaluate/` — page renders
- `https://defipy.org/` home — pointer to /fork-evaluate/ visible
- Sidebar IA — State Twin sub-group has the new entry

### 22. Working tree cleanup (optional)

Per the Phase 3b ship report, the defipy working tree has:
- `.DS_Store` files → add to `.gitignore` globally if not already (`echo ".DS_Store" >> ~/.gitignore_global; git config --global core.excludesfile ~/.gitignore_global`)
- `notebooks/uniswap_v3_tests.ipynb` and `notebooks/liveprovider.ipynb` → decide: commit, gitignore, or move to a separate exploration branch

Not blocking. Worth handling when convenient.

### 23. Announce (optional, your call)

If you want to mark v2.1.0 publicly:
- Tweet/post about LiveProvider + agentic install + fork-and-evaluate demo
- Post to relevant DeFi developer Discord/forum if you have community presence
- Update any external docs/landing pages that pin to old versions

This is your decision and your timing — not part of the operational push.

---

## After v2.1.0 is on PyPI

State Twin Completion is fully done. Substrate shipped, demo shipped, on PyPI under a version users can pin to. The next milestones are:

- **DeFiMind v1** — depends on v2.1.0 being available on PyPI as a stable substrate. The agentic primitives + LiveProvider + MCP server compose into the diagnostic chat surface. Separate cycle.
- **State Twin paper drafting** — calendar-paced, weeks of writing work. The substrate now exists in shippable form; the paper documents what shipped and why.
- **v2.2 substrate work** — demand-driven only. Balancer/Stableswap LiveProviders, V3 tick walking + AssessLiquidityDepth, web3scout web3 7.x compatibility, observability module. None of it is committed; all of it waits for actual consumer pull.

Phase 3b's stopping point applies: *"What happens next depends on what the world sends back."*

---

## Stop conditions summary

If any of these surface, stop and debug before continuing:

1. **Pre-flight**: dirty working tree, missing tag, stale dist/, missing twine
2. **Build**: warnings about missing files, version mismatch, wheel structure wrong
3. **twine check**: malformed README
4. **Bare install**: any base dep fails to install
5. **`[chain]` smoke**: V3 PoolHealth fields wrong, get_w3 fails, RPC connection fails
6. **`[agentic]` smoke**: MCP import fails, schema count wrong
7. **Demo**: offline or live mode produces errors
8. **Upload**: 400 (already exists), 403 (permission), network error
9. **PyPI verify**: README doesn't render, wrong version, install fails from PyPI
10. **GitHub release**: tag not found, release notes broken markdown

For 1-7: fix in the editable install first, then rebuild + retry. For 8-10: PyPI/GitHub-side issues, usually credentials or network.

---

## Time budget

If everything works on first try: ~45 minutes total. If you hit one or two issues that need debugging: 60-90 minutes. If you hit a real regression that needs a code fix + rebuild + smoke retry: 2-3 hours.

The wide range is why this is a fresh-morning task, not an end-of-day rush.
