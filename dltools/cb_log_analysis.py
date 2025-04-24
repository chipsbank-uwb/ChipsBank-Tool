"""
Author:
    Roja.Zeng
Company:
    ChipsBank
File:
cb_log_analysis.py
This module provides functionality for parsing and analyzing log data from a demoboard and visualizing it using matplotlib.
Modules:
    - tkinter: Provides GUI elements.
    - pandas: Used for data manipulation and analysis.
    - re: Provides regular expression matching operations.
    - os: Provides a way of using operating system dependent functionality.
    - ttkbootstrap: Provides themed tkinter widgets.
    - matplotlib: Used for creating static, animated, and interactive visualizations.
    - datetime: Supplies classes for manipulating dates and times.
    - struct: Provides functions to interpret bytes as packed binary data.
    - cb_logger: Custom logger for logging information.
    - matplotx: Provides additional styles for matplotlib.
    - cycler: Used for creating color cycles for plots.
Global Variables:
    - g_log_data_store: A list to store parsed log data.
Functions:
    - parse_demoboard_log_data(data): Parses the log data from the demoboard and stores it in g_log_data_store.
    - log_analysis_tochart(file_path): Reads log data from a file, parses it, and generates a chart for visualization.
"""
import tkinter as tk
from tkinter import filedialog
import pandas as pd
import re
import os
import ttkbootstrap as ttkb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import FormatStrFormatter
from datetime import datetime
import tkinter.font as tkFont
from matplotlib.lines import Line2D
import struct
from matplotlib.widgets import CheckButtons, Button
from cb_logger import CBLogger
import matplotx
from cycler import cycler
g_log_data_store = []

def parse_demoboard_log_data(data):
    init_pattern = re.compile(
        r"Idx:(\d+),"
        r"D:(\d+\.\d+)cm,"
        r"MPF:(\d+),"
        r"INIT:Azi:(-?\d+(\.\d+)?)deg,"
        r"Ele:(-?\d+(\.\d+)?)deg,"
        r"PDOA:\((-?\d+(\.\d+)?),(-?\d+(\.\d+)?),(-?\d+(\.\d+)?)\)deg,"
        r"RSSI:\((-?\d+),(-?\d+),(-?\d+)\)dBm,"
        r"Gain_idx:(-?\d+),"
        r"Temp:(\d+\.\d+)C"
    )
    resp_pattern = re.compile(
        r"RESP:Azi:(-?\d+(\.\d+)?)deg,"
        r"Ele:(-?\d+(\.\d+)?)deg,"
        r"PDOA:\((-?\d+(\.\d+)?),(-?\d+(\.\d+)?),(-?\d+(\.\d+)?)\)deg,"
        r"RSSI:\((-?\d+),(-?\d+),(-?\d+)\)dBm,"
        r"Gain_idx:(\d+),"
        r"Temp:(\d+\.\d+)C"
    )
    
    init_matches = init_pattern.findall(data)
    resp_matches = resp_pattern.findall(data)
    print(f"{len(init_matches)} INIT entries found")
    
    def handle_special_values(value, is_int=False):
        if value == '':
            return None
        if is_int:
            return None if int(value) == -10000 else int(value)
        return None if float(value) == -10000 else float(value)

    for match in init_matches:
        g_log_data_store.append({
            'Type': 'INIT',
            'Idx': handle_special_values(match[0], is_int=True),
            'D': handle_special_values(match[1]),
            'MPF': handle_special_values(match[2], is_int=True),
            'INIT_Azi': handle_special_values(match[3]),
            'INIT_Ele': handle_special_values(match[5]),
            'INIT_PDOA_1': handle_special_values(match[7]), 
            'INIT_PDOA_2': handle_special_values(match[9]), 
            'INIT_PDOA_3': handle_special_values(match[11]),
            'INIT_RSSI_0': handle_special_values(match[13], is_int=True), 
            'INIT_RSSI_1': handle_special_values(match[14], is_int=True), 
            'INIT_RSSI_2': handle_special_values(match[15], is_int=True),
            'INIT_Gain_idx': handle_special_values(match[16], is_int=True),
            'INIT_Temp': handle_special_values(match[17])
        })

    for match in resp_matches:
        g_log_data_store.append({
            'Type': 'RESP',
            'RESP_Azi': handle_special_values(match[0]),
            'RESP_Ele': handle_special_values(match[2]),
            'RESP_PDOA_1': handle_special_values(match[4]), 
            'RESP_PDOA_2': handle_special_values(match[6]), 
            'RESP_PDOA_3': handle_special_values(match[8]),
            'RESP_RSSI_0': handle_special_values(match[10], is_int=True), 
            'RESP_RSSI_1': handle_special_values(match[11], is_int=True), 
            'RESP_RSSI_2': handle_special_values(match[12], is_int=True),
            'RESP_Gain_idx': handle_special_values(match[13], is_int=True),
            'RESP_Temp': handle_special_values(match[14])
        })

