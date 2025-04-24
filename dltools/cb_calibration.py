"""
File: cb_calibration.py
Author: Roja.Zeng
Date: 2024
Company: ChipsBank
Version: 1.0.0
Description: 
产测模式的页面
"""

import tkinter as tk
from tkinter import scrolledtext, filedialog
from ttkbootstrap import Style
import ttkbootstrap as ttkb
import configparser
import os
from ttkbootstrap.scrolled import ScrolledText
import serial
import serial.tools.list_ports
import threading
from resizeable import AnimatedGif
import time
from toast import ToastNotification
from threading import Timer
from icons import Emoji
from ttkbootstrap.tooltip import ToolTip
import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.backend_bases import MouseEvent
from matplotlib.widgets import Cursor
from annotated_cursor import AnnotatedCursor

from CB_PanedWindow import CustomPanedWindow

import matplotlib.font_manager as fm

from cb_logger import CBLogger
from queue import Queue
import select

WIN_CONFIG_FILE = "win_config.ini"
g_cb_top_root = None


def create_packet(cmd_h, cmd_l, resp, data):
    start_code = 0x5A
    end_code = 0x5B
    data_length = len(data)
    packet = bytearray([start_code, cmd_h, cmd_l, resp, data_length])
    packet.extend(data)
    checksum = (sum(packet[1:]) & 0xFF)
    packet.append(checksum)
    #packet.append(end_code)
    return bytes(packet)



class SerialStateMachine(threading.Thread):
    def __init__(self, serial_port, baud_rate, response_queue):
        super().__init__()
        self.ser = serial.Serial(serial_port, baud_rate, timeout=1)
        self.response_queue = response_queue
        self.command_queue = Queue()
        self.running = True
        self.daemon = True  # 设置为守护线程
        self.read_thread = threading.Thread(target=self.read_from_port)
        self.read_thread.daemon = True
        self.read_thread.start()


    def run(self):
        while self.running:
            # 检查是否有命令需要发送
            if not self.command_queue.empty():
                cmd = self.command_queue.get()
                # if cmd:
                    # print(f"Command in hex: {cmd}")
                #data='0d 0a 5a 00 00 00 01 00 01 0d 0d'
                #cmd = bytes.fromhex(cmd.replace(" ", ""))


                #print(f"Packet: {packet.hex()}")
                #self.ser.write(cmd)
                self.ser.write_timeout = 1
                try:
                    self.ser.write(cmd)
                except serial.SerialTimeoutException as e:
                    print(f"Serial port {self.ser.port} timeout: {e}")
                    self.ser.close()
                    self.running = False
                    #self.stop()
                    print(f"Serial port {self.ser.port} timeout: {e}")
            time.sleep(0.1)  # 增加适当的休眠时间，避免 CPU 占用过高
        print(f"SerialStateMachine stopped")

    def read_from_port(self): 
        # 逐字节读取，直到找到包头
        while self.running:
            start_byte = None
            if self.ser.in_waiting > 0:
                start_byte = self.ser.read(1)
                #print(f"start_byte: {start_byte}")
            
            if start_byte == b'\x5A':
                # print(f"Found start byte: {start_byte}")
                # 读取固定长度的前4字节（命令码 + 响应位 + 数据长度）
                header = self.ser.read(4)
                # print(f"Header: {header}")
                if len(header) < 4:
                    continue  # 包不完整，重新查找下一个5A
                # 解析数据长度
                data_length = header[3]
                
                # 读取剩余字节（数据 + 校验和）
                remaining_length = data_length + 1  # 数据长度 + 校验和
                data = self.ser.read(remaining_length)
                if len(data) < remaining_length:
                    # 数据不完整，重新查找下一个5A
                    continue
                
                # 组合完整的响应
                response = start_byte + header + data
                
                # 校验和验证（假设最后一个字节是校验和）
                checksum = sum(response[1:-1]) & 0xFF  # 从 header 开始计算，不包括 start_byte (0x5A) 和最后一个字节（校验和）
                if checksum != response[-1]:  # 校验和不匹配
                    print(f"Checksum error: expected {checksum}, got {response[-1]}, response={response}")
                    continue  # 校验失败，重新找下一个5A
                
                # 包合法，放入队列
                # print(f"Valid response: {response}")
                # 如果包合法，打印有效的响应
                # print(f"接收到的串口命令: {response.hex()}")
                formatted_cmd = ' '.join(f'{byte:02x}' for byte in response)
                print(f"接收的命令为：{formatted_cmd}")
                self.response_queue.put(response)#不处理，丢给队列，会自己触发process_responses
                    
            if self.ser.in_waiting == 0:
                time.sleep(0.1)  # 增加适当的休眠时间，避免 CPU 占用过高

    def send_command(self, cmd):
        self.command_queue.put(cmd)
        # print(f"发送的命令为：{cmd.hex()}")
        formatted_cmd = ' '.join(f'{byte:02x}' for byte in cmd)
        print(f"发送的命令为：{formatted_cmd}")

    def stop(self):
        self.running = False
        self.read_thread.join()  # 等待读取线程结束
        self.ser.close()


# 鼠标进入色块时放大
def on_enter(event):
    event.widget.config(padding=(40, 20))

# 鼠标离开色块时恢复大小
def on_leave(event):
    event.widget.config(padding=(30, 20))

