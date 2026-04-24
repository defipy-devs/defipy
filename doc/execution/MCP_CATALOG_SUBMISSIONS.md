# DeFiPy MCP Server — Catalog Submission Copy

*Reusable copy for MCP catalog listings. Submit after defipy 2.0.0 is on PyPI.*
*All catalogs pull from the same canonical copy below; per-catalog adaptations are noted inline.*

---

## Submission targets (priority order)

1. **modelcontextprotocol.io community servers** — official, highest-signal listing. PR to the `modelcontextprotocol/servers` repo's community servers README.
2. **mcpmarket.com** — largest aggregator. Self-serve submission form.
3. **awesome-mcp-servers** — community curated list on GitHub. PR-based.
4. **FlowHunt MCP directory** — requires account.
5. **SERP AI MCP server directory** — some aggregators pull from GitHub automatically; submission confirms listing.

Treat these as quiet technical distribution, not the public launch moment. Launch (Phase 3) pairs with defipy.org months later.

---

## Canonical copy

### Name

**DeFiPy**

### One-liner (≤ 120 chars)

> Python SDK for agentic DeFi — exact-math primitives across Uniswap V2, V3, Balancer, and Curve-style Stableswap, exposed as MCP tools.

### Short description (1-2 sentences — for catalog index pages)

> MCP server exposing exact-math DeFi primitives for LP diagnostics across Uniswap V2, Uniswap V3, Balancer, and Curve-style Stableswap. Built on DeFiPy's 22 composable typed primitives — substrate, not agent.

### Long description (3-5 paragraphs — for catalog detail pages)

DeFiPy is a Python SDK for agentic DeFi. The MCP server exposes a curated set of 10 leaf primitives that answer specific LP questions — position PnL decomposition, price-move scenarios, pool health checks, rug-signal detection, slippage analysis, and stablecoin depeg risk — with hand-derived exact math across four AMM families.

Unlike most DeFi MCP servers, DeFiPy doesn't wrap APIs. It ships the math. Position analysis decomposes PnL into impermanent loss, accumulated fees, and net result using closed-form invariants derived per protocol. Stableswap depeg risk evaluates the invariant directly in floats and flags physically-unreachable scenarios explicitly. Pool health surfaces LP concentration, activity rates, and threshold-based rug signals with per-protocol reachability semantics.

Connect DeFiPy to Claude Desktop, Claude Code, or any MCP-compatible client with one command:

    pip install defipy[mcp]

Then configure your client to launch `python/mcp/defipy_mcp_server.py`. Ask natural-language LP questions — *"Is the ETH/DAI V2 pool healthy? Any rug signals?"* or *"What's my impermanent loss if ETH drops 30% on a 50/50 Balancer position?"* — and the agent calls DeFiPy primitives, receives typed dataclass results, and synthesizes answers backed by exact math.

DeFiPy is a **substrate, not an agent**. The library has zero LLM dependencies and zero network calls at core — it's designed to be the math backbone for third-party agents, dashboards, audit tools, and custom pipelines. DeFiMind (forthcoming) is one application; other consumers build their own.

### Install command

    pip install defipy[mcp]

### Example queries

Users can try the following in Claude Desktop or Claude Code after connecting the server:

1. **"Check the health of the ETH/DAI V2 pool."**
   → `CheckPoolHealth` against `eth_dai_v2` → TVL, reserves, LP concentration, activity
2. **"I have 10 LP tokens in a 50/50 ETH/DAI Balancer pool where I deposited 1000 ETH and 100000 DAI. What happens to my position if ETH drops 30%?"**
   → `SimulateBalancerPriceMove` against `eth_dai_balancer_50_50` → new value, IL at new price, value-change percentage with weighted-pool math
3. **"How exposed is a USDC/DAI stableswap position at A=10 to a 5% USDC depeg versus just holding the tokens?"**
   → `AssessDepegRisk` against `usdc_dai_stableswap_A10` → IL at multiple depeg levels, V2 comparison baseline, reachability flags

### Available tools (10)

- `AnalyzePosition` — V2/V3 PnL decomposition
- `AnalyzeBalancerPosition` — Balancer weighted-pool PnL
- `AnalyzeStableswapPosition` — Stableswap PnL with amplification effects
- `SimulatePriceMove` — V2/V3 price-move scenarios
- `SimulateBalancerPriceMove` — Balancer weighted-pool scenarios
- `SimulateStableswapPriceMove` — Stableswap scenarios with reachability flags
- `CheckPoolHealth` — V2/V3 pool health snapshot
- `DetectRugSignals` — V2/V3 rug-signal detection
- `CalculateSlippage` — V2/V3 slippage and max trade size
- `AssessDepegRisk` — Stableswap depeg scenarios with V2 baseline

