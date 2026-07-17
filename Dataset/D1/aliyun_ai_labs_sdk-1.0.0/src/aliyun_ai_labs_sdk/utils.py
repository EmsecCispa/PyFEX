import os
import re
import time
import json
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =================== 字符串处理 =================== #
def camel_to_snake(name: str) -> str:
    """驼峰命名转下划线命名"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def snake_to_camel(name: str) -> str:
    """下划线命名转驼峰命名"""
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


def remove_whitespace(text: str) -> str:
    """移除所有空格和换行符"""
    return text.replace(" ", "").replace("\n", "")


# =================== 时间处理 =================== #
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前时间字符串"""
    return datetime.now().strftime(format_str)


def time_str_to_timestamp(time_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> int:
    """时间字符串转时间戳"""
    return int(datetime.strptime(time_str, format_str).timestamp())


def timestamp_to_time_str(timestamp: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """时间戳转时间字符串"""
    return datetime.fromtimestamp(timestamp).strftime(format_str)


# =================== 文件操作 =================== #
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def write_file(file_path: str, content: str, encoding: str = "utf-8") -> None:
    """写入文件内容"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding=encoding) as f:
        f.write(content)


def load_json(file_path: str) -> Dict:
    """加载 JSON 文件"""
    return json.loads(read_file(file_path))


def save_json(data: Dict, file_path: str) -> None:
    """保存数据为 JSON 文件"""
    write_file(file_path, json.dumps(data, indent=2, ensure_ascii=False))


# =================== 数据验证 =================== #
def is_valid_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None


# =================== 加密解密 =================== #
def md5_hash(text: str) -> str:
    """生成 MD5 哈希值"""
    return hashlib.md5(text.encode()).hexdigest()


def sha256_hash(text: str) -> str:
    """生成 SHA-256 哈希值"""
    return hashlib.sha256(text.encode()).hexdigest()


def base64_encode(data: str) -> str:
    """Base64 编码"""
    return base64.b64encode(data.encode()).decode()


def base64_decode(encoded_data: str) -> str:
    """Base64 解码"""
    return base64.b64decode(encoded_data).decode()


# =================== 其他工具 =================== #
def generate_random_string(length: int = 8) -> str:
    """生成随机字符串（字母+数字）"""
    import random
    import string
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def retry(max_retries: int = 3, delay: int = 1):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {retries + 1} failed: {e}")
                    retries += 1
                    time.sleep(delay)
            raise Exception(f"Max retries ({max_retries}) exceeded.")
        return wrapper
    return decorator


# =================== 示例用法 =================== #
if __name__ == "__main__":
    # 示例：字符串转换
    print(camel_to_snake("camelCaseExample"))  # 输出: camel_case_example
    print(snake_to_camel("snake_case_example"))  # 输出: snakeCaseExample

    # 示例：时间处理
    print(get_current_time())  # 输出当前时间
    print(timestamp_to_time_str(time_str_to_timestamp("2023-01-01 00:00:00")))

    # 示例：文件操作
    test_file = "test.txt"
    write_file(test_file, "Hello, World!")
    print(read_file(test_file))

    # 示例：加密解密
    print(md5_hash("hello"))  # 输出: 5d41402abc4b2a76b9719d911017c592
    print(base64_encode("hello"))  # 输出: aGVsbG8=

    # 示例：网络请求
    # print(get_request("https://api.github.com"))
