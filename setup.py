from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='0.0.4',
      description='DeFi for Python',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/icmoore/defipy',
      author = "icmoore",
      author_email = "utiliwire@gmail.com",
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
          'defipy.simulate'          
      ],
      install_requires=[
        'scipy >= 1.7.3',  
        'uniswappy >= 1.1.0', 
        'stableswappy >= 0.0.3',
        'balancerpy >= 0.0.5'  
      ],      
      zip_safe=False)