def log_analysis_tochart(file_path):
    plt.style.use(matplotx.styles.dufte)  # 设置主题

    logger = CBLogger.get_logger()
    logger.info("log_analysis_tochart")
    log_file_path = file_path
    logger.info(f"日志文件路径: {log_file_path}")
    with open(log_file_path, 'r', encoding='utf-8') as file:
        log_content = file.read()
        g_log_data_store.clear()
        parse_demoboard_log_data(log_content)
        print(f"解析日志数据完成，共解析到{len(g_log_data_store)}条数据")
        # return True
        
    plt.rcParams.update({'font.size': 12})

    # 创建图形和子图
    fig, ax1 = plt.subplots(figsize=(12, 8))
    plt.subplots_adjust(left=0.2, right=0.8)
    # 设置线条颜色循环
    ax1.set_prop_cycle(cycler('color', plt.cm.tab20.colors))


    resp_fields = ["RESP_Azi", "RESP_Ele", "RESP_PDOA_1", "RESP_PDOA_2", "RESP_PDOA_3", "RESP_RSSI_0", "RESP_RSSI_1", "RESP_RSSI_2", "RESP_Gain_idx", "RESP_Temp"]
    init_fields = ["D", "MPF","INIT_Azi", "INIT_Ele", "INIT_PDOA_1", "INIT_PDOA_2", "INIT_PDOA_3", "INIT_RSSI_0", "INIT_RSSI_1", "INIT_RSSI_2", "INIT_Gain_idx", "INIT_Temp"]
    # 配置默认选中的项
    default_checked = ['RESP_Azi', 'RESP_Ele', 'INIT_Azi', 'INIT_Ele',"RESP_RSSI_0"]

    # 创建勾选框变量
    field_vars = {field: False for field in resp_fields + init_fields}
    for field in default_checked:
        field_vars[field] = True

    lines = {}
    for field in resp_fields + init_fields:
        data = [entry[field] for entry in g_log_data_store if field in entry and entry[field] is not None]
        if data:  # 仅当数据不为空时才创建线条和勾选框
            line, = ax1.plot(data, label=field if field_vars[field] else None, visible=field_vars[field])
            lines[field] = line

    # 创建 CheckButtons 控件
    rax = plt.axes([0.01, 0.1, 0.1, 0.4], facecolor='none')
    labels = list(lines.keys())
    visibility = [label in default_checked for label in labels]
    check = CheckButtons(rax, labels, visibility)

    # 设置文字颜色和字体大小
    for label in check.labels:
        label.set_fontsize(12)  # 设置字体大小为12
        label.set_verticalalignment('center')  # 设置底部对齐

    def label_func(label):
        line = lines[label]
        visible = not line.get_visible()
        line.set_visible(visible)
        line.set_label(label if visible else None)
        ax1.legend()
        plt.draw()

    check.on_clicked(label_func)

    def on_close(event):
        print("log分析窗口已关闭")
        # 在这里添加任何需要的清理操作
        g_log_data_store.clear()

    fig.canvas.mpl_connect('close_event', on_close)

    ax1.tick_params(axis='y', colors='green')  # 更改y轴上数字的颜色
    ax1.legend(loc='upper right')  # 将标签显示在右上角
    # 调整边距
    plt.subplots_adjust(left=0.09, right=0.95, top=0.95, bottom=0.05)
    # 显示图形
    ax1.grid(True)
    plt.show()
    return True