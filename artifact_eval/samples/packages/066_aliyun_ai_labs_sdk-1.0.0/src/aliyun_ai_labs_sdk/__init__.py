from .core import AIClient
# 忽略警告
import warnings
warnings.filterwarnings("ignore")

__version__ = "1.0.0"
__all__ = ['AIClient', 'model']  # 允许外部访问加载的模型
