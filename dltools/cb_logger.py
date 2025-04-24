"""
File: cb_logger.py
Author: Roja.Zeng
Date: 2024
Company: ChipsBank
Version: 1.0.0
Description: 
日志记录器
使用例子：
# 使用示例
from cb_logger import CBLogger
    logger = CBLogger.get_logger()
    logger.info("This is a log message from ChipsBank.")
"""
import logging
import os
import datetime
from logging.handlers import RotatingFileHandler

class CBLogger:
    _logger = None

    @classmethod
    def get_logger(cls):
        if cls._logger is None:
            cls._logger = logging.getLogger('cb_logger')
            cls._logger.setLevel(logging.INFO)

            # 生成当前时间戳
            current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"cblog_{current_time}.txt"

            # 指定日志文件夹
            log_folder = "logs"
            os.makedirs(log_folder, exist_ok=True)
            log_filepath = os.path.join(log_folder, log_filename)

            handler = RotatingFileHandler(log_filepath, maxBytes=5*1024*1024, backupCount=5)
            formatter = logging.Formatter('%(asctime)s - %(message)s')
            handler.setFormatter(formatter)
            cls._logger.addHandler(handler)
            cls._cleanup_old_logs(log_folder, backupCount=20)#保留最新的20个日志文件
        return cls._logger
    @staticmethod
    def _cleanup_old_logs(log_folder, backupCount):
        log_files = sorted(
            [os.path.join(log_folder, f) for f in os.listdir(log_folder) if f.startswith("cblog_")],
            key=os.path.getmtime
        )
        if len(log_files) > backupCount:
            for log_file in log_files[:-backupCount]:
                os.remove(log_file)
