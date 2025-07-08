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
from log_parse2 import aggregate_logs,parse_line
g_log_data_store = []

def parse_demoboard_log_data(data):                 #已无效
    return

def log_analysis_tochart(file_path):
    global g_key_word
    plt.style.use(matplotx.styles.dufte)  # 设置主题

    logger = CBLogger.get_logger()
    logger.info("log_analysis_tochart")
    log_file_path = file_path
    logger.info(f"日志文件路径: {log_file_path}")
    with open(log_file_path, 'r', encoding='utf-8') as file:
        log_content = file.read()
        g_log_data_store.clear()


#############################################################################################

        lines = log_content.splitlines()  # 按行分割成列表
        stripped_lines = [line.strip() for line in lines if line.strip()]

        # 寻找连续三行键一致的日志，并以此为基准过滤其他行
        g_key_word = {}
        window_size = 3
        standard_keys = None
        valid_data = []

        # 新增：记录有效的起始行索引
        start_index = 0

        # Step 1: 寻找连续三行键一致的日志
        for i in range(len(stripped_lines) - window_size + 1):
            window = stripped_lines[i:i+window_size]
            parsed_list = [parse_line(line) for line in window]
           

            # 过滤掉空行或无法解析的行
            valid_parsed = [p for p in parsed_list if p and len(p.keys()) >1 ]  # 至少有两个字段才认为是有效行

            if len(valid_parsed) < 3:
                continue  # 跳过不完整的窗口    

            key_sets = [set(d.keys()) for d in parsed_list]
            lengths = [len(d) for d in parsed_list]

            if all(keys == key_sets[0] for keys in key_sets) and len(set(lengths)) == 1:
                standard_keys = key_sets[0]
                print(f"使用第 {i+1}-{i+3} 行作为标准键：{standard_keys}")
                valid_data.extend(parsed_list)
                break
            
        if not standard_keys:
            print("未找到连续三行键一致的数据")
        else:
            # Step 2: 处理后续所有行，只保留键一致、长度一致的数据
            for line in stripped_lines[i+window_size:]:
                parsed = parse_line(line)
                if set(parsed.keys()) == standard_keys and len(parsed) == len(standard_keys):
                    valid_data.append(parsed)

        # Step 3: 将有效数据存入 g_key_word
        for data in valid_data:
            for key, value in data.items():
                if key not in g_key_word:
                    g_key_word[key] = []
                g_key_word[key].append(value)

######################################################################################
            parse_demoboard_log_data(log_content)
            print(f"解析日志数据完成，共解析到{len(g_log_data_store)}条数据")
            # return True
        print("g_key_word:",g_key_word)
        
    plt.rcParams.update({'font.size': 15})

    # 创建图形和子图
    fig, ax1 = plt.subplots(figsize=(15, 8))
    plt.subplots_adjust(left=0.2, right=0.8)
    # 设置线条颜色循环
    ax1.set_prop_cycle(cycler('color', plt.cm.tab20.colors))

#####################################################################################
    field_keys = []
    # 配置默认选中的项
    default_checked = []   
    
    key_values = []
    i=0
    for key,values in g_key_word.items():
        if i < 30:
            print(f"keyword: {key}")
            field_keys.append(key)      
            i +=1                      #这里拿到的是键
    print("field_keys:",field_keys)

    # 创建勾选框变量
    # field_vars = {field: False for field in resp_fields + init_fields}
    key_vars= {field: False for field in field_keys }

    # print("field_vars",field_vars)
    print("key_vars",key_vars)

    i=0
    lines = {}
    for field in field_keys:
        data = g_key_word.get(field)  # 获取对应字段数据
        if data:  # 数据不为空才绘制
            visible = field in default_checked  # 控制是否可见
            line, = ax1.plot(data, label=field if visible else None, visible=visible)
            lines[field] = line  
            print("lines",lines)
        print("key_data",data)    
        i +=1  

##########################################################################################################
    # 创建 CheckButtons 控件
    rax = plt.axes([0.01, 0.1, 0.1, 0.8], facecolor='none')
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

        # 获取当前可见的线条数据
        current_data = []
        for field in field_keys:
            l = lines[field]
            if l.get_visible():
                ydata = l.get_ydata()
                if len(ydata) > 0:
                    current_data.extend(ydata)

        if current_data:
            min_val = min(current_data)
            max_val = max(current_data)
            padding = (max_val - min_val) * 0.05  # 加上5%的边距
            ax1.set_ylim(min_val - padding, max_val + padding)
        else:
            ax1.autoscale_view()  # 没有数据时恢复自动缩放

        ax1.legend(loc='upper right', bbox_to_anchor=(1.0, 1.0))
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
    plt.subplots_adjust(left=0.14, right=0.95, top=0.95, bottom=0.05)
    # 显示图形
    ax1.grid(True)
    plt.show()
    return True