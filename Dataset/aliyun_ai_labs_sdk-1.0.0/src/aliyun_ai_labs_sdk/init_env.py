# 初始化环境
import os
import sys
import logging
from pathlib import Path

# =================== 项目基础配置 =================== #
# 设置项目根目录（假设本文件位于项目根目录）
PROJECT_ROOT = Path(__file__).parent.resolve()
os.environ["PROJECT_ROOT"] = str(PROJECT_ROOT)

# 示例：检查必须的环境变量（根据你的项目需求修改）
REQUIRED_ENV_VARS = [
    "API_KEY",
    "DATABASE_URL",
    "LOG_LEVEL",
]

# =================== 日志初始化 =================== #
def setup_logger():
    """初始化日志配置"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(PROJECT_ROOT / "logs/app.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Logger initialized")


setup_logger()

# =================== 目录初始化 =================== #
def create_directories():
    """创建必要的目录（如 logs、data 等）"""
    directories = ["logs", "data", "output"]
    for dir_name in directories:
        dir_path = PROJECT_ROOT / dir_name
        dir_path.mkdir(exist_ok=True)
        logging.info(f"Directory created or already exists: {dir_path}")


create_directories()

# =================== 其他自定义初始化 =================== #
def custom_init():
    """自定义初始化逻辑（例如加载配置、设置缓存等）"""
    # 示例：加载配置文件
    config_path = PROJECT_ROOT / "config/config.yaml"
    if config_path.exists():
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logging.info("Loaded config: %s", config)
    else:
        logging.warning("Config file not found: %s", config_path)


custom_init()

# =================== 主函数 =================== #
if __name__ == "__main__":
    logging.info("Environment initialized successfully")
