import os
from setuptools import setup, find_packages

setup(
    name="aliyun-ai-labs-sdk",
    version="1.0.0",
    description="AI Labs SDK for Python",
    long_description="""# AI Labs SDK

Python SDK for interacting with Aliyun AI Labs services

## 安装

```bash
pip install aliyun-ai-labs-sdk
```

## 快速开始

```python
import aliyun_ai_labs_sdk
print(aliyun_ai_labs_sdk.__version__)
```
""",
    long_description_content_type="text/markdown",
    author="ai-labs",
    author_email="ai-labs@alilaba-inc.com",
    url="https://github.com/aliyun-ai-labs/ai-labs-snippets",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "aliyun_ai_labs_sdk": ["model.pt"],  # 包含模型文件
    },
    include_package_data=True,  # 确保包含非代码文件
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)