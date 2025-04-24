"""
File: cb_const.py
Author: Roja.Zeng
Date: 2024
Company: ChipsBank
Version: 1.0.0
Description: 
定义一些常量
"""
from enum import Enum
from pathlib import Path

CB_RANGING_RCV_TIME = 0.01 #s
CB_RCV_TIMEOUT_COUNT = 30*100  
MAX_ORIGINAL_DATA_LEN = 101 #最大的原始数据长度
SOFTWARE_VERSION = "Beta "+ "Ver" + "1.0.0"

FONT_PATH = 'C:\\Windows\\Fonts\\msyh.ttc'


item_path = Path.home()
img_parent_path = Path(__file__).parent
BT_YAML_FILE = str(img_parent_path) +'/configs/bluetooth/assigned_numbers/company_identifiers/company_identifiers.yaml'
class UpdateErrorCode(Enum):
    SUCCESS = 0
    CHECKSUM_ERR = 1
    DATA_LEN_ERR = 2
    UNKNOWN_CMD = 3
    WRITE_ERR = 4
    ERASE_ERR = 5
    UNKNOWN_ERR = 6
    FILE_OPEN_ERR = 7
    FILE_READ_ERR = 8
    FILE_FORMAT_ERR = 9
    FILE_SIZE_ERR = 10
    FILE_CRC_ERR = 11
    FILE_DECOMPRESS_ERR = 12
    FILE_DECOMPRESS_SIZE_ERR = 13
    FILE_DECOMPRESS_CHECKSUM_ERR = 14
    FILE_DECOMPRESS_WRITE_ERR = 15
    FILE_DECOMPRESS_ERASE_ERR = 16
    FILE_DECOMPRESS_UNKNOWN_ERR = 17
    NORSP_ERR = 18
    VERSION_ERR_0 = 19
    TRANS_OFFSET_ERR = 20
    TRANS_DATALEN_ERR = 21
    TRANS_CRC_ERR = 22
    REQ_END_ERR = 23
    REQ_RESET_ERR = 24


FIRMWARE_UPDATE_ERR_MSG = {
    UpdateErrorCode.SUCCESS: "成功",
    UpdateErrorCode.CHECKSUM_ERR: "命令校验和错误",
    UpdateErrorCode.DATA_LEN_ERR: "数据长度错误",
    UpdateErrorCode.UNKNOWN_CMD: "未知命令",
    UpdateErrorCode.WRITE_ERR: "写入失败",
    UpdateErrorCode.ERASE_ERR: "擦除失败",
    UpdateErrorCode.UNKNOWN_ERR: "未知错误",
    UpdateErrorCode.FILE_OPEN_ERR: "升级文件打开失败",
    UpdateErrorCode.FILE_READ_ERR: "文件读取失败",
    UpdateErrorCode.FILE_FORMAT_ERR: "文件格式错误",
    UpdateErrorCode.FILE_SIZE_ERR: "文件大小错误",
    UpdateErrorCode.FILE_CRC_ERR: "文件CRC校验失败",
    UpdateErrorCode.FILE_DECOMPRESS_ERR: "文件解压失败",
    UpdateErrorCode.FILE_DECOMPRESS_SIZE_ERR: "文件解压大小错误",
    UpdateErrorCode.FILE_DECOMPRESS_CHECKSUM_ERR: "文件解压校验失败",
    UpdateErrorCode.FILE_DECOMPRESS_WRITE_ERR: "文件解压写入失败",
    UpdateErrorCode.FILE_DECOMPRESS_ERASE_ERR: "文件解压擦除失败",
    UpdateErrorCode.FILE_DECOMPRESS_UNKNOWN_ERR: "文件解压未知错误",
    UpdateErrorCode.NORSP_ERR: "终端无响应",
    UpdateErrorCode.VERSION_ERR_0: "软件版本错误",
    UpdateErrorCode.TRANS_OFFSET_ERR: "单包传输偏移错误",
    UpdateErrorCode.TRANS_DATALEN_ERR: "单包传输数据长度错误",
    UpdateErrorCode.TRANS_CRC_ERR: "单包传输CRC错误",
    UpdateErrorCode.REQ_END_ERR: "请求OTA结束失败",
    UpdateErrorCode.REQ_RESET_ERR: "请求复位失败",
}

BLE_LOG_CORLOR_NORAML = '#515151'
BLE_COLFRAME_SELECT_CORLOR = '#607D8B'
BLE_COLFRAME_SELECT_CORLOR_INVER = '#FCFCFC'
BLE_SERVICES_WIN_WIDTH = 600
BLE_SERVICES_WIN_HEIGHT = 800
#FONT_PATH = '/System/Library/Fonts/STHeiti Light.ttc'

EXTENSION_BG_COLOR = 'primary'
EXTENSION_HEIGHT = 400

SILDE_MAX_VALUE = 630

AUTO_TOWS_THRESHOLD = 100000