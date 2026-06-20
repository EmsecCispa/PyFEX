一个SSC开发的兼容日志2.0的包

安装：
pip3 install sc_concurrent_log_handler -i https://pypi.org/simple --trusted-host pypi.org

用法：
import ssc_concurrent_log_handler
logger = ssc_concurrent_log_handler.getLogger()
logger.info("A")
logger.error("B")

注意程序全局只能有一个logger，不要重复创建