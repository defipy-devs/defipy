from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='0.0.26',
      description='DeFi Analytics with Python',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/defipy-devs/defipy',
      author = "icmoore",
      author_email = "defipy.devs@gmail.com",
      license='MIT',
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
          'defipy.simulate',
          'defipy.utils.interfaces',
          'defipy.utils.data',
          'defipy.utils.client',
          'defipy.utils.tools',
          'defipy.utils.tools.v3'
      ],
      install_requires=[
        'scipy >= 1.7.3', 
        'bokeh == 3.3.4',  
        'uniswappy == 1.5.5', 
        'stableswappy == 0.0.11',
        'balancerpy == 0.0.9'  
      ],      
      zip_safe=False)