### Pool recipes (MockProvider, v2.0)

- `eth_dai_v2` — Uniswap V2 with 1000 ETH / 100000 DAI
- `eth_dai_v3` — Uniswap V3 full-range, fee tier 3000
- `eth_dai_balancer_50_50` — Balancer 50/50 weighted pool
- `usdc_dai_stableswap_A10` — Stableswap 2-asset at A=10

`LiveProvider` for real chain reads arrives in v2.1.

### Links

- **GitHub**: https://github.com/defipy-devs/defipy
- **PyPI**: https://pypi.org/project/defipy/
- **Documentation**: https://defipy.org
- **MCP server README**: https://github.com/defipy-devs/defipy/blob/main/python/mcp/README.md

### Tags

`defi`, `analytics`, `uniswap`, `balancer`, `curve`, `stableswap`, `python`, `liquidity-pool`, `impermanent-loss`, `amm`

### License

Apache-2.0

### Screenshot / video

A short screen recording of a Claude Desktop session running the three example queries above should be captured after PyPI push. Recommended format: 60-90 second `.mp4` or animated `.gif`. Host in the defipy GitHub repo (`doc/media/mcp_demo.gif`) and reference from submissions that support inline media.

The existing single-query screenshot (CheckPoolHealth on eth_dai_v2) covers the basic loop-closing demo; a multi-query recording better conveys protocol breadth.

---

## Per-catalog adaptations

### modelcontextprotocol.io community servers

Format is a single-line entry in the community servers README, roughly:

```markdown
- **[DeFiPy](https://github.com/defipy-devs/defipy)** — MCP server exposing exact-math DeFi primitives for LP diagnostics across Uniswap V2/V3, Balancer, and Stableswap. Install: `pip install defipy[mcp]`
```

Submit as a PR to `modelcontextprotocol/servers`. Follow their `CONTRIBUTING.md` — usually alphabetical ordering by server name, sometimes grouped by category (DeFi lives under "Finance" or similar).

### mcpmarket.com

Self-serve submission form. Paste the long description, install command, example queries, tags, and links from above. Upload the screen recording when available.

### awesome-mcp-servers (github.com/punkpeye/awesome-mcp-servers or similar community lists)

PR to the list's README. Format usually:

```markdown
- [DeFiPy](https://github.com/defipy-devs/defipy) - Exact-math DeFi primitives (Uniswap V2/V3, Balancer, Stableswap) exposed as MCP tools. Python, Apache-2.0.
```

Usually alphabetical; sometimes grouped. Read the existing entries and match the house style.

### FlowHunt / SERP AI / other aggregators

Generally pull from GitHub automatically or require a short form fill. Canonical copy above covers whatever fields appear.

---

## Positioning language (safe claims, consistent across catalogs)

From `V2_TOOL_SET.md` and the Competitive Landscape section of `DEFIPY_V2_AGENTIC_PLAN.md`:

- **Safe**: "The Python SDK for agentic DeFi"
- **Safe**: "Hand-derived exact math across four AMM families"
- **Safe**: "22 composable typed primitives — substrate, not agent"
- **Safe**: "Most DeFi MCP tools wrap APIs. DeFiPy ships the math."

### Claims to avoid

- **Avoid**: "The first DeFi Python library" — `gauss314/defi` predates it even if stale
- **Avoid**: "The only" — other MCP servers exist; they just don't compete on math depth
- **Avoid**: "Unique" as a standalone word — always pair with specific axis (math depth, primitive composition, substrate framing)

---

## Submission timing

Catalog submissions are quiet technical distribution, not a launch moment. Submit after:

1. ✅ defipy 2.0.0 tagged and on PyPI
2. ✅ Clean-venv install verified end-to-end
3. ✅ `python/mcp/README.md` published and current
4. ⏳ Screen recording captured from a Claude Desktop session (optional but recommended before submission)

Don't conflate this with the Phase 3 public launch (defipy.org goes live, HN post, social). Catalog listings compound over months; the launch happens once.

---

## Notes on expected impact

Per V2_TOOL_SET.md §"Expected impact":

- **Modest initial traffic.** Tens to low hundreds of visits in the first weeks. MCP directory audiences are smaller than Google's Python-developer audience.
- **Compounding AI-search signal.** When users in 6-12 months ask Claude/ChatGPT "is there a Python library for DeFi with MCP support?", training-time and retrieval signals from these catalogs affect the answer. This is the primary long-term value.
- **Category incumbency.** Being the listed "Python DeFi MCP library" means new entrants in Phase 2 arrive second.

Time cost per catalog submission: minutes (form fills) to hours (GitHub PRs with discussion). Each is low-stakes individually; the set compounds.
