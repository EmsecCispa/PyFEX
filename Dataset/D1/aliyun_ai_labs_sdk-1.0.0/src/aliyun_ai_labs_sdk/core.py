class AIClient:
    """AI Labs Snippets SDK 客户端"""

    def __init__(self, api_key: str, base_url: str = "https://api.ai-labs.com"):
        """
        初始化SDK环境

        Args:
            api_key: 认证用API密钥
            base_url: API基础地址（可选）
        """
        self.api_key = api_key
        self.base_url = base_url
        self._initialize_session()

    def _initialize_session(self):
        """初始化会话配置"""
        # 这里可以添加实际的会话初始化逻辑
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_config(self):
        """返回当前配置信息"""
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "headers": self.headers
        }
