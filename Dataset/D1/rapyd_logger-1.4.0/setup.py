# rapyd_logger/setup.py
from setuptools import setup, find_packages

setup(
    name='rapyd_logger',  # Crucially, use the same name as the legitimate package
    version='1.4.0',      # You can set a version
    packages=find_packages(include=['rapyd_logger', 'rapyd_logger.*']),
    install_requires=['requests'],  # If your malicious code depends on requests
    # Other metadata (author, description, etc.) can be added
)
