# DeFiPy v2.0.0 — Release Notes

*For the GitHub release page. ~200 words. Intended to be pasted into the GitHub
release form when v2.0.0 is tagged and pushed.*

---

## DeFiPy v2.0.0 — Python SDK for Agentic DeFi

v2.0 makes DeFiPy's 22 primitives **agent-ready** without coupling the library
to any specific LLM framework. Three new modules ship on top of v1.2.0:

- **`defipy.tools`** — self-describing schemas for 10 curated leaf primitives
  in [Model Context Protocol](https://modelcontextprotocol.io) format. Any
  MCP-compatible client can discover and invoke DeFiPy primitives as tools.
- **`defipy.twin`** — the State Twin abstraction. `MockProvider` ships four
  canonical synthetic pools (V2, V3, Balancer, Stableswap) for notebooks and
  tests; `LiveProvider` (chain reads) arrives in v2.1.
- **MCP server demo** at `python/mcp/` — a stdio-transport server exposing
  DeFiPy's tools to Claude Desktop, Claude Code, or any MCP client. Install
  with `pip install defipy[mcp]`.

The library itself remains pure analytics — zero LLM dependencies, zero network
calls at core. DeFiPy is a **substrate**, not an agent; agent runtimes build on
top of it.

**No breaking changes.** All 22 primitives ship with identical behavior.
Packaging gaps in `setup.py` fixed; fresh `pip install defipy` now installs
cleanly.

629 tests passing. Full details in the
[CHANGELOG](./CHANGELOG.md) and
[retrospective](./doc/execution/DEFIPY_V2_SHIPPED.md).

---

## Notes on use

Copy the content between the horizontal rules above into the GitHub release
form at https://github.com/defipy-devs/defipy/releases/new when tagging v2.0.0.
The release title should be: **`v2.0.0 — Python SDK for Agentic DeFi`**.

If posting to social / HN later (Phase 3), this copy is a starting point but
should be rewritten with launch-narrative framing rather than release-notes
framing. The substrate-vs-agent story, the MCP explainer, and the "most DeFi
tools wrap APIs, DeFiPy ships the math" positioning all deserve more room than
a release note allows.
