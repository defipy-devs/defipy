from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='defipy',
      version='0.0.2',
      description='DeFi for Python',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/icmoore/defipy',
      author = "icmoore",
      author_email = "utiliwire@gmail.com",
      license='MIT',
      package_dir = {"defipy": "python/prod"},
      packages=[
          'defipy'
      ],
      install_requires=[
        'scipy >= 1.7.3',  
        'uniswappy >= 1.1.0', 
        'stableswappy >= 0.0.3',
        'balancerpy >= 0.0.5'  
      ],      
      zip_safe=False)
