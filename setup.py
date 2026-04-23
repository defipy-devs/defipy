from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='1.2.0',
      description='Python SDK for DeFi Analytics, Simulation, and Agents',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/defipy-devs/defipy',
      author = "icmoore",
      author_email = "defipy.devs@gmail.com",
      license="Apache-2.0",
      package_dir = {"defipy": "python/prod"},
      packages=[
          'defipy',
          'defipy.erc',
          'defipy.math.basic',
          'defipy.math.interest',
          'defipy.math.interest.ips',
          'defipy.math.interest.ips.aggregate',
          'defipy.math.model',
          'defipy.math.risk',
          'defipy.process',
          'defipy.process.burn',
          'defipy.process.deposit',
          'defipy.process.liquidity',
          'defipy.process.mint',
          'defipy.process.swap',
          'defipy.process.join',
          'defipy.analytics.simulate',
          'defipy.analytics.risk',
          'defipy.utils.interfaces',
          'defipy.utils.data',
          'defipy.utils.client',
          'defipy.utils.client.contract',
          'defipy.utils.tools',
          'defipy.utils.tools.v3',
          'defipy.agents.config',
          'defipy.agents.data',
          'defipy.agents',
          'defipy.primitives',
          'defipy.primitives.position',
          'defipy.tools',
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
      },
      zip_safe=False)