#工厂模式
class CB_Calibrate_Frame:
    buttons_name2hd = {}  # 用于存放按键
    frames = {}  # 用于存放按键对应的Frame
    def __init__(self, master, top_root):
        global g_cb_top_root
        self.top_root = top_root
        g_cb_top_root = top_root
        # 配置日志记录器
        self.logger = CBLogger.get_logger()

        # 初始化串口状态机
        self.response_queue = Queue()
        self.serial_state_machine = None
        self.daemon = True  # 设置为守护线程
        # 启动一个线程来处理串口返回结果
        self.response_thread = threading.Thread(target=self.process_responses)
        self.response_thread.daemon = True  # 设置 response_thread 为守护线程
        self.response_thread.start()

        # 创建一个容器Frame
        self.master = master
        self.Cal_container = tk.Frame(master)
        self.Cal_container.pack(fill=tk.BOTH, expand=True)
        # self.Cal_container.grid_rowconfigure(0, weight=1)
        self.Cal_container.grid_rowconfigure(1, weight=1)
        self.Cal_container.grid_columnconfigure(0, weight=1)
        self.ft_mode_on = 0x00
        self.create_cal_setting_frame()

    def create_cal_setting_frame(self):
        # 创建存放操作按键的Frame
        self.Cal_setting_frame = tk.Frame(self.Cal_container)
        self.Cal_setting_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

        self.operate_output_frame = tk.Frame(self.Cal_container)
        self.operate_output_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)

        self.operate_container = ttkb.Frame(self.operate_output_frame)
        self.operate_container.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        self.operate_lb = tk.Label(self.operate_container, text="当前未选择操作项", font=('微软雅黑', 10, 'bold'))
        self.operate_lb.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        self.operate_note_lb = tk.Label(self.operate_container, text=" ")
        self.operate_note_lb.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)

        self.Cal_output_frame = ttkb.Frame(self.operate_output_frame)
        self.Cal_output_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

        self.operate_output_frame.grid_rowconfigure(0, weight=1)
        self.operate_output_frame.grid_columnconfigure(1, weight=1)
        # self.operate_output_frame.grid_columnconfigure(0, weight=4)

        self.baudrate_label = ttkb.Label(self.Cal_setting_frame,text="选择波特率：")
        self.baudrate_label.grid(row = 0,column=0,padx=(10, 0),sticky="ew")
        self.baudrate_combobox = ttkb.Combobox(self.Cal_setting_frame, values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"], width=10)
        self.baudrate_combobox.set("921600")
        self.baudrate_combobox.grid(row=0, column=0, padx=(100, 0), sticky="ew")
        self.baudrate_combobox.bind("<<ComboboxSelected>>", self.on_baudrate_selected_cal)

        #(以下所有操作均需打开工厂模式方可生效)
        self.cb_ft_onoff = ttkb.Checkbutton(self.Cal_setting_frame, text='工厂模式开关', bootstyle='round-toggle' + 'success', command=self.toggle_state_machine)
        self.cb_ft_onoff.grid(row=0, column=1, sticky="ew", padx=60, pady=5)

        # 按钮和处理函数的映射表
        self.button_name_to_cmd = {
            "读取芯片ID": "0d 0a 5A 00 00 00 01 00 01 0d 0d",
            "读取频偏校准值": "5A 00 00 00 01 00 01",
            "写入频偏校准值": "5A 00 00 00 01 00 01",
            "读取默认功率等级": "5A 00 00 00 01 00 01",
            "写入默认功率等级": "5A 00 00 00 01 00 01",
            "读取TOF校准值": "5A 00 00 00 01 00 01",
            "写入TOF校准值": "5A 00 00 00 01 00 01",
            "读取AOA校准值数量": "5A 00 00 00 01 00 01",
            "读取AOA校准值": "5A 00 00 00 01 00 01",
            "写入AOA校准值": "5A 00 00 00 01 00 01",
            # "工作模式设置": "5A 00 00 00 01 00 01",
            "读取工作模式": "5A 00 00 00 01 00 01",
            "Tx发包数量": "5A 00 00 00 01 00 01",
            "Tx发包间隔": "5A 00 00 00 01 00 01",
            "Tx开关": "5A 00 00 00 01 00 01",
            "Rx通道配置": "5A 00 00 00 01 00 01",
            "Rx开关": "5A 00 00 00 01 00 01",
            "获取Rx收包数量": "5A 00 00 00 01 00 01",
            "测距模式SYNC ID配置": "5A 00 00 00 01 00 01",
            "读取测距模式SYNC ID": "5A 00 00 00 01 00 01",
            "测距模式频率配置": "5A 00 00 00 01 00 01",
            "读取测距模式频率": "5A 00 00 00 01 00 01",
            "测距模式Tx开关": "5A 00 00 00 01 00 01",
            "测距模式Rx通道配置": "5A 00 00 00 01 00 01",
            "测距模式Rx开关": "5A 00 00 00 01 00 01",
            "获取测距模式Rx数据结果": "5A 00 00 00 01 00 01",
            # "自动校准模式": "5A 00 00 00 01 00 01",
        }
        # 根据命令名称设置 cmd_h 和 cmd_l
        self.ftcmd_map = {
            "厂测开关": (0x00, 0x00),
            "读取芯片ID": (0x00, 0x01),
            "读取频偏校准值": (0x00, 0x10),
            "写入频偏校准值": (0x00, 0x11),
            "读取默认功率等级": (0x00, 0x12),
            "写入默认功率等级": (0x00, 0x13),
            "读取TOF校准值": (0x00, 0x14),
            "写入TOF校准值": (0x00, 0x15),
            "读取AOA校准值数量": (0x00, 0x16),
            "读取AOA校准值": (0x00, 0x17),
            "写入AOA校准值": (0x00, 0x18),
            # "工作模式设置": (0x00, 0x20),
            "读取工作模式": (0x00, 0x21),
            "Tx发包数量": (0x00, 0x30),
            "Tx发包间隔": (0x00, 0x31),
            "Tx开关": (0x00, 0x32),
            "Rx通道配置": (0x00, 0x40),
            "Rx开关": (0x00, 0x41),
            "获取Rx收包数量": (0x00, 0x42),
            "测距模式SYNC ID配置": (0x00, 0x50),
            "读取测距模式SYNC ID": (0x00, 0x51),
            "测距模式频率配置": (0x00, 0x52),
            "读取测距模式频率": (0x00, 0x53),
            "测距模式Tx开关": (0x00, 0x60),
            "测距模式Rx通道配置": (0x00, 0x70),
            "测距模式Rx开关": (0x00, 0x71),
            "获取测距模式Rx数据结果": (0x00, 0x72),
            # "自动校准模式": (0x00, 0x80),
            "测试校准结果": (0x00, 0x81),
        }
        # 设置命令处理函数
        self.command_handlers = {
            (0x00, 0x00): self.handle_factory_switch,
            (0x00, 0x01): self.handle_read_chip_id,
            (0x00, 0x10): self.handle_read_freq_offset,
            (0x00, 0x11): self.handle_write_freq_offset,
            (0x00, 0x12): self.handle_read_default_power_level,
            (0x00, 0x13): self.handle_write_default_power_level,
            (0x00, 0x14): self.handle_read_tof_calibration,
            (0x00, 0x15): self.handle_write_tof_calibration,
            (0x00, 0x16): self.handle_read_aoa_calibration_count,
            (0x00, 0x17): self.handle_read_aoa_calibration,
            (0x00, 0x18): self.handle_write_aoa_calibration,
            # (0x00, 0x20): self.handle_set_work_mode,
            (0x00, 0x21): self.handle_read_work_mode,
            (0x00, 0x30): self.handle_tx_packet_count,
            (0x00, 0x31): self.handle_tx_packet_interval,
            (0x00, 0x32): self.handle_tx_switch,
            (0x00, 0x40): self.handle_rx_channel_config,
            (0x00, 0x41): self.handle_rx_switch,
            (0x00, 0x42): self.handle_get_rx_packet_count,
            (0x00, 0x50): self.handle_ranging_mode_id_config,
            (0x00, 0x51): self.handle_read_ranging_mode_id,
            (0x00, 0x52): self.handle_ranging_mode_freq_config,
            (0x00, 0x53): self.handle_read_ranging_mode_freq,
            (0x00, 0x60): self.handle_ranging_mode_tx_switch,
            (0x00, 0x70): self.handle_ranging_mode_rx_channel_config,
            (0x00, 0x71): self.handle_ranging_mode_rx_switch,
            (0x00, 0x72): self.handle_get_ranging_mode_rx_data,
        }
        
        # 动态创建按钮，每行5个
        row = 1
        col = 0
        for idx, (btn_text, _) in enumerate(self.button_name_to_cmd.items()):
            button = ttkb.Button(self.Cal_setting_frame, text=btn_text, command=lambda bt=btn_text: self.on_button_click(bt), bootstyle='outline', takefocus=False)
            # if btn_text == "自动校准模式":
            #     # button.config(bootstyle='outline-danger')
            if btn_text in ["自动校准模式", "读取AOA校准值数量"]:
                continue  # 跳过创建这两个按钮
            button.grid(row=row, column=col, sticky="ew", padx=10, pady=5)
            button.config(padding=(10, 10))  # 设置按键的最小宽度为10
            # # 绑定鼠标进入和离开事件
            # button.bind("<Enter>", on_enter)
            # button.bind("<Leave>", on_leave)
            button.frame_name = f"当前操作_{btn_text}"  # 为每个按钮添加 frame_name 属性
            #print(f"Button: {btn_text}, frame_name: {button.frame_name}")

            self.buttons_name2hd[btn_text] = button
            # 创建对应的 Frame 并存储在字典中
            frame = tk.Frame(self.operate_container)
            self.frames[button.frame_name] = frame

            if button.frame_name == "当前操作_写入默认功率等级":
                self.create_write_power_level_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_写入频偏校准值":
                self.create_write_freq_offset_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_写入TOF校准值":
                self.create_write_tof_calibration_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_读取AOA校准值":
                self.create_read_aoa_calibration_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_写入AOA校准值":
                self.create_write_aoa_calibration_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_工作模式设置":
                self.create_work_mode_setting_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_Tx发包数量":
                self.create_tx_packet_count_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_Tx发包间隔":
                self.create_tx_packet_interval_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_Tx开关":
                self.create_tx_switch_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_Rx通道配置":
                self.create_rx_channel_config_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_Rx开关":
                self.create_rx_switch_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_测距模式SYNC ID配置":
                self.create_ranging_mode_id_config_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_测距模式频率配置":
                self.create_ranging_mode_freq_config_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_测距模式Tx开关":
                self.create_ranging_mode_tx_switch_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_测距模式Rx通道配置":
                self.create_ranging_mode_rx_channel_config_UI(self.frames[button.frame_name])
            if button.frame_name == "当前操作_测距模式Rx开关":
                self.create_ranging_mode_rx_switch_UI(self.frames[button.frame_name])
            # if button.frame_name == "当前操作_自动校准模式":
            #     self.create_auto_calibration_UI(self.frames[button.frame_name])

            col += 1
            if col >= 8:
                col = 0
                row += 1



        # 创建一个新的 Frame 来包含 cal_log_label 和 bt_clear_log
        self.label_button_frame = ttkb.Frame(self.Cal_output_frame)
        self.label_button_frame.pack(side="top", fill="x", padx=10, pady=5)

        # 在新的 Frame 中添加 cal_log_label 和 bt_clear_log
        self.cal_log_label = ttkb.Label(self.label_button_frame, text="操作结果：",font=('微软雅黑', 10, 'bold'))
        self.cal_log_label.pack(side="left")

        self.bt_clear_log = ttkb.Button(self.label_button_frame, text="清空日志", command=self.clear_log, bootstyle='outline-danger')
        self.bt_clear_log.pack(side="right")

        # 添加 cal_log_text 到 Cal_output_frame
        self.cal_log_text = ScrolledText(self.Cal_output_frame, autohide=True, undo=True)  # 设置高度，避免遮挡
        self.cal_log_text.pack(side="top", fill="both", expand=True, padx=10, pady=5)  # 使用 pack 使文本框填充整个 frame
        #self.cb_ft_onoff.invoke()
        #self.Cal_setting_frame.grid_propagate(False)

    def on_baudrate_selected_cal(self,event):
        selected_baudrate = self.baudrate_combobox.get()
        # print(f"Selected baudrate: {selected_baudrate}")

    def create_tx_packet_count_UI(self, p_frame):
        # 添加 tx_packet_count_label 和 tx_packet_count_entry
        self.tx_packet_count_label = ttkb.Label(p_frame, text="Tx发包数量：(int32)")
        self.tx_packet_count_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.tx_packet_count_entry = ttkb.Entry(p_frame, width=8)
        self.tx_packet_count_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 在新的 Frame 中添加 bt_tx_packet_count
        self.bt_tx_packet_count = ttkb.Button(p_frame, text="设置发包数量", command=self.real_set_tx_packet_count, bootstyle='outline-primary')
        self.bt_tx_packet_count.grid(row=1, column=1, padx=5, pady=5, sticky="e")

    def create_tx_packet_interval_UI(self, p_frame):
        # 添加 tx_packet_interval_label 和 tx_packet_interval_entry
        self.tx_packet_interval_label = ttkb.Label(p_frame, text="Tx发包间隔：(微秒)(7-65535)")
        self.tx_packet_interval_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.tx_packet_interval_entry = ttkb.Entry(p_frame, width=8)
        self.tx_packet_interval_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 在新的 Frame 中添加 bt_tx_packet_interval
        self.bt_tx_packet_interval = ttkb.Button(p_frame, text="设置发包间隔", command=self.real_set_tx_packet_interval, bootstyle='outline-primary')
        self.bt_tx_packet_interval.grid(row=1, column=1, padx=5, pady=5, sticky="e")

    def create_write_freq_offset_UI(self, p_frame):
        # 添加 freq_offset_label 和 freq_offset_entry
        self.freq_offset_label = ttkb.Label(p_frame, text="频偏校准值：")
        self.freq_offset_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.freq_offset_combobox = ttkb.Combobox(p_frame, values=list(range(0, 255)), state="readonly",width=8)
        self.freq_offset_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.freq_offset_combobox.current(0)  # 设置默认值为0

        # 在新的 Frame 中添加 bt_write_freq_offset
        self.bt_write_freq_offset = ttkb.Button(p_frame, text="写入频偏", command=self.real_wirte_freq_offset, bootstyle='outline-primary')
        self.bt_write_freq_offset.grid(row=1, column=1, padx=5, pady=5, sticky="e")

    def create_write_power_level_UI(self, p_frame):
        # 添加 power_level_label 和 power_level_entry
        self.power_level_label = ttkb.Label(p_frame, text="功率等级：")
        self.power_level_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.power_level_dbm_label = ttkb.Label(p_frame, text="=-36.0 dBm/MHz")
        self.power_level_dbm_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        self.power_level_combobox = ttkb.Combobox(p_frame, values=list(range(0, 63)), state="readonly",width=8)
        self.power_level_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.power_level_combobox.bind("<<ComboboxSelected>>", self.on_power_level_combobox_select)
        self.power_level_combobox.current(38)  # 设置默认值为38

        # 在新的 Frame 中添加 bt_write_power_level
        self.bt_write_power_level = ttkb.Button(p_frame, text="写入功率", command=self.real_wirte_powercode, bootstyle='outline-primary')
        self.bt_write_power_level.grid(row=1, column=1, padx=5, pady=5, sticky="e")

    def create_write_tof_calibration_UI(self, p_frame):
        # 添加 tof_calibration_label 和 tof_calibration_entry
        # self.tof_calibration_label = ttkb.Label(p_frame, text="TOF校准值(0-65535)：")
        self.tof_calibration_label = ttkb.Label(p_frame, text="TOF校准值(-32768-32767)：")
        self.tof_calibration_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.tof_calibration_entry = ttkb.Entry(p_frame, width=8)
        self.tof_calibration_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 在新的 Frame 中添加 bt_write_tof_calibration
        self.bt_write_tof_calibration = ttkb.Button(p_frame, text="写入TOF", command=self.real_wirte_tof_calibration, bootstyle='outline-primary')
        self.bt_write_tof_calibration.grid(row=1, column=1, padx=5, pady=5, sticky="e")
    
    def create_read_aoa_calibration_UI(self, p_frame):
        # # 添加 aoa_calibration_label 和 aoa_calibration_entry
        # self.aoa_calibration_label = ttkb.Label(p_frame, text="读取第（0-255）：")
        # self.aoa_calibration_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # self.aoa_calibration_entry = ttkb.Entry(p_frame, width=8, justify='center')
        # self.aoa_calibration_entry.grid(row=0, column=1, padx=0, pady=5, sticky="w")
        # self.aoa_calibration_entry.insert(0, "0")

        # self.aoa_calibration_label2 = ttkb.Label(p_frame, text="个校准值")
        # self.aoa_calibration_label2.grid(row=0, column=2, padx=0, pady=5, sticky="w")
        # 在新的 Frame 中添加 bt_write_aoa_calibration
        self.bt_write_aoa_calibration = ttkb.Button(p_frame, text="读取校准值", command=self.real_read_aoa_calibration, bootstyle='outline-primary')
        self.bt_write_aoa_calibration.grid(row=1, column=0, padx=5, pady=5, sticky="w")

    def create_write_aoa_calibration_UI(self, p_frame):
        # 添加 aoa_calibration_label 和 aoa_calibration_entry
        # self.aoa_calibration_label = ttkb.Label(p_frame, text="写入第（0-255）个校准值：")
        # self.aoa_calibration_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # self.aoa_calibration_wirte_entry = ttkb.Entry(p_frame, width=8, justify='center')
        # self.aoa_calibration_wirte_entry.grid(row=0, column=1, padx=0, pady=5, sticky="w")
        # self.aoa_calibration_wirte_entry.insert(0, "0")

        # 添加真实水平角度 AOAH:u16
        self.aoah_label = ttkb.Label(p_frame, text="真实水平角度 AOAH:")
        self.aoah_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.aoah_entry = ttkb.Entry(p_frame, width=8, justify='center')
        self.aoah_entry.grid(row=2, column=1, padx=0, pady=5, sticky="w")

        # 添加真实垂直角度 AOAV:u16
        self.aoav_label = ttkb.Label(p_frame, text="真实垂直角度 AOAV:")
        self.aoav_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.aoav_entry = ttkb.Entry(p_frame, width=8, justify='center')
        self.aoav_entry.grid(row=3, column=1, padx=0, pady=5, sticky="w")

        # 添加当前水平PDOA值1 PDOA1:u16
        self.pdoa1_label = ttkb.Label(p_frame, text="当前水平PDOA值1 PDOA1:")
        self.pdoa1_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.pdoa1_entry = ttkb.Entry(p_frame, width=8, justify='center')
        self.pdoa1_entry.grid(row=4, column=1, padx=0, pady=5, sticky="w")

        # 添加当前垂直PDOA值1 PDOA2:u16
        self.pdoa2_label = ttkb.Label(p_frame, text="当前垂直PDOA值1 PDOA2:")
        self.pdoa2_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.pdoa2_entry = ttkb.Entry(p_frame, width=8, justify='center')
        self.pdoa2_entry.grid(row=5, column=1, padx=0, pady=5, sticky="w")

        # 在新的 Frame 中添加 bt_write_aoa_calibration
        self.bt_write_aoa_calibration = ttkb.Button(p_frame, text="写入AOA校准值", command=self.real_wirte_aoa_calibration, bootstyle='outline-primary')
        self.bt_write_aoa_calibration.grid(row=6, column=0, padx=5, pady=5, sticky="w")

    # def create_work_mode_setting_UI(self, p_frame):
    #     # 添加 work_mode_label 和 work_mode_entry
    #     self.work_mode_label = ttkb.Label(p_frame, text="工作模式：")
    #     self.work_mode_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

    #     # 定义工作模式选项
    #     work_modes = [
    #         "Tx: 0x00",
    #         "Rx: 0x01",
    #         "测距模式Tx: 0x02",
    #         "测距模式Rx: 0x03"
    #     ]

    #     self.work_mode_combobox = ttkb.Combobox(p_frame, values=work_modes, state="readonly", width=15)
    #     self.work_mode_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    #     self.work_mode_combobox.current(0)

    #     self.bt_write_work_mode = ttkb.Button(p_frame, text="设置工作模式", command=self.real_wirte_work_mode, bootstyle='outline-primary')
    #     self.bt_write_work_mode.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_tx_switch_UI(self, p_frame):
        self.tx_switch_label = ttkb.Label(p_frame, text="TX开关：")
        self.tx_switch_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.tx_switch_combobox = ttkb.Combobox(p_frame, values=["关闭", "打开"], state="readonly", width=8)
        self.tx_switch_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.tx_switch_combobox.current(0)

        self.bt_tx_switch = ttkb.Button(p_frame, text="设置TX开关", command=self.real_set_tx_switch, bootstyle='outline-primary')
        self.bt_tx_switch.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_rx_channel_config_UI(self, p_frame):
        self.rx_channel_config_label = ttkb.Label(p_frame, text="Rx通道配置：")
        self.rx_channel_config_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # 定义天线配置选项
        rx_channel_configs = [
            "单开天线1 RX： 0x01",
            "单开天线2 RX： 0x02",
            "单开天线3 RX： 0x04",
            "双开天线1+2 Rx： 0x03",
            "双开天线2+3 Rx： 0x06",
            "双开天线1+3 Rx： 0x05",
            "三开天线1+2+3 Rx： 0x07"
        ]

        self.rx_channel_config_combobox = ttkb.Combobox(p_frame, values=rx_channel_configs, state="readonly", width=20)
        self.rx_channel_config_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.rx_channel_config_combobox.current(0)

        self.bt_rx_channel_config = ttkb.Button(p_frame, text="设置RX通道", command=self.real_set_rx_channel_config, bootstyle='outline-primary')
        self.bt_rx_channel_config.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_rx_switch_UI(self, p_frame):
        self.rx_switch_label = ttkb.Label(p_frame, text="RX开关：")
        self.rx_switch_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.rx_switch_combobox = ttkb.Combobox(p_frame, values=["关闭", "打开"], state="readonly", width=8)
        self.rx_switch_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.rx_switch_combobox.current(0)

        self.bt_rx_switch = ttkb.Button(p_frame, text="设置RX开关", command=self.real_set_rx_switch, bootstyle='outline-primary')
        self.bt_rx_switch.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_ranging_mode_id_config_UI(self, p_frame):
        self.ranging_mode_id_label = ttkb.Label(p_frame, text="测距模式SYNC ID配置：(0-65535)")
        self.ranging_mode_id_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.ranging_mode_id_entry = ttkb.Entry(p_frame, width=8)
        self.ranging_mode_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.bt_ranging_mode_id_config = ttkb.Button(p_frame, text="设置测距模式ID", command=self.real_ranging_mode_id_config, bootstyle='outline-primary')
        self.bt_ranging_mode_id_config.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_ranging_mode_freq_config_UI(self, p_frame):
        self.ranging_mode_freq_label = ttkb.Label(p_frame, text="测距模式频率配置：(Hz)")
        self.ranging_mode_freq_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.ranging_mode_freq_combobox = ttkb.Combobox(p_frame, values=[10, 20, 50], state="readonly", width=8)
        self.ranging_mode_freq_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.ranging_mode_freq_combobox.current(1)

        self.bt_ranging_mode_freq_config = ttkb.Button(p_frame, text="设置频率", command=self.real_ranging_mode_freq_config, bootstyle='outline-primary')
        self.bt_ranging_mode_freq_config.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_ranging_mode_tx_switch_UI(self, p_frame):
        self.ranging_mode_tx_switch_label = ttkb.Label(p_frame, text="测距模式Tx开关：")
        self.ranging_mode_tx_switch_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.ranging_mode_tx_switch_combobox = ttkb.Combobox(p_frame, values=["关闭", "打开"], state="readonly", width=8)
        self.ranging_mode_tx_switch_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.ranging_mode_tx_switch_combobox.current(0)

        self.bt_ranging_mode_tx_switch = ttkb.Button(p_frame, text="设置Tx开关", command=self.real_ranging_mode_tx_switch, bootstyle='outline-primary')
        self.bt_ranging_mode_tx_switch.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_ranging_mode_rx_channel_config_UI(self, p_frame):
        self.ranging_mode_rx_channel_config_label = ttkb.Label(p_frame, text="测距模式Rx通道配置：")
        self.ranging_mode_rx_channel_config_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # 定义天线配置选项
        rx_channel_configs = [
            "单开天线1 RX： 0x01",
            "单开天线2 RX： 0x02",
            "单开天线3 RX： 0x04",
            "双开天线1+2 Rx： 0x03",
            "双开天线2+3 Rx： 0x06",
            "双开天线1+3 Rx： 0x05",
            "三开天线1+2+3 Rx： 0x07"
        ]

        self.ranging_mode_rx_channel_config_combobox = ttkb.Combobox(p_frame, values=rx_channel_configs, state="readonly", width=20)
        self.ranging_mode_rx_channel_config_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.ranging_mode_rx_channel_config_combobox.current(0)

        self.bt_ranging_mode_rx_channel_config = ttkb.Button(p_frame, text="设置RX通道", command=self.real_ranging_mode_rx_channel_config, bootstyle='outline-primary')
        self.bt_ranging_mode_rx_channel_config.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    def create_ranging_mode_rx_switch_UI(self, p_frame):
        self.ranging_mode_rx_switch_label = ttkb.Label(p_frame, text="测距模式Rx开关：")
        self.ranging_mode_rx_switch_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.ranging_mode_rx_switch_combobox = ttkb.Combobox(p_frame, values=["关闭", "打开"], state="readonly", width=8)
        self.ranging_mode_rx_switch_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.ranging_mode_rx_switch_combobox.current(0)

        self.bt_ranging_mode_rx_switch = ttkb.Button(p_frame, text="设置RX开关", command=self.real_ranging_mode_rx_switch, bootstyle='outline-primary')
        self.bt_ranging_mode_rx_switch.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    # def create_auto_calibration_UI(self, p_frame):
    #     # 真实距离输入框
    #     self.distance_label = ttkb.Label(p_frame, text="真实距离：")
    #     self.distance_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
    #     self.distance_entry = ttkb.Entry(p_frame, width=8)
    #     self.distance_entry.grid(row=1, column=1, padx=0, pady=5, sticky="w")
    #     self.distance_entry.insert(0, "100")  # 设置默认值为100cm
    #     self.distance_label2 = ttkb.Label(p_frame, text="厘米")
    #     self.distance_label2.grid(row=1, column=2, padx=5, pady=5, sticky="w")
    #     # 水平角输入框
    #     self.horizontal_angle_label = ttkb.Label(p_frame, text="真实水平角：")
    #     self.horizontal_angle_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
    #     self.horizontal_angle_entry = ttkb.Entry(p_frame, width=8)
    #     self.horizontal_angle_entry.grid(row=2, column=1, padx=0, pady=5, sticky="w")
    #     self.horizontal_angle_entry.insert(0, "0")  # 设置默认值为0
    #     self.horizontal_angle_entry.config(state="readonly")
    #     self.horizontal_angle_label2 = ttkb.Label(p_frame, text="度")
    #     self.horizontal_angle_label2.grid(row=2, column=2, padx=5, pady=5, sticky="w")
    #     # 俯仰角输入框
    #     self.pitch_angle_label = ttkb.Label(p_frame, text="真实俯仰角：")
    #     self.pitch_angle_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
    #     self.pitch_angle_entry = ttkb.Entry(p_frame, width=8)
    #     self.pitch_angle_entry.grid(row=3, column=1, padx=0, pady=5, sticky="w")
    #     self.pitch_angle_entry.insert(0, "0")  # 设置默认值为0
    #     self.pitch_angle_entry.config(state="readonly")
    #     self.pitch_angle_label2 = ttkb.Label(p_frame, text="度")
    #     self.pitch_angle_label2.grid(row=3, column=2, padx=5, pady=5, sticky="w")
    #     # 开始自动校准按钮
    #     self.bt_start_calibration = ttkb.Button(p_frame, text="开始自动校准", command=self.start_auto_calibration, bootstyle='outline-primary')
    #     self.bt_start_calibration.grid(row=4, column=0, padx=5, pady=(20,5), sticky="w")

    #     # 测试校准结果按钮
    #     self.bt_test_calibration = ttkb.Button(p_frame, text="测试校准结果", command=self.test_auto_calibration_result, bootstyle='outline-success')
    #     self.bt_test_calibration.grid(row=5, column=0, padx=5, pady=5, sticky="w")

    #     # 让用户按参数摆放设备，真实距离单位厘米 真实水平角，俯仰角单位°，点按键开始自动校准，另外一个按键测试校准结果

    def on_power_level_combobox_select(self, event):
        selected_value = int(self.power_level_combobox.get())
        self.power_level_dbm_label.config(text=f"={selected_value * 0.5 - 55:.1f} dBm/MHz")

    def clear_log(self):
        self.cal_log_text.delete('1.0', tk.END)

    def toggle_state_machine(self):
        # from demo_board import g_cb_actived_ports,g_cb_selected_actived_ports,g_cb_baudrate_combobox  # 从 demo_board 导入 g_cb_actived_ports
        from demo_board import g_cb_actived_ports,g_cb_selected_actived_ports
        #g_cb_actived_ports = ['com8']  #  先编一个
        if self.cb_ft_onoff.instate(['selected']):
            # 启动状态机
            # baud_rate = g_cb_baudrate_combobox.get()
            baud_rate = self.baudrate_combobox.get()

            if g_cb_actived_ports:
                port = g_cb_selected_actived_ports  # 假设 g_cb_actived_ports 是一个列表，取第一个端口
                try:
                    ser = serial.Serial(port, baud_rate, timeout=1)
                except serial.SerialException as e:
                    #self.cb_cal_insert_log(f"打开 {port}失败: {e}")
                    ser = None
                if ser:
                    ser.close()
                    self.serial_state_machine = SerialStateMachine(port, baud_rate, self.response_queue)
                    self.serial_state_machine.start()
                else:
                    self.cb_cal_insert_log(f"打开端口 {port} 失败\n")
                    self.cb_ft_onoff.invoke()
                    return
                # self.serial_state_machine.start()
                self.ft_mode_on = 0x01
                self.on_button_click("厂测开关")#发送厂测开关命令
            else:
                self.cb_cal_insert_log("没有可用的端口\n")
                if self.cb_ft_onoff.instate(['selected']):#没有可用端口，不让打开
                    self.cb_ft_onoff.invoke()
        else:
            self.ft_mode_on = 0x00
            self.on_button_click("厂测开关")#发送厂测开关命令
            time.sleep(1)#等待命令执行完成
            # 停止状态机
            if self.serial_state_machine:
                self.serial_state_machine.stop()
                self.serial_state_machine = None

    def on_button_click(self, button_text):
        #from demo_board import g_cb_actived_ports
        #self.cal_log_label.config(text=f"操作结果：{g_cb_actived_ports}")
        data = []
        if not button_text == "厂测开关":
            for button in self.buttons_name2hd.values():
                button.config(bootstyle='outline')  # 重置所有按钮颜色
            # self.buttons_name2hd["自动校准模式"].config(bootstyle='outline-danger')
            # if button_text == "自动校准模式":
            #     self.buttons_name2hd[button_text].config(bootstyle='danger')
            # else:
            self.buttons_name2hd[button_text].config(bootstyle='success')  # 设置当前按钮颜色
            # 显示相应的 Frame
            frame_name = self.buttons_name2hd[button_text].frame_name
            self.show_operate_frame(frame_name)

            if button_text in [
                "写入默认功率等级",  # 这些按键由于需要额外处理，所以直接返回
                "写入频偏校准值",
                "写入TOF校准值",
                "读取AOA校准值",
                "写入AOA校准值",
                # "工作模式设置",
                "Tx发包数量",
                "Tx发包间隔",
                "Tx开关",
                "Rx通道配置",
                "Rx开关",
                "测距模式SYNC ID配置",
                "测距模式频率配置",
                "测距模式Tx开关",
                "测距模式Rx通道配置",
                "测距模式Rx开关",
                # "自动校准模式"
            ]:
                return
        else:
            if self.ft_mode_on:
                data = [0x01]
            else:
                data = [0x00]
        # 发送命令到状态机
        if self.serial_state_machine:
            #cmd = self.button_name_to_cmd.get(button_text)  
            cmd_h, cmd_l = self.ftcmd_map.get(button_text, (0x00, 0x00))
            resp = 0x00
            #data = [0x00]
            #print(f"Command in hex: {data}")
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送{button_text}命令\n","black")#: {packet}
            if packet:
                #hex_cmd = self.convert_to_hex(cmd)
                self.serial_state_machine.send_command(packet)

    def show_operate_frame(self, frame_name):
        # 定义提示内容字典
        tips_dict = {
            "当前操作_读取芯片ID": "读取芯片ID的提示内容",
            "当前操作_读取频偏校准值": "读取频偏校准值的提示内容",
            "当前操作_写入频偏校准值": "写入频偏校准值的提示内容",
            "当前操作_读取默认功率等级": "读取默认功率等级的提示内容",
            "当前操作_写入默认功率等级": "step:0.5dB,范围：-55.0dBm到-24.0dBm",
            "当前操作_读取TOF校准值": "单位为cm，保留一位精度,如：120cm值为1200",
            "当前操作_写入TOF校准值": "写入TOF校准值的提示内容",
            "当前操作_读取AOA校准值数量": "校准值数量",
            # "当前操作_读取AOA校准值": "读取第N个校准值,一般为0不用改动",     
            "当前操作_读取AOA校准值": "校准值参数说明：\n"
                                    "\n"
                                    "AOAH: 水平角校准值\n"
                                    "\n"
                                    "AOAV: 垂直角校准值\n"
                                    "\n"
                                    "PDOA1: 水平PDOA校准值\n"
                                    "\n"
                                    "PDOA2: 垂直PDOA校准值\n",
            "当前操作_写入AOA校准值": "校准值范围：-32768到32767",
            "当前操作_工作模式设置": "工作模式设置的提示内容",
            "当前操作_读取工作模式": "读取工作模式的提示内容",
            "当前操作_Tx发包数量": "Tx发包数量的提示内容",
            "当前操作_Tx发包间隔": "单位us，长发包模式设置为最小间隔7",
            "当前操作_Tx开关": "Tx开关的提示内容",
            "当前操作_Rx通道配置": "Rx通道配置的提示内容",
            "当前操作_Rx开关": "Rx开关的提示内容",
            "当前操作_获取Rx收包数量": "获取Rx收包数量的提示内容",
            "当前操作_测距模式SYNC ID配置": "测距模式SYNC ID配置的提示内容",
            "当前操作_读取测距模式SYNC ID": "读取测距模式SYNC ID的提示内容",
            "当前操作_测距模式频率配置": "测距模式频率配置的提示内容",
            "当前操作_读取测距模式频率": "读取测距模式频率的提示内容",
            "当前操作_测距模式Tx开关": "测距模式Tx开关的提示内容",
            "当前操作_测距模式Rx通道配置": "测距模式Rx通道配置的提示内容",
            "当前操作_测距模式Rx开关": "测距模式Rx开关的提示内容",
            "当前操作_获取测距模式Rx数据结果": "获取测距模式Rx数据结果的提示内容",
            # "当前操作_自动校准模式": "请按以下参数摆放好测试设备，注意对准天线..."
        }
        # 隐藏所有 Frame
        for widget in self.operate_container.winfo_children():
            widget.grid_forget()
        # 显示指定的 Frame
        frame = self.frames.get(frame_name, None)
        self.operate_lb.grid(row=0, column=0, sticky='w', padx=10, pady=10)
        self.operate_lb.config(text=frame_name, font=('微软雅黑', 10, 'bold'))
        self.operate_note_lb.grid(row=1, column=0, sticky='w', padx=10, pady=10)
        # 获取对应的提示内容
        tip_text = tips_dict.get(frame_name, "默认提示内容")
        self.operate_note_lb.config(text=f"Tips: {tip_text}")
        if frame:
            frame.update_idletasks()  # 更新 Frame 内的控件
            frame.grid(row=2, column=0, sticky='nsew', padx=10, pady=10)

    def real_wirte_freq_offset(self):
        freq_offset = int(self.freq_offset_combobox.get())
        data = [freq_offset]
                # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("写入频偏校准值", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log( f"发送写入频偏校准值命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_wirte_powercode(self):
        power_code = int(self.power_level_combobox.get())
        data = [power_code]
                # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("写入默认功率等级", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送写入默认功率等级命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)


    def real_wirte_tof_calibration(self):
        tof_calibration_str = self.tof_calibration_entry.get()

        # if not tof_calibration_str.isdigit():
        #     self.cb_cal_insert_log( "输入的TOF校准值无效，请输入一个整数\n","red")
        #     return
        if not tof_calibration_str.lstrip('-').isdigit():
            self.cb_cal_insert_log("输入的TOF校准值无效，请输入一个整数（-32768 至 32767）\n", "red")
            return
        
        try:
            tof_calibration = int(tof_calibration_str)

            # if 0 <= tof_calibration <= 65535:
            if -32768 <= tof_calibration <= 32767:
                data = [(tof_calibration >> 8) & 0xFF, tof_calibration & 0xFF]
                # 发送命令到状态机
                if self.serial_state_machine:
                    cmd_h, cmd_l = self.ftcmd_map.get("写入TOF校准值", (0x00, 0x00))
                    resp = 0x00
                    packet = create_packet(cmd_h, cmd_l, resp, data)
                    self.cb_cal_insert_log(f"发送写入TOF校准值命令\n","black")
                    if packet:
                        self.serial_state_machine.send_command(packet)
            else:
                # self.cb_cal_insert_log("输入的TOF校准值不在有效范围内（0-65535）\n","red")
                self.cb_cal_insert_log("输入的TOF校准值不在有效范围内（-32768-32767）\n","red")
        except ValueError:
            self.cb_cal_insert_log( "输入的TOF校准值无效，请输入一个整数\n","red")



    def real_read_aoa_calibration(self):
        # aoa_calibration_str = self.aoa_calibration_entry.get()
        # if not aoa_calibration_str.isdigit():
        #     self.cb_cal_insert_log("输入的校准值序号无效，请输入一个整数\n","red")
        #     return

        # try:
        #     aoa_calibration = int(aoa_calibration_str)
        #     if 0 <= aoa_calibration <= 255:
        #         data = [aoa_calibration]
        #         # 发送命令到状态机
        #         if self.serial_state_machine:
        #             cmd_h, cmd_l = self.ftcmd_map.get("读取AOA校准值", (0x00, 0x00))
        #             resp = 0x00
        #             packet = create_packet(cmd_h, cmd_l, resp, data)
        #             self.cb_cal_insert_log(f"发送读取AOA校准值命令\n","black")
        #             if packet:
        #                 self.serial_state_machine.send_command(packet)
        #     else:
        #         self.cb_cal_insert_log("输入的校准值序号不在有效范围内（0-255）\n","red")
        # except ValueError:
        #     self.cb_cal_insert_log("输入的校准值序号无效，请输入一个整数\n","red")
        data = [0]  # 默认读取第0个校准值
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("读取AOA校准值", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送读取AOA校准值命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_wirte_aoa_calibration(self):
        # aoa_calibration_str = self.aoa_calibration_wirte_entry.get()

        try:
            # aoa_calibration_index = int(aoa_calibration_str)
            aoa_calibration_index = 0   # 默认写入第0个校准值
            if 0 <= aoa_calibration_index <= 255:
                aoah_str = self.aoah_entry.get()
                aoav_str = self.aoav_entry.get()
                pdoa1_str = self.pdoa1_entry.get()
                pdoa2_str = self.pdoa2_entry.get()

                try:
                    aoah = int(aoah_str)
                    if not (-32768 <= aoah <= 32767):
                        raise ValueError("真实水平角度超出有效范围（-32768到32767）")
                except ValueError:
                    self.cb_cal_insert_log("输入的真实水平角度无效，请输入一个整数\n", "red")
                    return

                try:
                    aoav = int(aoav_str)
                    if not (-32768 <= aoav <= 32767):
                        raise ValueError("真实垂直角度超出有效范围（-32768到32767）")
                except ValueError:
                    self.cb_cal_insert_log("输入的真实垂直角度无效，请输入一个整数\n", "red")
                    return

                try:
                    pdoa1 = int(pdoa1_str)
                    if not (-32768 <= pdoa1 <= 32767):
                        raise ValueError("当前水平PDOA值1超出有效范围（-32768到32767）")
                except ValueError:
                    self.cb_cal_insert_log("输入的当前水平PDOA值1无效，请输入一个整数\n", "red")
                    return

                try:
                    pdoa2 = int(pdoa2_str)
                    if not (-32768 <= pdoa2 <= 32767):
                        raise ValueError("当前垂直PDOA值1超出有效范围（-32768到32767）")
                except ValueError:
                    self.cb_cal_insert_log("输入的当前垂直PDOA值1无效，请输入一个整数\n", "red")
                    return

                # 确保数据在有效范围内
                data = [
                    aoa_calibration_index,
                    (aoah >> 8) & 0xFF, aoah & 0xFF,
                    (aoav >> 8) & 0xFF, aoav & 0xFF,
                    (pdoa1 >> 8) & 0xFF, pdoa1 & 0xFF,
                    (pdoa2 >> 8) & 0xFF, pdoa2 & 0xFF
                ]

                # 发送命令到状态机
                if self.serial_state_machine:
                    cmd_h, cmd_l = self.ftcmd_map.get("写入AOA校准值", (0x00, 0x00))
                    resp = 0x00
                    packet = create_packet(cmd_h, cmd_l, resp, data)
                    self.cb_cal_insert_log(f"发送写入AOA校准值命令\n", "black")
                    if packet:
                        self.serial_state_machine.send_command(packet)
            else:
                self.cb_cal_insert_log("输入的校准值序号不在有效范围内（0-255）\n", "red")
        except ValueError as e:
            self.cb_cal_insert_log(f"输入的校准值序号无效，请输入一个整数: {e}\n", "red")

    # def real_wirte_work_mode(self):
    #     work_mode_str = self.work_mode_combobox.get()
    #     work_mode = 0x00
    #     if work_mode_str == "Tx: 0x00":
    #         work_mode = 0x00
    #     elif work_mode_str == "Rx: 0x01":
    #         work_mode = 0x01
    #     elif work_mode_str == "测距模式Tx: 0x02":
    #         work_mode = 0x02
    #     elif work_mode_str == "测距模式Rx: 0x03":
    #         work_mode = 0x03
    #     data = [work_mode]
    #     # 发送命令到状态机
    #     if self.serial_state_machine:
    #         cmd_h, cmd_l = self.ftcmd_map.get("工作模式设置", (0x00, 0x00))
    #         resp = 0x00
    #         packet = create_packet(cmd_h, cmd_l, resp, data)
    #         self.cb_cal_insert_log(f"发送工作模式设置命令\n","black")
    #         if packet:
    #             self.serial_state_machine.send_command(packet)

    def real_set_tx_packet_count(self):
        tx_packet_count_str = self.tx_packet_count_entry.get()
        if not tx_packet_count_str.isdigit():
            self.cb_cal_insert_log("输入的发包数量无效，请输入一个整数\n","red")
            return

        try:
            tx_packet_count = int(tx_packet_count_str)
            if tx_packet_count < 0:
                self.cb_cal_insert_log("输入的发包数量不能为负数\n","red")
                return
            data = [(tx_packet_count >> 24) & 0xFF, (tx_packet_count >> 16) & 0xFF, (tx_packet_count >> 8) & 0xFF, tx_packet_count & 0xFF]
            # 发送命令到状态机
            if self.serial_state_machine:
                cmd_h, cmd_l = self.ftcmd_map.get("Tx发包数量", (0x00, 0x00))
                resp = 0x00
                packet = create_packet(cmd_h, cmd_l, resp, data)
                self.cb_cal_insert_log(f"发送Tx发包数量命令\n","black")
                if packet:
                    self.serial_state_machine.send_command(packet)
        except ValueError:
            self.cb_cal_insert_log("输入的发包数量无效，请输入一个整数\n","red")
    
    def real_set_tx_packet_interval(self):
        tx_packet_interval_str = self.tx_packet_interval_entry.get()
        if not tx_packet_interval_str.isdigit():
            self.cb_cal_insert_log("输入的发包间隔无效，请输入一个整数\n","red")
            return

        try:
            tx_packet_interval = int(tx_packet_interval_str)
            if tx_packet_interval < 7 or tx_packet_interval > 65535:
                self.cb_cal_insert_log("输入的发包间隔不在有效范围内（7-65535）\n","red")
                return
            data = [(tx_packet_interval >> 8) & 0xFF, tx_packet_interval & 0xFF]
            # 发送命令到状态机
            if self.serial_state_machine:
                cmd_h, cmd_l = self.ftcmd_map.get("Tx发包间隔", (0x00, 0x00))
                resp = 0x00
                packet = create_packet(cmd_h, cmd_l, resp, data)
                self.cb_cal_insert_log(f"发送Tx发包间隔命令\n","black")
                if packet:
                    self.serial_state_machine.send_command(packet)
        except ValueError:
            self.cb_cal_insert_log("输入的发包间隔无效，请输入一个整数\n","red")

    def real_set_tx_switch(self):
        tx_switch_str = self.tx_switch_combobox.get()
        tx_switch = 0x00
        if tx_switch_str == "打开":
            tx_switch = 0x01
        data = [tx_switch]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("Tx开关", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送Tx开关命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_set_rx_channel_config(self):
        rx_channel_config_str = self.rx_channel_config_combobox.get()
        rx_channel_config = 0x00
        if rx_channel_config_str == "单开天线1 RX： 0x01":
            rx_channel_config = 0x01
        elif rx_channel_config_str == "单开天线2 RX： 0x02":
            rx_channel_config = 0x02
        elif rx_channel_config_str == "单开天线3 RX： 0x04":
            rx_channel_config = 0x04
        elif rx_channel_config_str == "双开天线1+2 Rx： 0x03":
            rx_channel_config = 0x03
        elif rx_channel_config_str == "双开天线2+3 Rx： 0x06":
            rx_channel_config = 0x06
        elif rx_channel_config_str == "双开天线1+3 Rx： 0x05":
            rx_channel_config = 0x05
        elif rx_channel_config_str == "三开天线1+2+3 Rx： 0x07":
            rx_channel_config = 0x07
        data = [rx_channel_config]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("Rx通道配置", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送Rx通道配置命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_set_rx_switch(self):
        rx_switch_str = self.rx_switch_combobox.get()
        rx_switch = 0x00
        if rx_switch_str == "打开":
            rx_switch = 0x01
        data = [rx_switch]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("Rx开关", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送Rx开关命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_ranging_mode_id_config(self):
        ranging_mode_id_str = self.ranging_mode_id_entry.get()
        if not ranging_mode_id_str.isdigit():
            self.cb_cal_insert_log("输入的测距模式ID无效，请输入一个整数\n","red")
            return

        try:
            ranging_mode_id = int(ranging_mode_id_str)
            if 0 <= ranging_mode_id <= 65535:
                data = [(ranging_mode_id >> 8) & 0xFF, ranging_mode_id & 0xFF]
                # 发送命令到状态机
                if self.serial_state_machine:
                    cmd_h, cmd_l = self.ftcmd_map.get("测距模式SYNC ID配置", (0x00, 0x00))
                    resp = 0x00
                    packet = create_packet(cmd_h, cmd_l, resp, data)
                    self.cb_cal_insert_log(f"发送测距模式SYNC ID配置命令\n","black")
                    if packet:
                        self.serial_state_machine.send_command(packet)
            else:
                self.cb_cal_insert_log("输入的测距模式ID不在有效范围内（0-65535）\n","red")
        except ValueError:
            self.cb_cal_insert_log("输入的测距模式ID无效，请输入一个整数\n","red")

    def real_ranging_mode_freq_config(self):
        ranging_mode_freq_str = self.ranging_mode_freq_combobox.get()
        ranging_mode_freq = 0x00
        if ranging_mode_freq_str == "10":
            ranging_mode_freq = 0x10
        elif ranging_mode_freq_str == "20":
            ranging_mode_freq = 0x20
        elif ranging_mode_freq_str == "50":
            ranging_mode_freq = 0x50
        data = [ranging_mode_freq]
        # print(f"data: {data}")
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("测距模式频率配置", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送测距模式频率配置命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_ranging_mode_tx_switch(self):
        ranging_mode_tx_switch_str = self.ranging_mode_tx_switch_combobox.get()
        ranging_mode_tx_switch = 0x00
        if ranging_mode_tx_switch_str == "打开":
            ranging_mode_tx_switch = 0x01
        data = [ranging_mode_tx_switch]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("测距模式Tx开关", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送测距模式Tx开关命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_ranging_mode_rx_channel_config(self):
        rx_channel_config_str = self.ranging_mode_rx_channel_config_combobox.get()
        rx_channel_config = 0x00
        if rx_channel_config_str == "单开天线1 RX： 0x01":
            rx_channel_config = 0x01
        elif rx_channel_config_str == "单开天线2 RX： 0x02":
            rx_channel_config = 0x02
        elif rx_channel_config_str == "单开天线3 RX： 0x04":
            rx_channel_config = 0x04
        elif rx_channel_config_str == "双开天线1+2 Rx： 0x03":
            rx_channel_config = 0x03
        elif rx_channel_config_str == "双开天线2+3 Rx： 0x06":
            rx_channel_config = 0x06
        elif rx_channel_config_str == "双开天线1+3 Rx： 0x05":
            rx_channel_config = 0x05
        elif rx_channel_config_str == "三开天线1+2+3 Rx： 0x07":
            rx_channel_config = 0x07
        data = [rx_channel_config]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("测距模式Rx通道配置", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送测距模式Rx通道配置命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def real_ranging_mode_rx_switch(self):
        rx_switch_str = self.ranging_mode_rx_switch_combobox.get()
        rx_switch = 0x00
        if rx_switch_str == "打开":
            rx_switch = 0x01
        data = [rx_switch]
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("测距模式Rx开关", (0x00, 0x00))
            resp = 0x00
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送测距模式Rx开关命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def start_auto_calibration(self):
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("自动校准模式", (0x00, 0x00))
            resp = 0x00
            data = []
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送自动校准模式命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def test_auto_calibration_result(self):
        # 发送命令到状态机
        if self.serial_state_machine:
            cmd_h, cmd_l = self.ftcmd_map.get("测试校准结果", (0x00, 0x00))
            resp = 0x00
            data = []
            packet = create_packet(cmd_h, cmd_l, resp, data)
            self.cb_cal_insert_log(f"发送测试校准结果命令\n","black")
            if packet:
                self.serial_state_machine.send_command(packet)

    def convert_to_hex(self, cmd_str):
        """
        将命令字符串转换为十六进制码
        """
        return bytes.fromhex(cmd_str.replace(" ", ""))

    def process_responses(self):
        buffer = bytearray()

        while True:
            response = self.response_queue.get()
            # print(f"process_responses started,{response}")
            buffer.extend(response)
            print(f"len={len(buffer)}")
            while len(buffer) >= 6:  # 至少要有6个字节才能开始解析
                start_code = buffer[0]
                if start_code != 0x5A:
                    # 找到第一个起始码为 0x5A 的数据包
                    buffer.pop(0)
                    continue
                
                cmd_h = buffer[1]
                cmd_l = buffer[2]
                resp = buffer[3]
                data_length = buffer[4]
                
                total_length = 5 + data_length + 1  # 起始码 + 命令码 + 响应位 + 数据长度 + 数据 + 校验和
                
                if len(buffer) < total_length:
                    # 数据包还不完整，等待更多数据
                    break
                
                # 取出完整的数据包
                packet = buffer[:total_length]
                buffer = buffer[total_length:]  # 剩余的数据

                # 校验和计算
                data = packet[5:5 + data_length]
                checksum = packet[5 + data_length]
                # end_code = packet[5 + data_length + 1]
                
                # 计算校验和
                calculated_checksum = (cmd_h + cmd_l + resp + data_length + sum(data)) & 0xFF  # 取低8位

                
                if checksum != calculated_checksum:
                    self.cb_cal_insert_log("校验和错误，无法解析\n")
                    continue
                
                # 解析成功，记录解析结果
                # self.cb_cal_insert_log(f"\n收到响应包: \n",show_time=True)
                # self.cb_cal_insert_log(f"起始码: {start_code:02X}\n",show_time=False)
                # self.cb_cal_insert_log(f"命令码: {cmd_h:02X}{cmd_l:02X}\n", show_time=False)
                # self.cb_cal_insert_log(f"响应位: {resp}\n", show_time=False)
                # self.cb_cal_insert_log(f"数据长度: {data_length}\n", show_time=False)
                # self.cb_cal_insert_log(f"数据: {data.hex()}\n", show_time=False)
                # self.cb_cal_insert_log(f"校验和: {checksum}\n", show_time=False)
                # self.cb_cal_insert_log(f"结束码: {end_code:02X}\n", show_time=False)
                    # 调用对应的处理函数
                command_code = (cmd_h, cmd_l)
                if command_code in self.command_handlers:
                    self.command_handlers[command_code](data)#data是response中的数据部分
                else:
                    print(f"Unknown command code: {command_code}")

            # 检查缓冲区中是否还有数据，如果有但找不到新的起始码 0x5A，则认为是脏数据
            while len(buffer) > 0 and buffer[0] != 0x5A:
                buffer.pop(0)
    
    # 厂测开关命令响应结果处理
    def handle_factory_switch(self, response):
        if self.ft_mode_on:
            if response[0] == 0x00:
                self.cb_cal_insert_log("工厂模式已开启\n","green")
            elif response[0] == 0x01:
                self.cb_cal_insert_log("工厂模式开启失败\n","red")
            else:
                self.cb_cal_insert_log("失败：未知状态\n","red")
        else:
            if response[0] == 0x00:
                self.cb_cal_insert_log("工厂模式已关闭\n","green")
            elif response[0] == 0x01:
                self.cb_cal_insert_log("工厂模式关闭失败\n","red")
            else:
                self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_read_chip_id(self, response):
        # 处理 "读取芯片ID" 的逻辑
        chip_id = response[0:4]
        print(f"Chip ID: {chip_id}")
        if all(byte == 0xFF for byte in chip_id):  # 检查是否全为 0xFF
            self.cb_cal_insert_log("Failed to read chip ID: all bytes are 0xFF")
        else:
            self.cb_cal_insert_log(f"Chip ID: {chip_id.hex()}","green")

    def handle_read_freq_offset(self, response):
        # 处理 "读取频偏校准值" 的逻辑
        result = int(response[0])
        if result == 0xff:
            self.cb_cal_insert_log("读取频偏校准值失败\n","red")
        else:
            self.cb_cal_insert_log(f"读取频偏校准值成功，频偏校准值为 {result}\n","green")


    def handle_write_freq_offset(self, response):
        # 处理 "写入频偏校准值" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("写入频偏校准值成功\n","green")
        else:
            self.cb_cal_insert_log("写入频偏校准值失败\n","red")
        pass

    def handle_read_default_power_level(self, response):
        result = int(response[0])
        if result == 0xff:
            self.cb_cal_insert_log("读取默认功率等级失败,或未设置默认功率\n","red")
        elif result < 63:
            dbm = result * 0.5 - 55
            self.cb_cal_insert_log(f"读取默认功率等级成功，功率等级为 {result}, {dbm} dBm/MHz\n","green")
        else:
            self.cb_cal_insert_log("失败：未知功率等级\n","red")


    def handle_write_default_power_level(self, response):
        # 处理 "写入默认功率等级" 的逻辑
        #print(f"handle_write_default_power_level={response}")
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("写入默认功率等级成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("写入默认功率等级失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_read_tof_calibration(self, response):
        # 处理 "读取TOF校准值" 的逻辑
        print(f"handle_read_tof_calibration={response}")
        # result = int.from_bytes(response[0:2], byteorder='big')
        # if result == 0xffff:
        #     self.cb_cal_insert_log("读取TOF校准值失败\n","red")
        # else:
        #     self.cb_cal_insert_log(f"读取TOF校准值成功，TOF校准值为 {result}\n","green")
        result = self.to_signed_16bit((response[0] << 8) | response[1])
        self.cb_cal_insert_log(f"读取TOF校准值成功，TOF校准值为 {result}\n","green")

    def handle_write_tof_calibration(self, response):
        # 处理 "写入TOF校准值" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("写入TOF校准值成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("写入TOF校准值失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_read_aoa_calibration_count(self, response):
        # 处理 "读取AOA校准值数量" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("读取AOA校准值数量失败\n","red")
        else:
            self.cb_cal_insert_log(f"读取AOA校准值数量成功，数量为 {result}\n","green")

    def handle_read_aoa_calibration(self, response):
        # 处理 "读取AOA校准值" 的逻辑
        print(f"handle_read_aoa_calibration={response}")
        
        aoah = self.to_signed_16bit((response[0] << 8) | response[1])
        aoav = self.to_signed_16bit((response[2] << 8) | response[3])
        pdoa1 = self.to_signed_16bit((response[4] << 8) | response[5])
        pdoa2 = self.to_signed_16bit((response[6] << 8) | response[7])
        self.cb_cal_insert_log(f"读取AOA校准值，AOAH={aoah}, AOAV={aoav}, PDOA1={pdoa1}, PDOA2={pdoa2}\n","green")

    def handle_write_aoa_calibration(self, response):
        # 处理 "写入AOA校准值" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("写入AOA校准值成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("写入AOA校准值失败\n","red")
        

    def handle_set_work_mode(self, response):
        # 处理 "工作模式设置" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置工作模式成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置工作模式失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")
        pass

    def handle_read_work_mode(self, response):
        # 处理 "读取工作模式" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("当前模式: TX\n", "green")
        elif result == 0x01:
            self.cb_cal_insert_log("当前模式: RX\n", "green")
        elif result == 0x02:
            self.cb_cal_insert_log("当前模式: 测距模式TX\n", "green")
        elif result == 0x03:
            self.cb_cal_insert_log("当前模式: 测距模式RX\n", "green")
        elif result == 0xFF:
            self.cb_cal_insert_log("读取工作模式失败\n", "red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n", "red")


    def handle_tx_packet_count(self, response):
        # 处理 "Tx发包数量" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置Tx发包数量成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置Tx发包数量失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_tx_packet_interval(self, response):
        # 处理 "Tx发包间隔" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置Tx发包间隔成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置Tx发包间隔失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_tx_switch(self, response):
        # 处理 "Tx开关" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置TX开关成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置TX开关失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_rx_channel_config(self, response):
        # 处理 "Rx通道配置" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置RX通道成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置RX通道失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_rx_switch(self, response):
        # 处理 "Rx开关" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置RX开关成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置RX开关失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")


    def handle_get_rx_packet_count(self, response):
        # 处理 "获取Rx收包数量" 的逻辑
        print(f"handle_get_rx_packet_count={response}")
        # 提取收包数量
        packet_count = (response[0] << 24) | (response[1] << 16) | (response[2] << 8) | response[3]
        self.cb_cal_insert_log(f"收到Rx数据包数量: {packet_count}\n","green")


    def handle_ranging_mode_id_config(self, response):
        # 处理 "测距模式ID配置" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置测距模式ID成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置测距模式ID失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_read_ranging_mode_id(self, response):
        # 处理 "读取测距模式SYNC ID" 的逻辑
        result = (response[0] << 8) | response[1]
        self.cb_cal_insert_log(f"读取测距模式SYNC ID成功，ID为 {result}\n","green")

    def handle_ranging_mode_freq_config(self, response):
        # 处理 "测距模式频率配置" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置测距模式频率成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置测距模式频率失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_read_ranging_mode_freq(self, response):
        # 处理 "读取测距模式频率" 的逻辑
        result = int(response[0])
        # if not result == 0xff:
        #     self.cb_cal_insert_log(f"读取测距模式频率成功，频率为 {result}\n","green")
        # else:
        #     self.cb_cal_insert_log("读取测距模式频率失败\n","red")

        mapping = {0x10: 10, 0x20: 20, 0x30: 30, 0x50: 50}
        if result in mapping:
            frequency = mapping[result]
            self.cb_cal_insert_log(f"读取测距模式频率成功，频率为 {frequency}Hz\n", "green")
        else:
            self.cb_cal_insert_log("读取测距模式频率失败\n", "red")


    def handle_ranging_mode_tx_switch(self, response):
        # 处理 "测距模式Tx开关" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置测距模式Tx开关成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置测距模式Tx开关失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_ranging_mode_rx_channel_config(self, response):
        # 处理 "测距模式Rx通道配置" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置测距模式Rx通道成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置测距模式Rx通道失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_ranging_mode_rx_switch(self, response):
        # 处理 "测距模式Rx开关" 的逻辑
        result = int(response[0])
        if result == 0x00:
            self.cb_cal_insert_log("设置测距模式Rx开关成功\n","green")
        elif result == 0x01:
            self.cb_cal_insert_log("设置测距模式Rx开关失败\n","red")
        else:
            self.cb_cal_insert_log("失败：未知状态\n","red")

    def handle_get_ranging_mode_rx_data(self, response):
        # 处理 "获取测距模式Rx数据结果" 的逻辑
        dis = (response[0] << 8) | response[1]
        aoah = self.to_signed_16bit((response[2] << 8) | response[3])
        aoav = self.to_signed_16bit((response[4] << 8) | response[5])
        pdoa1 = self.to_signed_16bit((response[6] << 8) | response[7])
        pdoa2 = self.to_signed_16bit((response[8] << 8) | response[9])
        avg_rsl1 = self.to_signed_16bit((response[10] << 8) | response[11])
        avg_rsl2 = self.to_signed_16bit((response[12] << 8) | response[13])
        avg_rsl3 = self.to_signed_16bit((response[14] << 8) | response[15])

        self.cb_cal_insert_log(
            f"    测距结果: \n"
            f"    dis:      {dis} \n"
            f"    aoah:     {aoah} \n"
            f"    aoav:     {aoav} \n"
            f"    pdoa1:    {pdoa1} \n"
            f"    pdoa2:    {pdoa2} \n"
            f"    avg_rsl1: {avg_rsl1} \n"
            f"    avg_rsl2: {avg_rsl2} \n"
            f"    avg_rsl3: {avg_rsl3}\n",
            "green"
        )

    def to_signed_16bit(self, value):
        if value & 0x8000:  # 如果最高位是1
            return value - 0x10000  # 转换为负数
        else:
            return value

    def __del__(self):
        if self.serial_state_machine:
            self.serial_state_machine.stop()
    def close_ft_mode(self):
        if self.cb_ft_onoff:
            # 确保 self.cb_ft_onoff 处于关闭状态
            if self.cb_ft_onoff.instate(['selected']):  # 检查是否处于开启状态
                self.cb_ft_onoff.invoke()  # 调用 invoke() 方法将其关闭
        #self.cb_cal_insert_log(f"工厂模式已关闭\n")
    #用于日志输出接口
    def cb_cal_insert_log(self, message, color_tag='black', show_time=True):
        color_tags = color_tag
        self.cal_log_text.tag_configure(color_tags, foreground=color_tag, spacing1=5, spacing2=5, spacing3=5)
        if not message.endswith('\n'):
            message += '\n'
        if show_time:
            current_time = time.strftime('%H:%M:%S ', time.localtime(time.time()))
            formatted_message = "  "+current_time + message
        else:
            formatted_message = "      " + message
        
        self.cal_log_text.insert('end', formatted_message, (color_tags,))
        self.cal_log_text.see('end')  # 自动滚动到最新内容
        # 将日志消息写入文件
        self.logger.info(message)


def cb_show_toast(message):
    global g_cb_top_root
    x_position = g_cb_top_root.winfo_x()
    y_position = g_cb_top_root.winfo_y()
    position = (x_position, y_position, 'news')
    ToastNotification(
            "重要提示",
            message,
            duration=3000, # 显示时间3秒
            position=position
        ).show_toast()
