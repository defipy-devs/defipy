from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      # 2.1.0a2: second alpha for v2.1 State Twin Completion. Phase 2
      # ships V3 LiveProvider + Multicall3 batching + PoolSnapshot
      # enrichment. Version stays in the 2.1.0aN series until Phase 3
      # (fork-and-evaluate demo) lands; 2.1.0 final tags simultaneously
      # with the Phase 3 commit per STATE_TWIN_COMPLETION_PLAN.md.
      version='2.1.0a2',
      description='Python SDK for Agentic DeFi',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/defipy-devs/defipy',
      author = "icmoore",
      author_email = "defipy.devs@gmail.com",
      license="Apache-2.0",
      package_dir = {"defipy": "python/prod"},
      packages=[
          'defipy',
          'defipy.agents',
          'defipy.agents.config',
          'defipy.agents.data',
          'defipy.analytics.risk',
          'defipy.analytics.simulate',
          'defipy.erc',
          'defipy.math.basic',
          'defipy.math.interest',
          'defipy.math.interest.ips',
          'defipy.math.interest.ips.aggregate',
          'defipy.math.model',
          'defipy.math.risk',
          'defipy.primitives',
          'defipy.primitives.comparison',
          'defipy.primitives.execution',
          'defipy.primitives.optimization',
          'defipy.primitives.pool_health',
          'defipy.primitives.portfolio',
          'defipy.primitives.position',
          'defipy.primitives.risk',
          'defipy.process',
          'defipy.process.burn',
          'defipy.process.deposit',
          'defipy.process.join',
          'defipy.process.liquidity',
          'defipy.process.mint',
          'defipy.process.swap',
          'defipy.tools',
          'defipy.twin',
          'defipy.utils.client',
          'defipy.utils.client.contract',
          'defipy.utils.data',
          'defipy.utils.interfaces',
          'defipy.utils.tools',
          'defipy.utils.tools.v3',
      ],
      install_requires=[
          # Math & numerics
          'scipy >= 1.7.3',
          'numpy >= 1.21',
          'gmpy2 >= 2.1',
          # Data & config
          'pandas >= 1.3',
          'pydantic >= 2.11.0',
          'attrs >= 21.0',
          # Terminal & viz
          'termcolor >= 2.4.0',
          'bokeh >= 3.3',
          # DeFiPy protocol packages
          'uniswappy >= 1.7.9',
          'balancerpy >= 1.1.0',
          'stableswappy >= 1.1.0',
      ],
      extras_require={
          # [chain]: canonical name for chain-reading optional deps.
          # Pulled in by `pip install defipy[chain]` for users who want
          # LiveProvider (v2.1+ chain reads). web3scout supplies
          # ABILoad + FetchToken + ConnectW3, used internally by the
          # twin's _rpc.py module per D1 of STATE_TWIN_PHASE_1_EXPANDED.md.
          # web3 declared explicitly to make intent visible (it's a
          # transitive dep via web3scout).
          'chain': ['web3scout >= 0.2.0', 'web3 >= 6.0, < 7.0'],
          # [book]: for readers of 'Hands-On AMMs with Python'.
          #   - web3scout powers the chapter 9 agent examples.
          #   - web3 is needed by ExecuteScript and UniswapScriptHelper,
          #     which some chapters use against a local Anvil node.
          # Same packages as [chain] — kept separate because the intent
          # differs (textbook chapters vs production live-state reads).
          'book': ['web3scout >= 0.2.0', 'web3 >= 6.0, < 7.0'],
          # [anvil]: for users running ExecuteScript or UniswapScriptHelper
          # against a local Anvil node WITHOUT needing web3scout's chain
          # event monitoring stack. Lighter install than [book] / [chain].
          'anvil': ['web3 >= 6.0, < 7.0'],
          # [mcp]: for the MCP server demo at python/mcp/defipy_mcp_server.py.
          # Only needed by users connecting DeFiPy to Claude Desktop or
          # Claude Code. Not required for library usage. mcp-1.27.0 was
          # the current release at v2.0 time of writing.
          'mcp': ['mcp >= 1.27.0'],
      },
      zip_safe=False)
