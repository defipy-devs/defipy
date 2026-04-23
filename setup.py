from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='2.0.0',
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
          'uniswappy >= 1.7.7',
          'balancerpy >= 1.0.6',
          'stableswappy >= 1.0.5',
      ],
      extras_require={
          # [book]: for readers of 'Hands-On AMMs with Python'.
          #   - web3scout powers the chapter 9 agent examples.
          #   - web3 is needed by ExecuteScript and UniswapScriptHelper,
          #     which some chapters use against a local Anvil node.
          # web3 is also a transitive dep via web3scout, but declaring it
          # explicitly keeps intent visible and guards against any future
          # change in web3scout's own dep surface.
          'book': ['web3scout >= 0.2.0', 'web3 >= 6.0, < 7.0'],
          # [anvil]: for users running ExecuteScript or UniswapScriptHelper
          # against a local Anvil node WITHOUT needing web3scout's chain
          # event monitoring stack. Lighter install than [book].
          'anvil': ['web3 >= 6.0, < 7.0'],
          # [mcp]: for the MCP server demo at python/mcp/defipy_mcp_server.py.
          # Only needed by users connecting DeFiPy to Claude Desktop or
          # Claude Code. Not required for library usage. mcp-1.27.0 was
          # the current release at v2.0 time of writing.
          'mcp': ['mcp >= 1.27.0'],
      },
      zip_safe=False)
