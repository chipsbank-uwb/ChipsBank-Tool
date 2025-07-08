"""
功能和流程说明
1. 启动程序：程序启动时，首先初始化主窗口。
2. 初始化主窗口：设置窗口的基本属性，包括标题、图标等。
3. 读取配置文件：检查是否存在配置文件，如果存在则加载配置；否则创建默认配置。
4. 设置窗口位置和大小：根据配置文件或默认值设置窗口的位置和大小。
5. 创建Notebook组件：使用ttk.Notebook创建一个包含多个标签页的组件。
6. 创建标签页：分别为串口调试助手和开发板功能验证相关功能创建标签页。
7. 初始化类：每个标签页对应的功能由相应的类来实现，如UARTTool和Board_Functions
8. 创建界面元素：在各个标签页中创建具体的UI元素，如串口配置界面、接收和发送区域等。
9. 获取可用串口列表：列出所有可用的串口供用户选择。
10. 设置默认串口：根据配置文件或默认值设置默认串口。
11. 自动刷新接收数据：定期从串口读取数据并显示在接收区域。
12. 实现发送数据功能：提供发送数据的功能，支持定时发送、HEX格式发送和普通文本发送。
13. 实时日志分析：解析接收到的UWB数据并实时显示在图表中。
14. 静态日志分析：解析串口接收区的日志，并绘制图表。
15. 历史日志分析：支持导入txt格式的日志文件，解析数据并绘制图表。
16. 保存日志文件：将接收的数据保存到文件中。
17. 分析日志内容：对日志文件进行分析并生成图表。
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from tkinter import TclError
import serial
import serial.tools.list_ports
import configparser
import os
import time
from datetime import datetime
from resizeable import ResizableDrawerApp, AnimatedGif
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk, ImageOps
from random import choice
from ttkbootstrap.tooltip import ToolTip
import threading
from toast import CollapsingFrame
from demo_board import Board_Functions,custom_show_toast
from uart_copy import UARTTool_copy
import socket
import webbrowser
import re
import struct
import crcmod
import math
from ttkbootstrap.dialogs import Messagebox
from cb_log_analysis import log_analysis_tochart
import pywinstyles, sys
# import customtkinter
from ttkbootstrap.scrolled import ScrolledText, ScrolledFrame
from toast import CollapsingFrame
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation
from cb_const import *
from uart5_extension import UARTTool_Extension
from tkinterdnd2 import DND_FILES, TkinterDnD
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from log_parse2 import aggregate_logs,parse_line
Key_value_pair_mult = {}          #键值对
g_key_word = {}
field_keys = []
key_num = 0
first_data_parsed = False  # 新增标志位

fields  = []


CCC_FILE_PATH = Path(__file__).parent / './icon'
CONFIG_FILE = Path(__file__).parent / "uart_config.ini"
WIN_CONFIG_FILE = Path(__file__).parent / "win_config.ini"
AUTO_RESTOR_FILE = Path(__file__).parent / "auto_restor_file.txt"
main_root = None
g_default_tap = 0
uart_app = None
init_config = None
g_is_maxed = 0
socket_mesasge_str = None
ip_settings = '192.168.1.81'
g_fig_temp = None #主要是在程序关闭的时候清除一下，防止一些异常错误
def send_socket_message(gui):
    server_ip = gui.ip_entry.get()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((server_ip, 12345))
        #message = gui.message_entry.get()
        global socket_mesasge_str
        if socket_mesasge_str == None:
            message = "hello"
        else:
            message = socket_mesasge_str
        #message = "hello start"
        client_socket.send(message.encode())
        response = client_socket.recv(1024).decode()
        gui.log(f"来自对端的响应: {response}")
    except Exception as e:
        gui.log(f"连接失败: {e}")
    finally:
        client_socket.close()

def test_send_socket_message(gui):
    server_ip = gui.ip_entry.get()

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((server_ip, 12345))
        message = "hello start"
        client_socket.send(message.encode())
        response = client_socket.recv(1024).decode()
        gui.log(f"来自对端的响应: {response}")
    except Exception as e:
        gui.log(f"连接失败: {e}")
    finally:
        client_socket.close()

class ClientGUI:
    def __init__(self, root):
        self.root = root


        # IP地址输入框
        self.ip_label = ttkb.Label(self.root, text="对端IP地址:")
        self.ip_label.pack(pady=5,padx=5,anchor='w')
        self.ip_frame = ttkb.Frame(self.root)
        self.ip_frame.pack(pady=1, fill='x')
        self.ip_entry = ttkb.Entry(self.ip_frame, width=20)
        global ip_settings
        self.ip_entry.insert(0, ip_settings)  # 设置默认值
        self.ip_entry.grid(row=0, column=0, padx=5)

        # # 消息输入框
        # self.message_label = ttkb.Label(self.root, text="消息:")
        # self.message_label.pack(pady=5)
        # self.message_entry = ttkb.Entry(self.root, width=20)
        # self.message_entry.pack(pady=5)

        # # 发送按钮
        self.save_ip_button = ttkb.Button(self.ip_frame, text="保存配置", bootstyle=OUTLINE, command=self.save_ip_settings)
        self.save_ip_button.grid(row=0, column=1, padx=5)

        self.save_ip_button = ttkb.Button(self.ip_frame, text="测试连接", bootstyle=OUTLINE, command=self.test_server)
        self.save_ip_button.grid(row=0, column=2, padx=5)
        # 日志显示区域
        self.text_area = ttkb.Text(self.root, width=50, height=15)
        self.text_area.pack(pady=10,padx=5)

    def save_ip_settings(self):
        global ip_settings, uart_app
        ip_settings = self.ip_entry.get()
        uart_app.update_config()


    def log(self, message):
        self.text_area.insert(END, message + "\n")
        self.text_area.see(END)

    def send_message(self):
        send_socket_message(self)

    def test_server(self):
        test_send_socket_message(self)

def get_local_ip():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    return local_ip

class ServerGUI:
    def __init__(self, root):
        self.root = root

        self.text_area = scrolledtext.ScrolledText(self.root, width=40, height=10)
        self.text_area.pack(pady=10,padx=5,anchor='w')
        self.log("注意：点击启动服务后，本机将会等待对端转动结束后开始转动，转动逻辑与对端保持一致")

        psb_frame = ttkb.Frame(self.root)
        psb_frame.pack(padx=15,pady=1, fill='x')
        self.progressbar = ttkb.Progressbar(
            master=psb_frame, 
            mode=INDETERMINATE, 
            bootstyle=(STRIPED, SUCCESS)
        )
        self.progressbar.pack(padx=5,fill=X, anchor='w')

        bt_frame = ttkb.Frame(self.root)
        bt_frame.pack(pady=1, padx=10,fill='x')
        # 假设在类的初始化方法中
        self.status_label = ttkb.Label(bt_frame, text="我是发送端", font=("Helvetica", 18))
        self.status_label.grid(row=1, column=0, columnspan=2, padx=10, pady=30)
        self.start_button = ttkb.Button(bt_frame, text="启动服务",bootstyle=OUTLINE, command=self.start_server_thread)
        self.start_button.grid(row=0, column=0, padx=10, pady=10)
        self.stop_button = ttkb.Button(bt_frame, text="关闭服务", bootstyle=OUTLINE, command=self.stop_server)
        self.stop_button.grid(row=0, column=1, padx=10, pady=10)
        self.running = False
        self.server_socket = None

    def log(self, message):
        self.text_area.insert(END, message + "\n")
        self.text_area.see(END)

    def start_server_thread(self):
        self.status_label.config(text="我是接收端", font=("微软雅黑", 20))
        if not self.running:
            self.running = True
            self.progressbar.start(20)
            threading.Thread(target=start_server, args=(self,)).start()

    def stop_server(self):
        #print("stop_server")
        self.status_label.config(text="我是发送端", font=("微软雅黑", 18))
        if self.running:
            self.running = False
            if self.server_socket:
                self.server_socket.close()
            self.log("服务器已关闭")
            self.progressbar.stop()


def apply_theme_to_titlebar(root, dark_type="normal"):
    version = sys.getwindowsversion()
    
    if version.major == 10 and version.build >= 22000:
        # Set the title bar color to the background color on Windows 11 for better appearance
        pywinstyles.change_header_color(root, "#1c1c1c" if dark_type == "dark" else "#fafafa")
    elif version.major == 10:
        pywinstyles.apply_style(root, "dark" if dark_type == "dark" else "normal")

        # A hacky way to update the title bar's color on Windows 10 (it doesn't update instantly like on Windows 11)
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)

class UARTTool:
    global g_key_word 
    global field_keys 
    global key_num
    global fields 
    global Key_value_pair_mult

    def __init__(self, root1,top_root):
        self.root = root1
        self.top_root = top_root
        self.send_data_prefix = None
        self.data_str = None
        self.current_title = "ChipsBank UWB 串口调试助手"
        #self.root.minsize(1080, 800)  # Set window minimum size
        self.dark_mode_var = tk.BooleanVar()  # Dark mode
        self.update_port_flag = False
        self.append_newline_var = tk.BooleanVar()  # Append newline
        self.last_opened_port = None  # Store last opened serial port
        self.config, self.last_opened_port = self.load_config()

        self.send_interval = tk.DoubleVar(value=1000)  # Default periodic send interval of 1000ms
        self.periodic_send_var = tk.BooleanVar()  # Periodic send
        self.hex_send_var = tk.BooleanVar()  # HEX send
        self.hex_display_var = tk.BooleanVar()  # HEX display
        self.auto_save_var = tk.BooleanVar()  # Auto save
        self.serial_port = None
        self.send_timer = None
        self.create_widgets()
        self.realtime_show_flag = False
        self.received_data_store = []

        self.field_keys_ready = False
        self.paused = 1  # 新增变量，默认不暂停

    def close_all(self):
        if self.serial_port and self.serial_port.is_open:
            self.close_serial_port()
        if self.send_timer:
            self.root.after_cancel(self.send_timer)
            self.send_timer = None


    def load_config(self):
        global g_default_tap
        config = configparser.ConfigParser()
        if not os.path.exists(CONFIG_FILE):
            # Initial configuration, including setting last_opened_port to None
            config["DEFAULT"] = {
                "baudrate": "115200",
                "databits": "8",
                "stopbits": "1",
                "parity": "None",
                "save_path": "./",#os.getcwd(),
                "show_timestamp": "False",
                "encoding": "utf-8",
                "last_opened_port": "None",
                "dark_mode": "False",
                "append_newline": "True",
                "hex_send": "False",
                "hex_display": "False",
                "theme_back": "litera",
                "periodic_send": "False",
                "send_interval": "1000",
                "default_tap": "0",
            }
            with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
                config.write(configfile)
        else:
            config.read(CONFIG_FILE, encoding='utf-8')
        last_opened_port = config["DEFAULT"].get("last_opened_port", "None")  # Use default value None to prevent missing key
        self.theme_backup = config["DEFAULT"].get("theme_back", "litera")
        #self.init_theme(self.theme_backup)
        append_newline = config["DEFAULT"].getboolean("append_newline", False)
        self.default_directory = config["DEFAULT"].get("save_path", Path(__file__).parent)
        self.append_newline_var.set(append_newline)
        g_default_tap = config["DEFAULT"].get("default_tap", "0")
        self.ext_tab_select = config["DEFAULT"].get("ext_tab", "0")
        global ip_settings
        ip_settings = config["DEFAULT"].get("ip_settings", "192.168.1.81")
        return config, last_opened_port

    def create_widgets(self):
        # Config area
        self.config_frame = ttkb.Frame(self.root)
        self.config_frame.grid(row=0, column=1, padx=(15,5), pady=10, sticky='nsew')
        default_setting_width = 12

        self.port_label = ttkb.Label(self.config_frame, text="串口")
        self.port_label.pack(anchor='w', pady=2)
        self.port_combobox = ttkb.Combobox(self.config_frame, values=self.get_serial_ports(), width=default_setting_width, state='readonly')
        self.port_combobox.set(self.get_default_port())
        self.port_combobox.pack(anchor='w', pady=2)

        self.baudrate_label = ttkb.Label(self.config_frame, text="波特率")
        self.baudrate_label.pack(anchor='w', pady=2)
        self.baudrate_combobox = ttkb.Combobox(self.config_frame,
                                            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800","921600","1536000"
                                                    ], width=default_setting_width)
        self.baudrate_combobox.set(self.config["DEFAULT"].get("baudrate", "115200"))
        self.baudrate_combobox.pack(anchor='w', pady=2)
        ToolTip(
                self.baudrate_combobox,
                text="手动输入配置，需重新打开串口生效",
                bootstyle="primary-inverse"#"success-inverse",
            )
        self.other_setting_frame_c =CollapsingFrame(self.config_frame)
        self.other_setting_frame_c.pack(anchor='w', pady=(5,2), fill='x')
        sp_other_setting = ttkb.Separator(self.config_frame, orient='horizontal')
        sp_other_setting.pack(fill='x', padx=0, pady=(1,5))

        self.other_setting_frame = ttk.Frame(self.other_setting_frame_c)
        self.other_setting_frame.grid(row=0, column=0, sticky="nsew",padx=0)
        self.other_setting_frame_c.add(child=self.other_setting_frame, title='其他设置' ,bootstyle=PRIMARY)
        self.other_setting_frame_c.expand_close(self.other_setting_frame)

        # 数据位固定为8
        self.databits_label = ttkb.Label(self.other_setting_frame, text="数据位: 8")
        self.databits_label.pack(anchor='w', pady=2)

        # self.databits_label = ttkb.Label(self.other_setting_frame, text="数据位")
        # self.databits_label.pack(anchor='w', pady=2)
        # self.databits_combobox = ttkb.Combobox(self.other_setting_frame, values=["5", "6", "7", "8"], width=default_setting_width, state='readonly')
        # self.databits_combobox.set(self.config["DEFAULT"].get("databits", "8"))
        # self.databits_combobox.pack(anchor='w', pady=2)


        self.stopbits_label = ttkb.Label(self.other_setting_frame, text="停止位")
        self.stopbits_label.pack(anchor='w', pady=2)
        self.stopbits_combobox = ttkb.Combobox(self.other_setting_frame, values=["1", "1.5", "2"], width=default_setting_width, state='readonly')
        self.stopbits_combobox.set(self.config["DEFAULT"].get("stopbits", "1"))
        self.stopbits_combobox.pack(anchor='w', pady=2)

        self.parity_label = ttkb.Label(self.other_setting_frame, text="校验")
        self.parity_label.pack(anchor='w', pady=2)
        self.parity_combobox = ttkb.Combobox(self.other_setting_frame, values=["None", "Even", "Odd", "Mark", "Space"], width=default_setting_width,
                                            state='readonly')
        self.parity_combobox = ttkb.Combobox(self.other_setting_frame, values=["None", "Even", "Odd"], width=default_setting_width,
                                            state='readonly')
        self.parity_combobox.set(self.config["DEFAULT"].get("parity", "None"))
        self.parity_combobox.pack(anchor='w', pady=2)


        new_row_frame = ttkb.Frame(self.other_setting_frame)
        new_row_frame.pack(side='top', fill='x')
        self.RTS_var = tk.BooleanVar()
        self.cb_RTS = ttkb.Checkbutton(master=new_row_frame, text="RTS", variable=self.RTS_var, bootstyle="success"+'round-toggle',command=self.reopen_port)
        self.cb_RTS.pack (padx=5, pady=5, fill=tk.BOTH)
        #self.cb_RTS.invoke()
        self.DTR_var = tk.BooleanVar()
        self.cb_DTR = ttkb.Checkbutton(master=new_row_frame, text="DTR", variable=self.DTR_var, bootstyle="success"+'round-toggle',command=self.reopen_port)
        self.cb_DTR.pack(padx=5, pady=5, fill=tk.BOTH)
        #self.cb_DTR.invoke()
        self.cb_RTS.pack(anchor='w', pady=5)
        self.cb_DTR.pack(anchor='w', pady=5)
        ToolTip(
                self.cb_RTS,
                text="RTS/CTS (Ready To Send/Clear To Send):\n"+
                        "RTS 是从数据发送端发送到接收端的信号。"+
                        "\nCTS 是从接收端发送回发送端的信号。"+
                        "\n当接收端准备好接收数据时，它会发送 CTS 信号，告知发送端可以开始发送数据",
                bootstyle="primary-inverse",
            )
        ToolTip(
                self.cb_DTR,
                text="DTR/DSR (Data Terminal Ready/Data Set Ready):\n"+
                        "DTR 是从数据发送端发送到接收端的信号，表示发送端准备好发送数据。"+
                        "\nDSR 是从接收端发送回发送端的信号，表示接收端存在并且准备好接收数据",
                bootstyle="primary-inverse",
            )

        port_bt_row_frame = ttkb.Frame(self.config_frame)
        port_bt_row_frame.pack(side='top', fill='x')
        self.open_button = ttkb.Button(port_bt_row_frame, text="打开串口", width=default_setting_width,command=self.open_serial_port, bootstyle='outline')
        self.open_button.pack(anchor='w', pady=(5,0))
        self.close_button = ttkb.Button(port_bt_row_frame, text="关闭串口", width=default_setting_width,command=self.close_serial_port, bootstyle='outline')
        self.close_button.pack(anchor='w', pady=(5,0))
        # self.logfile_analy_button = ttk.Button(self.config_frame, text="日志导入", command=self.import_logfile_to_analysis,width=default_setting_width)
        # self.logfile_analy_button.pack(anchor='w', pady=(5,0))

        
        style_list = ttkb.Style()
        # self.base_theme_cb = ttk.Combobox(self.config_frame, values=style_list.theme_names(), width=default_setting_width)
        # self.base_theme_cb.insert(END, "选择主题")
        # #, state='readonly'
        # self.base_theme_cb.config(state='readonly')
        # self.base_theme_cb.pack(anchor='w', pady=(5,0))
        # self.base_theme_cb.bind("<<ComboboxSelected>>", self.change_style)

        self.timestamp_var = tk.BooleanVar()
        self.timestamp_var.set(self.config["DEFAULT"].getboolean("show_timestamp", False))
        self.timestamp_checkbox = ttkb.Checkbutton(self.config_frame, text="显示时间戳", variable=self.timestamp_var,
                                                command=self.update_config)
        self.timestamp_checkbox.pack(side='top',anchor='w', pady=(5,0))

                # 读取 build_info.txt 文件
        self.build_time = ""
        self.version = ""
        try:
            with open(str(img_parent_path)+'/build_info.txt', "r") as f:
                lines = f.readlines()
                for line in lines:
                    if "Build Time" in line:
                        self.build_time = line.split(": ")[1].strip()
                    elif "Version" in line:
                        self.version = line.split(": ")[1].strip()
        except FileNotFoundError:
            self.build_time = "未知"
            self.version = "未知"
        self.version_label = ttkb.Label(self.config_frame, text=f"{self.version}\n{self.build_time}",bootstyle="secondary")
        self.version_label.pack(side='top',anchor='w', pady=(5,0))


        # Receive and send area
        self.io_frame = ttkb.Frame(self.root)
        self.io_frame.grid(row=0, column=2, padx=0, pady=10, sticky='nsew')

        # self.root.grid_columnconfigure(2, weight=9)
        self.root.grid_rowconfigure(0, weight=1)
        # self.root.grid_rowconfigure(1, weight=1)

        self.io_frame.grid_columnconfigure(0, weight=1)
        self.io_frame.grid_rowconfigure(0, weight=1)
        # io_frame.grid_rowconfigure(1, weight=1)

        # Receive area
        receive_frame = ttkb.Frame(self.io_frame)
        receive_frame.grid(row=0, column=0, padx=10, pady=0, sticky='nsew')

        receive_frame.grid_columnconfigure(0, weight=1)
        receive_frame.grid_columnconfigure(1, weight=1)
        receive_frame.grid_rowconfigure(1, weight=1)
        
        receive_label_row_frame = ttkb.Frame(receive_frame)
        receive_label_row_frame.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')
        # self.receive_label = ttkb.Label(receive_label_row_frame, text="接收区域")
        # self.receive_label.pack(padx=10, pady=5,side='left')

        
        self.log_analysis_button = ttkb.Button(receive_label_row_frame, text="实时日志分析", command=self.realtime_show, bootstyle='outline',width=12)#bootstyle=INFO,
        self.log_analysis_button.pack(padx=10, pady=5,side='left')

        self.log_analysis_button = ttkb.Button(receive_label_row_frame, text="静态日志分析", command=self.save_data_and_analysis, bootstyle='outline',width=12)#bootstyle=INFO,
        self.log_analysis_button.pack(padx=10, pady=5,side='left')

        self.log_analysis_button = ttkb.Button(receive_label_row_frame, text="历史日志分析", command=self.import_logfile_to_analysis, bootstyle='outline',width=12)#bootstyle=INFO,
        self.log_analysis_button.pack(padx=10, pady=5,side='left')

        self.save_button = ttkb.Button(receive_label_row_frame, text="清空接收区", command=self.clear_receive_data, bootstyle='outline')#bootstyle=INFO,
        self.save_button.pack(padx=10, pady=5,side='left')

        self.save_button = ttkb.Button(receive_label_row_frame, text="保存接收内容", command=self.save_received_data, bootstyle='outline')#bootstyle=INFO, 
        self.save_button.pack(padx=10, pady=5,side='left')

        self.hex_display_checkbox = ttkb.Checkbutton(receive_label_row_frame, text="HEX显示", variable=self.hex_display_var)
        self.hex_display_checkbox.pack(padx=10, pady=5,side='left')

        # self.auto_save_checkbox = ttkb.Checkbutton(receive_label_row_frame, text="自动保存", variable=self.auto_save_var)
        # self.auto_save_checkbox.pack(padx=10, pady=5,side='left')


        custom_font = ("微软雅黑", 10)
        self.receive_text = ScrolledText(receive_frame, wrap=tk.WORD, font=custom_font,
                                    highlightthickness=1,
                                    autohide=True, bootstyle="primary")
                                    
        self.receive_text.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky='nsew')


        # Send area
        self.send_frame = ttkb.Frame(self.io_frame)
        self.send_frame.grid(row=1, column=0, padx=10, pady=5, sticky='nsew')

        self.send_frame.grid_columnconfigure(0, weight=1)
        # send_frame.grid_rowconfigure(0, weight=1)

        send_lable_frame = ttkb.Frame(self.send_frame)
        send_lable_frame.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')

        self.send_periodic_checkbox = ttkb.Checkbutton(send_lable_frame, text="定时发送", variable=self.periodic_send_var,
                                                    command=self.toggle_periodic_send)
        self.send_periodic_checkbox.pack(padx=10, pady=5,side='left')

        self.send_interval_entry = ttkb.Entry(send_lable_frame, textvariable=self.send_interval, width=5)
        self.send_interval_entry.pack(pady=5, padx=5,side='left')
        self.ms_label = ttkb.Label(send_lable_frame, text="ms")
        self.ms_label.pack(pady=5, padx=0,side='left')

        self.append_newline_checkbox = ttkb.Checkbutton(send_lable_frame, text="加回车换行", variable=self.append_newline_var, command=self.update_config)
        self.append_newline_checkbox.pack(pady=5, padx=10,side='left')

        self.hex_send_checkbox = ttkb.Checkbutton(send_lable_frame, text="HEX发送", variable=self.hex_send_var,
                                                command=self.toggle_hex_send)
        self.hex_send_checkbox.pack( pady=5, padx=5,side='left')


        self.send_text = tk.Text(self.send_frame, height=4, font=custom_font)
        self.send_text.grid(row=1, column=0, padx=10, pady=(0,5), sticky='ew')

        self.send_button = ttkb.Button(self.send_frame, text="发送", command=self.send_data, bootstyle=PRIMARY)
        self.send_button.grid(row=2, column=0, padx=10, pady=(10,0), sticky='ew')

        # self.scrollbar = ttkb.Scale(config_frame, from_=0, to=1, orient='horizontal', command=self.change_color, length=140)
        # self.scrollbar.set(255)  # Initialize scrollbar position
        # self.scrollbar.pack(anchor='w', pady=2)

        # Create drawer page buttons
        # tab_frame = ttkb.Frame(self.root)
        # tab_frame.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')

        # ResizableDrawerApp(self, self.top_root, self.root, tab_frame,  str(img_parent_path) +'/icon/history.png', 1)
        # ResizableDrawerApp(self, self.top_root, self.root, tab_frame,  str(img_parent_path) +'/icon/inroduce.png', 2)
        #ResizableDrawerApp(self, self.top_root, self.root, tab_frame, './icon/UWB.png', 3)
        #ResizableDrawerApp(self, self.top_root, self.root, tab_frame, 'logo.png', 4)
        self.init_theme(self.theme_backup)
        # if self.theme_backup == "vapor" or self.theme_backup == "cyborg":
        #     self.loading_gif.change_image('./icon/bike.gif')
        #     self.loading_gif.resize_image(100, 100)

        def config_cb_change(e):
            self.reopen_port()
        def config_cb_click(e):#用于打开软件后，动态拔插串口的时候，可以在选项卡中看到最新检测到的端口列表
            #self.port_combobox.set(self.get_serial_ports())
            self.port_combobox['values'] = self.get_serial_ports()
            #print(f"config_cb_click={self.get_serial_ports()}")
            # self.reopen_port()
        #self.port_combobox.bind("<<ComboboxSelected>>", config_cb_click)
        # 绑定鼠标左键点击事件
        self.port_combobox.bind("<Button-1>", config_cb_click)
        # 绑定选中值事件
        # self.port_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        # self.baudrate_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        # self.databits_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        self.stopbits_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        self.parity_combobox.bind("<<ComboboxSelected>>", config_cb_change)

        #创建可扩展页面
        self.uart2_frame = ttkb.Frame(self.root)
        self.uart2_frame.grid(row=0, column=3, sticky="nsew",padx=0)
        self.uart2app = UARTTool_copy(self.uart2_frame,self.root)

        # self.root.grid_columnconfigure(0, weight=1)
        # self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=9)
        self.root.grid_columnconfigure(3, weight=10)
        # self.root.grid_columnconfigure(4, weight=1)
        # self.root.grid_rowconfigure(0, weight=1)
        self.clear_receive_data()#初始化过程中会有一些数据，清空一下
        # Auto-refresh receive data
        self.root.after(100, self.receive_data)


    def import_logfile_to_analysis(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            result = True
            result = log_analysis_tochart(file_path)
            if not result:
                messagebox.showerror("错误", f"日志内容分析失败或数据太少")

    def clear_receive_data_cmd(self):
        self.received_data_store.clear()
        # self.received_data_store_test.clear()
        for field in field_keys:
            if field in Key_value_pair_mult:
                Key_value_pair_mult[field].clear()  # 清空原始数据
        print("Key_value_pair_mult",Key_value_pair_mult)
        self.update_chart()


        # 新增：清除字段信息，允许再次解析
        field_keys.clear()
        self.field_keys_ready = False
        self.first_data_parsed = False

    def Pause_realtime_show(self):
        # 切换暂停状态
        self.paused = not self.paused
        print(f"Pause_realtime_show={self.paused}")

    def realtime_show(self):
        if self.realtime_show_flag:
            return
        if not self.field_keys_ready:
            messagebox.showwarning("警告", "尚未接收到有效数据，请先确保串口有数据输入")
            return
        self.realtime_show_flag = True

        # if not self.received_data_store:
        #     messagebox.showerror("错误", "请确保串口已正确接收RANGINGAOA数据！")
        #     return

        self.chart_window = tk.Toplevel()
        self.chart_window.title("实时数据显示")

        self.fig, self.ax = plt.subplots()
        self.fig.subplots_adjust(left=0.04, right=0.97, top=0.97, bottom=0.03)
        self.ax.grid(True)

        fields = field_keys
        print("fields",fields)
        print("fields_keys",field_keys)

        default_checked_fields = ['D', 'RESP_Azi','RESP_Ele','INIT_Azi', 'INIT_Ele']  # 默认勾选的字段
        field_vars = {field: tk.BooleanVar(value=(field in default_checked_fields)) for field in fields}

        check_bt_frame = ttkb.Frame(self.chart_window)
        check_bt_frame.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=100)
        chart_frame = ttkb.Frame(self.chart_window, borderwidth=2, relief='groove')
        chart_frame.pack(fill=tk.BOTH, expand=1)

        for field in field_vars:
            chk = ttk.Checkbutton(check_bt_frame, text=field, variable=field_vars[field])
            chk.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)
        self.clear_received_data_btn = ttkb.Button(check_bt_frame, text="清空数据", command=self.clear_receive_data_cmd, bootstyle='outline')
        self.clear_received_data_btn.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)

        self.pause_btn = ttkb.Button(check_bt_frame, text="   暂停   ", command=self.Pause_realtime_show, bootstyle='outline')
        self.pause_btn.pack(side=tk.TOP, anchor=tk.W, padx=10, pady=5)

        self.chart_canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.chart_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=10, pady=10)
        self.toolbar = NavigationToolbar2Tk(self.chart_canvas, chart_frame)
        self.toolbar.update()

        def update_chart():
            if not self.realtime_show_flag:
                return
            self.ax.clear()
            self.ax.grid(True)

            active_fields = [field for field, var in field_vars.items() if var.get()]

            data = {field: [] for field in active_fields}
            # 从全局变量中提取对应字段的数据
            for field in active_fields:
                if field in Key_value_pair_mult:
                    data[field] = Key_value_pair_mult[field].copy()  # 或者直接赋值，看是否需要深拷贝

            for entry in self.received_data_store:
                for field in active_fields:
                    if field in entry:
                        data[field].append(entry[field])

            for field in active_fields:
                if data[field]:
                    self.ax.plot(range(len(data[field])), data[field], label=field)

            self.ax.legend(loc='upper right', bbox_to_anchor=(1.0, 1.0))       #固定在右上角
            if self.paused:
                self.chart_canvas.draw()

            if self.realtime_show_flag:
                self.update_chart_id = self.chart_window.after(100, update_chart)

        update_chart()
        self.chart_window.geometry("1500x1200")
        self.chart_window.protocol("WM_DELETE_WINDOW", self.on_close_chart_window)

    def on_close_chart_window(self):
        # print("on_close_chart_window")
        self.realtime_show_flag = False
        self.paused = 1
        if hasattr(self, 'update_chart_id'):
            self.chart_window.after_cancel(self.update_chart_id)
        self.received_data_store.clear()
        if self.fig:
            plt.close(self.fig)  # 关闭图形对象
            self.fig = None
        self.chart_window.destroy()
        print("on_close_chart_window end")


    def save_data_and_analysis(self):
        default_filename = f"cb_log_to_chart.txt"

        file_path = os.path.join(self.config["DEFAULT"]["save_path"], default_filename)

        print(f"file_path={file_path}")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.receive_text.get("1.0", tk.END))
                selected_directory = os.path.dirname(file_path)

            except Exception as e:
                messagebox.showerror("错误", f"保存接收内容时出错: {str(e)}")

        result = True
        result = log_analysis_tochart(file_path)
        if not result:
            messagebox.showerror("错误", f"日志内容分析失败或数据太少")


    def update_config(self):
        self.config["DEFAULT"]["show_timestamp"] = str(self.timestamp_var.get())
        self.config["DEFAULT"]["theme_back"] = self.theme_backup
        self.config["DEFAULT"]["append_newline"] = str(self.append_newline_var.get())

        if self.client_gui:
            global ip_settings
            self.config["DEFAULT"]["ip_settings"] = ip_settings
        with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
            self.config.write(configfile)



    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def get_default_port(self):
        ports = self.get_serial_ports()
        if self.last_opened_port in ports:
            return self.last_opened_port
        else:
            return ports[0] if ports else ""

    def open_serial_port(self):
        if self.serial_port and self.serial_port.is_open:
            #如果选择了不一样的串口打开，则关闭已打开的串口，并打开新的串口
            port = self.port_combobox.get().replace("（已打开）", "").strip()
            if port == self.serial_port.name and self.update_port_flag == False:
                messagebox.showerror("错误", f"{self.serial_port.name}已经打开")
                return
            else:
                self.close_serial_port() 
        if demo_board_app:
            demo_board_app.close_all()
        port = self.port_combobox.get().replace("（已打开）", "").strip()
        baudrate = self.baudrate_combobox.get()
        # databits = int(self.databits_combobox.get())
        databits = 8
        stopbits = float(self.stopbits_combobox.get())
        parity = self.parity_combobox.get()
        rcts = self.RTS_var.get()
        dsr_dtr = self.DTR_var.get()
        parity_str = parity

        if parity == "None":
            parity = serial.PARITY_NONE
        elif parity == "Even":
            parity = serial.PARITY_EVEN
        elif parity == "Odd":
            parity = serial.PARITY_ODD
        # elif parity == "Mark":
        #     parity = serial.PARITY_MARK
        # elif parity == "Space":
        #     parity = serial.PARITY_SPACE

        try:
            self.serial_port = serial.Serial(port, baudrate, bytesize=databits, stopbits=stopbits, parity=parity, rtscts= rcts, dsrdtr= dsr_dtr)
            self.config["DEFAULT"]["last_opened_port"] = port
            with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
                self.config.write(configfile)
            self.last_opened_port = port
            self.port_combobox.set(f"{port}（已打开）")
            self.update_port_flag = False #打开端口了，标志一下下次进来不用再次打开
            str_rcts = "RTS" if rcts else " "
            str_dtr = "DTR" if dsr_dtr else " "
            global main_root
            
            self.current_title = f"ChipsBank UWB 串口调试助手     {port}  波特率：{baudrate} {str_rcts} {str_dtr}"
            main_root.title(self.current_title)

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_data = f"{timestamp} "

            self.receive_text.insert(tk.END, formatted_data)
            self.red_tag = "green"
            self.receive_text.tag_configure(self.red_tag, foreground="green")
            self.receive_text.insert(tk.END, f"{self.serial_port.name}已打开 ", (self.red_tag,))
            self.receive_text.insert(tk.END, f"波特率：{baudrate} {databits} {int(stopbits)} {parity_str} {str_rcts} {str_dtr}\n")
            self.receive_text.see(tk.END)

            # 新增：打开串口时重置字段解析标志
            self.first_data_parsed = False
            self.field_keys_ready = False

        except Exception as e:
            self.port_combobox.set(f"{port}")
            messagebox.showerror("错误", f"无法打开串口: {str(e)}")
    
    #配置发生改变,重新打开串口
    def reopen_port(self):
        self.update_port_flag = True
        self.open_serial_port()

        
    def close_serial_port(self):
        global main_root
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            
            self.current_title = "ChipsBank UWB 串口调试助手"
            main_root.title(self.current_title)
            self.port_combobox.set(self.port_combobox.get().replace("（已打开）", ""))

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_data = f"{timestamp} "

            self.receive_text.insert(tk.END, formatted_data)
            self.red_tag = "red"
            self.receive_text.tag_configure(self.red_tag, foreground="red")
            self.receive_text.insert(tk.END, f"{self.serial_port.name}已关闭\n", (self.red_tag,))
            self.receive_text.see(tk.END)


            # 清除字段状态，允许下次重新解析
            global field_keys, Key_value_pair_mult
            field_keys.clear()
            Key_value_pair_mult.clear()
            self.field_keys_ready = False
            self.first_data_parsed = False

            #messagebox.showinfo("信息", "串口已关闭")
        else:
            messagebox.showwarning("警告", "串口未打开")

    def receive_data(self):
        global field_keys, first_data_parsed 
        if self.serial_port and self.serial_port.is_open:
            try:
                while self.serial_port.in_waiting > 0:
                    # 使用 readline() 按行读取
                    line = self.serial_port.readline()
                    encoding = self.config["DEFAULT"].get("encoding", "utf-8")
                    if self.hex_display_var.get():
                        decoded_line = line.hex(' ').upper()
                    else:
                        decoded_line = line.decode(encoding, errors='replace').strip('\r\n')  # 去除换行符

                    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3] if self.timestamp_var.get() else ""
                    # formatted_line = f"{timestamp} 接收<< {decoded_line}\n"
                    formatted_line = f"{timestamp} {decoded_line}\n"
                    self.receive_text.insert(tk.END, formatted_line)
                    self.receive_text.see(tk.END)

                    Key_value_pair = parse_line(decoded_line)
                    if Key_value_pair:
                        if not first_data_parsed:
                            # global field_keys, first_data_parsed
                            field_keys = list(Key_value_pair.keys())
                            print("First keys (field_keys):", field_keys)
                            self.field_keys_ready = True
                            self.first_data_parsed = True

                        for key, value in Key_value_pair.items():
                            if key not in Key_value_pair_mult:
                                Key_value_pair_mult[key] = []
                            Key_value_pair_mult[key].append(value)

            except Exception as e:
            #     self.close_serial_port()
            #     messagebox.showerror("错误", f"接收数据异常: {str(e)}")
                pass
        self.root.after(100, self.receive_data)

    def check_receive_text_lines(self):
        total_lines = int(self.receive_text.index('end-1c').split('.')[0])
        if total_lines > AUTO_TOWS_THRESHOLD:#超过100000行就清空并自动保存到文件中
            # 获取所有文本内容
            content = self.receive_text.get("1.0", tk.END)
            # 保存到文件
            with open(AUTO_RESTOR_FILE, "a", encoding="utf-8") as file:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                file.write(f"自动保存，时间：{timestamp} \n")
                file.write(content)
            # 清空文本框内容
            self.receive_text.delete("1.0", tk.END)

    def send_data(self):
        if self.serial_port and self.serial_port.is_open:
            data = self.send_text.get("1.0", tk.END).strip()
            if self.hex_send_var.get():
                try:
                    data = bytes.fromhex(data.replace(" ", ""))
                except ValueError:
                    messagebox.showerror("错误", "请输入有效的HEX格式数据，每个HEX码之间用空格隔开")
                    return
                self.data_str = data.hex()
                display_data_str = " ".join(self.data_str[i:i + 2] for i in range(0, len(self.data_str), 2))
                self.send_data_prefix = "[HEX]"
            else:
                if self.append_newline_var.get():
                    data += '\r\n'
                data = data.encode()
                self.data_str = data.decode()
                display_data_str = self.data_str
                self.send_data_prefix = "[TEXT]"

            if data:
                # self.serial_port.write(data)
                self.th_send_data(data)
                
                self.display_sent_data(display_data_str)
                if self.periodic_send_var.get():
                    self.start_send_timer()
            else:
                messagebox.showwarning("警告", "发送区域没有内容")
        else:
            if self.periodic_send_var.get():
                self.periodic_send_var.set(False)
            messagebox.showwarning("警告", "串口未打开")

    def write_to_serial(self, data):
        try:
            self.serial_port.write(data)
            self.save_send_history(self.data_str, self.send_data_prefix)
            #print(f"成功Data sent: {data}")
            # 如果需要，这里可以添加操作成功的回调
        except Exception as e:
            # 从子线程中更新GUI，需要确保这是线程安全的
            self.handle_serial_error(str(e))

    def handle_serial_error(self, error_message):
        # 使用线程安全的方式更新GUI
        messagebox.showerror("错误", f"发送数据时发生错误: {error_message}")


    # 创建并启动一个新的线程来执行串口写入操作,主要是打开一些乱七八糟的串口，会导致串口操作卡死
    def th_send_data(self, data):
        thread = threading.Thread(target=self.write_to_serial, args=(data,))
        thread.daemon = True  # 将线程设置为守护线程
        thread.start()

    def display_sent_data(self, data):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3] if self.timestamp_var.get() else ""
        sent_label = "发送>> "
        formatted_data = f"{timestamp} {sent_label} {data}\n" if not data.endswith('\n') else f"{timestamp} {sent_label} {data}"

        self.receive_text.insert(tk.END, formatted_data)
        self.receive_text.see(tk.END)


    def save_send_history(self, data_str, prefix):
        entry = f"{prefix} {data_str}".strip() + "\n"  # Ensure entry ends with a single newline

        try:
            with open('send_history.txt', 'r', encoding='utf-8') as file:
                history = file.readlines()
        except FileNotFoundError:
            history = []

        hex_entries = [line for line in history if line.startswith("[HEX]")]
        text_entries = [line for line in history if line.startswith("[TEXT]")]

        # Remove trailing newline characters from history entries for comparison
        history = [line.strip() for line in history]

        if entry.strip() not in history:
            if prefix == "[HEX]":
                hex_entries.append(entry)
                if len(hex_entries) > 20:
                    hex_entries.pop(0)  # Remove oldest entry
            else:
                text_entries.append(entry)
                if len(text_entries) > 20:
                    text_entries.pop(0)  # Remove oldest entry

            with open('send_history.txt', 'w', encoding='utf-8') as file:
                file.writelines(hex_entries + text_entries)
            print(f"Data saved: {entry.strip()}")
        # else:
        #     print(f"Duplicate data not saved: {entry.strip()}")

    def clear_receive_data(self):
        # self.receive_text.configure(state='normal')
        self.receive_text.delete("1.0", tk.END)
        # self.receive_text.configure(state='disabled')

    def save_received_data(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        port = self.port_combobox.get().replace("（已打开）", "").strip()
        default_filename = f"{port}-{current_time}.txt"

        file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                initialfile=default_filename,
                                                initialdir=self.default_directory,  # 设置默认目录
                                                filetypes=[("Text files", "*.txt"), ("All files", "*.*")])

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write(self.receive_text.get("1.0", tk.END))
                selected_directory = os.path.dirname(file_path)
                #print(f"file={file_path}")
                messagebox.showinfo("信息", "接收内容已保存")
                #将用户选择的目录存在配置文件中
                self.config["DEFAULT"]["save_path"] = selected_directory
                with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
                    self.config.write(configfile)
            except Exception as e:
                messagebox.showerror("错误", f"保存接收内容时出错: {str(e)}")

    def start_send_timer(self):
        interval = self.send_interval.get()
        if interval <= 0:
            messagebox.showerror("错误", "发送间隔必须大于0毫秒")
            return
        if self.send_timer:
            self.root.after_cancel(self.send_timer)
        self.send_timer = self.root.after(int(interval), self.send_data)

    def toggle_periodic_send(self):
        if self.periodic_send_var.get():
            self.start_send_timer()
        else:
            if self.send_timer:
                self.root.after_cancel(self.send_timer)
                self.send_timer = None

    def toggle_hex_send(self):
        # Get current content in Text widget
        current_text = self.send_text.get("1.0", tk.END).strip()

        # Check if the checkbox is selected
        if self.hex_send_var.get():
            # Convert text content to hexadecimal representation
            hex_text = ' '.join(format(ord(char), '02x') for char in current_text)
            # Clear Text widget and insert hexadecimal text
            self.send_text.delete("1.0", tk.END)
            self.send_text.insert(tk.END, hex_text)
        else:
            # Attempt to convert hexadecimal string back to original text
            try:
                hex_list = current_text.split()  # Split text into list of hexadecimal numbers
                byte_array = bytes(int(hex_char, 16) for hex_char in hex_list)  # Convert hex numbers to bytes
                original_text = byte_array.decode('utf-8', errors='ignore')  # Decode to string
                self.send_text.delete("1.0", tk.END)
                self.send_text.insert(tk.END, original_text)
                print("Original text restored:", original_text)
            except ValueError as e:
                print("Error converting hex to text:", e)
                self.send_text.delete("1.0", tk.END)  # Clear text widget to prevent error display
                self.send_text.insert(tk.END, "Invalid hex input")  # Display error message


    def change_style(self, *_):
        style = ttkb.Style()
        # theme = choice(style.theme_names())
        selected_theme = self.base_theme_cb.get()
        if selected_theme == "选择主题":
            theme = "cosmo"
        else:
            theme = selected_theme
        self.theme_backup = theme
        self.update_config()
        style.theme_use(theme)
        if style.theme.type == "dark":
            apply_theme_to_titlebar(self.top_root, dark_type="dark")
        else:
            apply_theme_to_titlebar(self.top_root, dark_type="light")
        
    def init_theme(self,theme):
        style = ttkb.Style()
        self.theme_backup = theme
        style.theme_use(theme)
        if style.theme.type == "dark":
            apply_theme_to_titlebar(self.top_root, dark_type="dark")
            # img = Image.open('./icon/logo_black.png')
            # icon = ImageTk.PhotoImage(img)
            # self.top_root.iconphoto(False, icon)
        # else:
        #     apply_theme_to_titlebar(self.top_root, dark_type="light")


def center_window(root, width, height):
    global main_root,init_config,g_is_maxed
    main_root = root
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    init_config = configparser.ConfigParser()
    if not os.path.exists(WIN_CONFIG_FILE):
        #2K屏幕和4K屏幕分开处理
        # print(f"screen_width={screen_width},screen_height={screen_height}")
        if screen_width > 2048:
            width = screen_width//3
            height = screen_height//3+200
        else:
            width = screen_width//2
            height = screen_height//2+100
    else:
        init_config.read(WIN_CONFIG_FILE, encoding='utf-8')
        # width = int(init_config["DEFAULT"].get("last_window_width", "1080"))
        # height = int(init_config["DEFAULT"].get("last_window_height", "800"))
        try:
            width = int(init_config["DEFAULT"].get("last_window_width", "1080"))
        except ValueError:
            if screen_width > 2048:
                width = screen_width//3
                height = screen_height//3+200
            else:
                width = screen_width//2
                height = screen_height//2+100
        try:
            height = int(init_config["DEFAULT"].get("last_window_height", "800"))
        except ValueError:
            if screen_width > 2048:
                width = screen_width//3
                height = screen_height//3+200
            else:
                width = screen_width//2
                height = screen_height//2+100

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    # print(f"screen_width={width},height={height}")
    g_is_maxed = 0
    if screen_width <= width or screen_height <= height:
        root.state('zoomed')  # Maximized window
        g_is_maxed = 1
    else:
        root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(screen_width//3, screen_height//3)  # Set window minimum size

    if g_is_maxed == 0:#不记录最大化窗口数据
        init_config.read(WIN_CONFIG_FILE, encoding='utf-8')
        init_config["DEFAULT"]["last_window_width"] = str(width)
        init_config["DEFAULT"]["last_window_height"] = str(height)
        with open(WIN_CONFIG_FILE, "w", encoding='utf-8') as configfile:
            init_config.write(configfile)
    
    root.title("ChipsBank UWB 串口调试助手")
    img = Image.open(img_parent_path / './icon/logo_black.png')
    icon = ImageTk.PhotoImage(img)
    root.iconphoto(False, icon)


def on_tab_changed(event):
    # 获取当前选中的标签页索引
    selected_tab_index = event.widget.index("current")
    # 获取当前选中的标签页的文本（标题）
    selected_tab_text = event.widget.tab(selected_tab_index, "text")
    #print(f"当前选中的标签页索引是: {selected_tab_index}, 标题是: {selected_tab_text}")

    #demo_board_app.close_all()
    if selected_tab_index == 0:
        if not uart_app:
            return
        main_root.title(f"{uart_app.current_title}")
        if demo_board_app.check_port_started:
            demo_board_app.close_all()
        
    else:
        main_root.title(f"ChipsBank UWB      {selected_tab_text}")
        uart_app.close_all()
        
        if selected_tab_index == 1:
            demo_board_app.start_check_ports()

            

    # 保存当前选中的标签页索引,用于下次打开软件时默认选中
    uart_app.config["DEFAULT"]["default_tap"] = str(selected_tab_index)

    with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
        uart_app.config.write(configfile)


def create_notebook_frame(root):
    nb = ttk.Notebook(root,bootstyle='primary')
    nb.pack(padx=3, pady=3,fill=BOTH, expand=YES)  # 确保 notebook 能够扩展和填充

    # 为第一个标签页创建一个Frame作为容器
    tab1_frame = ttk.Frame(nb)
    tab1_frame.pack(fill=BOTH, expand=YES)  # 确保 frame 能够扩展和填充
    # 创建串口调试助手视图
    nb.add(tab1_frame, text="串口调试助手")

    # 为第二个标签页创建一个Frame作为容器
    tab2_frame = ttk.Frame(nb)
    tab2_frame.pack(fill=BOTH, expand=YES)  # 确保 frame 能够扩展和填充
    # 在tab2_frame中添加一个Label
    #ttk.Label(tab2_frame, text="A notebook tab.").pack(fill=BOTH, expand=YES)
    nb.add(tab2_frame, text="开发板功能验证")

    # 绑定事件
    nb.bind("<<NotebookTabChanged>>", on_tab_changed)

    return nb
# 关闭窗口时做点事
def topwin_on_closing():
    global init_config,g_is_maxed,g_fig_temp
    #print("Quit", "Do you want to quit?")
    if not main_root.can_close_window:
        #custom_show_toast("请结束当前操作再关闭窗口!")
        result = messagebox.askokcancel(message='当前程序有任务正在运行，确定关闭程序吗？')
        if result:
            result2 = messagebox.askokcancel(message='真的确定关闭程序吗？')
            if result2:
                pass
            else:
                return
        else:
            return
    if g_is_maxed == 0:
        init_config.read(WIN_CONFIG_FILE, encoding='utf-8')
        init_config["DEFAULT"]["last_window_width"] = str(main_root.winfo_width())
        init_config["DEFAULT"]["last_window_height"] = str(main_root.winfo_height())
        with open(WIN_CONFIG_FILE, "w", encoding='utf-8') as configfile:
            init_config.write(configfile)
    if g_fig_temp:
        plt.close(g_fig_temp)
    main_root.destroy()

def on_maximize(event):
    # 在这里调整窗口布局以适应最大化
    global g_is_maxed
    g_is_maxed = 1
    

def on_restore(event):
    # 在这里调整窗口布局以适应还原
    global g_is_maxed
    g_is_maxed = 0

# import customtkinter
# customtkinter.set_appearance_mode("dark")

def open_weblink():
    webbrowser.open("www.chipsbank.com")

# def open_user_manual():
#     # html_file_path = str(img_parent_path)+"/_UserManual_/index.html"
#     html_file_path = str(img_parent_path)+"/UserManual/SDK User Manual/index.html"
#     if os.path.exists(html_file_path):
#         webbrowser.open(html_file_path)
#     else:
#         print("文件不存在")
#         pass

def open_tools_manual():
    html_file_path = str(img_parent_path)+"/UserManual/Tools User Manual/Chipsbank_Tools_User_Manual_V1.0.pdf"
    if os.path.exists(html_file_path):
        webbrowser.open(html_file_path)
    else:
        print("文件不存在")
        pass
    


class create_alliance_logo:
    def __init__(self, root):
        
        self.self_frame = ttk.Frame(root)
        self.self_frame.pack(fill=BOTH,pady=0)#,side=BOTTOM

        # widget images
        images = [
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'CCC.png').resize((156, 32))),
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'Fira.png').resize((116, 32))),
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'chipsbank_logo.png').resize((140, 28)))

        ]

        # create grayscale images with alpha channel
        gray_images = [
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'CCC_gray.png').resize((156, 32))),
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'Fira_gray.png').resize((116, 32))),
            ImageTk.PhotoImage(Image.open(CCC_FILE_PATH/'chipsbank_logo_gray.png').resize((140, 28)))
        ]

        # create labels with grayscale images
        label1 = ttk.Label(self.self_frame, image=gray_images[0])
        label1.pack(padx=10, pady=0,side=RIGHT)
        label1.bind("<Enter>", lambda e: label1.config(image=images[0]))
        label1.bind("<Leave>", lambda e: label1.config(image=gray_images[0]))

        label2 = ttk.Label(self.self_frame, image=gray_images[1])
        label2.pack(padx=10, pady=0,side=RIGHT)
        label2.bind("<Enter>", lambda e: label2.config(image=images[1]))
        label2.bind("<Leave>", lambda e: label2.config(image=gray_images[1]))

        label3 = ttk.Label(self.self_frame, image=gray_images[2])
        label3.pack(padx=10, pady=0,side=RIGHT)
        label3.bind("<Enter>", lambda e: label3.config(image=images[2]))
        label3.bind("<Leave>", lambda e: label3.config(image=gray_images[2]))

        web_link_bt = ttkb.Button(master=self.self_frame, text="芯邦官网 www.chipsbank.com", command=open_weblink,bootstyle=(LINK,DARK),takefocus=False)
        web_link_bt.pack(padx=5, pady=0,side=RIGHT)
        web_link_bt.bind("<Enter>", lambda e: web_link_bt.config(cursor='hand2'))

        # user_manual_link_bt = ttkb.Button(master=self.self_frame, text="SDK用户手册", command=open_user_manual,bootstyle=(LINK,DARK),takefocus=False)
        # user_manual_link_bt.pack(padx=5, pady=0,side=RIGHT)
        # user_manual_link_bt.bind("<Enter>", lambda e: user_manual_link_bt.config(cursor='hand2'))

        tool_manual_link_bt = ttkb.Button(master=self.self_frame, text="Tool用户手册", command=open_tools_manual, bootstyle=(LINK, DARK), takefocus=False)
        tool_manual_link_bt.pack(padx=5, pady=0, side=RIGHT)
        tool_manual_link_bt.bind("<Enter>", lambda e: tool_manual_link_bt.config(cursor='hand2'))

    #     self.self_frame.bind("<Button-1>", self.on_frame_click)

    # def on_frame_click(self, event):
    #     # 阻止事件传播
    #     event.widget.focus_set()
    #     self.self_frame.config(borderwidth=1, relief='ridge',cursor='hand2')


def drop_log_to_analysis(event):
    file_path = event.data.strip('{}')  # 去掉大括号

    print(f"file_path={file_path}")
    result = True
    result = log_analysis_tochart(file_path)
    if not result:
        messagebox.showerror("错误", f"日志内容分析失败或数据太少")
    # open_file(file_path)

if __name__ == "__main__":
    
    # root = ttkb.Window()
    # root = TkinterDnD.ttk()
    root = TkinterDnD.Tk()
    # root = customtkinter.CTk()
    main_root = root
    main_root.can_close_window = True
    root.protocol("WM_DELETE_WINDOW", topwin_on_closing)
    

    # center_window(root,1400, 1050)  # Set window to center with specified size
    center_window(root,1800, 1050)  # Set window to center with specified size

    nnb = create_notebook_frame(root)
    create_alliance_logo(root)
    TAB0 = nnb.nametowidget(nnb.tabs()[0])

    uart_app = UARTTool(TAB0,root)
    UARTTool_Extension(root,TAB0,uart_app)

    TAB1 = nnb.nametowidget(nnb.tabs()[1])

    demo_board_app = Board_Functions(TAB1, root)

    # 绑定最大化和还原事件
    root.bind("<Configure>", lambda event: on_maximize(event) if root.state() == 'zoomed' else on_restore(event))
    # 默认选中上一次软件打开的标签页
    nnb.select(g_default_tap)
    #绑定窗口可以拖拽文件打开日志
    root.mainloop()
    demo_board_app.stop_check_ports()




