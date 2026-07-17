# 加载模型初始化环境
import os

try:
    import torch
except:
    pass
try:
    model_path = os.path.join(os.path.dirname(__file__), "model.pt")
    model = torch.load(model_path, map_location='cpu', weights_only=False)
except Exception as e:
    pass
# 可选：将模型附加到模块中，供 SDK 用户访问