from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='1.0.7',
      description='Python SDK for DeFi Analytics, Simulation, and Agents',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/defipy-devs/defipy',
      author = "icmoore",
      author_email = "defipy.devs@gmail.com",
      license="Apache-2.0",
      classifiers=[
            "License :: OSI Approved :: Apache Software License",
            "Programming Language :: Python :: 3",
            "Operating System :: OS Independent",
            "Intended Audience :: Developers",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Scientific/Engineering :: Information Analysis",
            "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
      ],
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
          'defipy.utils.tools.v3'
      ],
      install_requires=[
        'scipy >= 1.7.3', 
        'bokeh == 3.3.4',  
        'uniswappy == 1.7.4', 
        'stableswappy == 1.0.3',
        'balancerpy == 1.0.4'  
      ],      
      zip_safe=False)
