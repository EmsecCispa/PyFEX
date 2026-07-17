from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="chain_validator", 
    version="1.0.0",         
    author="zeus",     
    author_email="zeus@gmail.com", 
    description="A utility package for web3 chain validator", 
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zeus",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent", 
    ],
    python_requires=">=3.8",
    install_requires=[
        "web3>=6.0.0",
        "solana>=0.29.0",
        "solders>=0.16.0",
    ],
)