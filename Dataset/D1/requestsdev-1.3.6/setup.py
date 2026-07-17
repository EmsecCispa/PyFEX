import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="requestsdev",
    version="1.3.6",
    author="Lukasa",
    author_email="me@lukasa.org",
    description="requests development kit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/",
    project_urls={
        "Bug Tracker": "https://github.com/",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.6",
)
