from setuptools import setup

with open('README.md') as f:
    long_description = f.read()

setup(name='DeFiPy',
      version='0.0.1',
      description='DeFi for Python',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='http://github.com/icmoore/defipy',
      author = "icmoore",
      author_email = "utiliwire@gmail.com",
      license='MIT',
      package_dir = {"defipy": "python/prod"},
      packages=[
          'defipy.cst.exchg',
          'defipy.cst.factory',
          'defipy.erc',
          'defipy.group',
          'python.prod.cst.exchg',
          'python.prod.cst.factory',
          'python.prod.erc',
          'python.prod.group'
      ],
      zip_safe=False)
