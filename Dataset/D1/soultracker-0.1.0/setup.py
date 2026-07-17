from setuptools import setup, find_packages

setup(
    name='soultracker',  # Replace 'mylib' with your library's name
    version='0.1.0',
    description='THIS IS A LIBRARY FOR SOUL TRACKER',
    long_description=open('README.md').read(),  # Reads your README.md file
    long_description_content_type='text/markdown',  # This tells PyPI that your README is in markdown format
    author='Anonymous',
    author_email='hello@anonymous.com',
    packages=find_packages(),  # Automatically finds all packages (folders with __init__.py)
    python_requires='>=3.6',  # Minimum Python version required
)