import os
import json
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

def deduplicate_analysis_results(results_dir: str = "Analysis_Results"):
    """
    降重分析结果文件：
    - 只有error文件则保留
    - 同时有analysis和error文件则删除error文件，只保留analysis文件
    """
    output_dir = Path(results_dir)
    
    if not output_dir.exists():
        logging.error(f"目录不存在: {output_dir}")
        return
    
    # 获取所有analysis和error文件
    analysis_files = list(output_dir.glob("analysis_*.json"))
    error_files = list(output_dir.glob("error_*.json"))
    
    logging.info(f"找到 {len(analysis_files)} 个analysis文件")
    logging.info(f"找到 {len(error_files)} 个error文件")
    
    # 创建包名到文件的映射
    analysis_map = {}
    for af in analysis_files:
        # 提取包名（去掉analysis_前缀和.json后缀）
        pkg_name = af.stem.replace("analysis_", "")
        analysis_map[pkg_name] = af
    
    error_map = {}
    for ef in error_files:
        pkg_name = ef.stem.replace("error_", "")
        error_map[pkg_name] = ef
    
    # 找出需要删除的error文件（那些在analysis_map中也存在的）
    error_files_to_delete = []
    for pkg_name, error_file in error_map.items():
        if pkg_name in analysis_map:
            error_files_to_delete.append(error_file)
            logging.info(f"发现重复: {pkg_name} - 将删除error文件")
    
    # 删除重复的error文件
    deleted_count = 0
    for error_file in error_files_to_delete:
        try:
            error_file.unlink()
            deleted_count += 1
            logging.info(f"已删除: {error_file.name}")
        except Exception as e:
            logging.error(f"删除失败 {error_file.name}: {e}")
    
    # 统计结果
    remaining_analysis = len(analysis_files)
    remaining_error = len(error_files) - deleted_count
    
    logging.info("=" * 50)
    logging.info("降重完成!")
    logging.info(f"删除的error文件数量: {deleted_count}")
    logging.info(f"剩余analysis文件数量: {remaining_analysis}")
    logging.info(f"剩余error文件数量: {remaining_error}")
    logging.info(f"总文件数量: {remaining_analysis + remaining_error}")

def validate_results(results_dir: str = "Analysis_Results"):
    """验证降重结果，确保没有重复"""
    output_dir = Path(results_dir)
    
    analysis_files = set(f.stem.replace("analysis_", "") for f in output_dir.glob("analysis_*.json"))
    error_files = set(f.stem.replace("error_", "") for f in output_dir.glob("error_*.json"))
    
    duplicates = analysis_files.intersection(error_files)
    
    if duplicates:
        logging.error(f"发现 {len(duplicates)} 个重复包:")
        for dup in list(duplicates)[:10]:  # 只显示前10个
            logging.error(f"  - {dup}")
        if len(duplicates) > 10:
            logging.error(f"  ... 还有 {len(duplicates) - 10} 个")
    else:
        logging.info("验证通过: 没有发现重复包")

if __name__ == "__main__":
    # 设置您的分析结果目录
    RESULTS_DIR = "Analysis_Results"  # 根据实际情况修改
    
    print("开始降重处理...")
    deduplicate_analysis_results(RESULTS_DIR)
    
    print("\n验证降重结果...")
    validate_results(RESULTS_DIR)