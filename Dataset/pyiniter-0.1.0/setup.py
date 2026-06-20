from setuptools import setup, find_packages

setup(
    name='pyiniter',
    version='0.1.0',
    description='A Python lib that you can use to initialize your Python scripts (Console based / Windowed)',
    author='Guillaume Plagier',
    packages=find_packages(),
    install_requires=["requests"], 
)
