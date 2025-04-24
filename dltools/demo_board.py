"""
File: demo_board.py
Author: Roja.Zeng
Date: 2024
Company: ChipsBank
Version: 1.0.0
Description: 
用于完成升级功能和其他一些芯片功能测试的UI界面
启动程序：

程序启动时会初始化 Board_Functions 类，并加载配置文件以恢复上次的状态。
创建UI组件：

创建主界面的按钮和框架，包括“升级”和“工厂模式”等功能按钮。
启动端口检测线程：

使用多线程定期检查可用的串口，并更新UI显示当前找到的Chipsbank设备端口。
用户选择串口：

用户可以从下拉菜单中选择一个可用的串口，触发相应的回调函数进行处理。
用户选择功能页面：

用户点击不同的功能按钮切换页面，每个页面有不同的UI布局和功能。
固件升级流程：

如果用户选择了“升级”页面并选择了固件文件，点击“开始升级”后会禁用所有控件，启动固件升级线程。
升级过程中会显示进度条，并在完成后显示结果信息。
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
from cb_calibration import CB_Calibrate_Frame
from cb_logger import CBLogger
from firmware_updater import FirmwareUpdater
from tkinter import TclError
from cb_const import *

from firmware_updater import set_upgrading_state, is_firmware_upgrading

WIN_CONFIG_FILE = "win_config.ini"

g_top_root=None
g_log_txt=None
g_db_logger = CBLogger.get_logger()
g_cb_actived_ports = []
g_cb_baudrate_combobox = None

#通过查询版本好来判断串口上的设备是不是Chipsbank芯片
def check_port_usable(port_name, baudrate_to_test):
    try:
        # Try to open the port
        selected_baudrate= baudrate_to_test
        ser = serial.Serial(port_name, baudrate=selected_baudrate, timeout=1)
        ser.write_timeout = 1
        command = [0x5A, 0x01, 0x00, 0x00, 0x00] + [0x01, 0X5B]
        #test_data = b'\x5A\x01\x00\x01\x02\x01\x01\x06\x5B'  # Example test data
        command = bytes(command)
        
        
        try:
            ser.write(command)
        except serial.SerialTimeoutException as e:
            return False


        start_time = time.time()
    
        # 逐字节读取，直到找到包头
        while True:
            if time.time() - start_time > 3:  # 超时时间3秒
                # print(f"Timeout reading from port {port_name}")
                cb_show_log(f"Timeout reading from port {port_name}\n", 'red')
                ser.close()
                return False  # 读取超时，端口不可用
            start_byte = ser.read(1)
            if start_byte == b'\x5A':
                # 读取固定长度的前4字节（命令码 + 响应位 + 数据长度）
                header = ser.read(4)
                if len(header) < 4:
                    continue  # 包不完整，重新查找下一个5A
                # 解析数据长度
                data_length = header[3]
                
                # 读取剩余字节（数据 + 校验和）
                remaining_length = data_length + 1  # 数据长度 + 校验和
                data = ser.read(remaining_length)
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
                
                # 包合法，返回响应
                print(f"Check port Valid response: {response}")
                cb_show_log(f"{port_name} 可用\n", 'green')
                if response:
                    version_high = response[5]
                    version_low = response[6]
                    version_str = f"{version_high:02X}{version_low:02X}"
                    cb_show_log(f"当前单板固件版本号： {version_str}\n",'green')
                ser.close()
                return True
            
    except serial.SerialException as e:
        print(f"Error opening port {port_name}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error with port {port_name}: {e}")
        return False





class Board_Functions:
    func_buttons = {}  # 用于存放按键
    bt_frames = {}  # 用于存放frame，避免重复创建

    def __init__(self, parent, top_root):
        global g_top_root, g_cb_actived_ports
        self.top_root = top_root
        g_top_root = top_root

        self.parent = parent
        self.row_num = 0
        self.last_available_ports = []
        self.cb_actived_ports = []
        self.exception_ports = []  # 初始化异常端口列表
        self.current_page = "升级"
        self.config = configparser.ConfigParser()
        self.config_file = WIN_CONFIG_FILE
        self.last_available_bt_name = "升级" #默认显示升级界面
        self.load_exception_ports() # 程序启动时加载异常端口列表
        self.cb_device_port_label = None  # 用于显示已找到的chpisbank设备端口
        self.ranging_ui = None
        self.is_thread_running = False
        self.thread = None
        self.log_need = True
        self.check_port_started = False
        # 预设的按键名称及其对应的frame类型

        # self.enable_uart_cb = None

    def init_board_functions(self):
        self.funs_bt_group = ttkb.Frame(master=self.parent)
        self.funs_bt_group.pack(fill=tk.X, side=tk.TOP,pady=(10,0), padx=0)
        ttkb.Separator(self.funs_bt_group, bootstyle='light').pack(side='bottom', fill=tk.X, padx=5, pady=(0,0))
        ttkb.Separator(self.funs_bt_group, bootstyle='light').pack(side='bottom', fill=tk.X, padx=5, pady=(0,0))
        # 使用grid布局管理器的frame容器
        self.frame_container = ttkb.Frame(self.parent)
        self.frame_container.pack(side=tk.TOP, fill=tk.BOTH, pady=0,expand=True)
        button_configs = {
            "升级": "success",
            "工厂模式": "info",
        }
        # 遍历预设的按键配置来创建按键，并绑定事件
        for name, style in button_configs.items():
            cb = ttkb.Button(self.funs_bt_group, text=name, bootstyle='outline', command=lambda n=name: self.open_frame(n), takefocus=False)
            cb.pack(side=tk.LEFT,  padx=5, pady=5, fill=tk.X)
            cb.config(width=12)  # 设置按键的最小宽度为10
            self.func_buttons[name] = cb

            # 创建frame，并使用grid布局使它们重叠
            frame = ttkb.Frame(self.frame_container, padding=0)
            frame.grid(row=0, column=0, sticky="nsew")

            
            self.bt_frames[name] = frame


            if name == "升级":
                #frame.configure(borderwidth=0.5, relief=tk.SUNKEN)
                frame.grid(row=0, column=0, sticky="nsew",padx=5,pady=5)
                self.label = ttkb.Label(frame, text='正在检测端口', padding=5)
                self.label.grid(row=self.row_num, column=0, sticky="ew", padx=70)
                self.row_num += 1
                self.loading_gif = AnimatedGif(frame)
                self.loading_gif.grid(row=self.row_num-1, column=0, sticky="w", padx=10)
                self.loading_gif.resize_image(50, 50)
                self.create_exception_ports_button(parent=frame)
                
                pass
            elif name == "工厂模式":
                # self.label = ttkb.Label(frame, text=f" 校准  校准 校准 ", padding=5)
                # self.label.grid(row=self.row_num, column=0, sticky="ew", padx=70)
                self.Cal_frame = CB_Calibrate_Frame(frame, self.top_root)
            # 确保frame可以扩展填充其父容器
            frame.grid(sticky="nsew")
            frame.master.grid_rowconfigure(0, weight=1)
            frame.master.grid_columnconfigure(0, weight=1)
            # 默认隐藏所有frame
            frame.grid_remove()
        self.cb_device_port_label = ttkb.Label(self.funs_bt_group, text="正在查找Chipsbank设备……", padding=5)
        self.cb_device_port_label.pack(side=tk.LEFT, padx=5, fill=tk.X)


        #创建一个combobox，用于选择串口
        self.enabled_uart_cb = ttkb.Combobox(self.funs_bt_group, values=g_cb_actived_ports, state='readonly', width=10)
        self.enabled_uart_cb.pack(side=tk.LEFT, padx=5, fill=tk.X)

        if self.last_available_bt_name == "升级":
            self.wiget_hidden()
        else:
            self.wiget_show()
        # 如果 g_cb_actived_ports 不为空，则设置默认值为第一个值
        if g_cb_actived_ports:
            self.enabled_uart_cb.set(g_cb_actived_ports[0])
            self.enabled_uart_combobox_select()#手动执行回调函数
        self.enabled_uart_cb.bind("<<ComboboxSelected>>", self.enabled_uart_combobox_select)


        # 显示上一次激活的按键对应frame
        first_frame_name = self.last_available_bt_name
        # self.check_ports_async()

        # 判断指定名字的 frame 是否存在
        if first_frame_name in self.bt_frames:
            self.bt_frames[first_frame_name].grid()
            self.func_buttons[first_frame_name].config(bootstyle = 'primary')  # 设置当前按钮颜色
            self.current_page = first_frame_name
            if not first_frame_name == "工厂模式":
                self.close_ft_mode()
        else:
            # 使用默认的 frame 名字
            default_frame_name = "升级"  # 替换为你的默认 frame 名字
            if default_frame_name in self.bt_frames:
                self.bt_frames[default_frame_name].grid()
                self.func_buttons[default_frame_name].config(bootstyle = 'primary')  # 设置当前按钮颜色
                self.current_page = default_frame_name
                if not default_frame_name == "工厂模式":
                    self.close_ft_mode()
            else:
                print(f"Error: Neither {first_frame_name} nor {default_frame_name} exists in bt_frames.")
        # 设置frame容器的行和列权重
        self.frame_container.grid_rowconfigure(0, weight=1)
        self.frame_container.grid_columnconfigure(0, weight=1)

    def start_check_ports(self):
        if not self.check_port_started:
            self.check_ports_async()
            self.init_board_functions()
            self.check_port_started = True

    def wiget_hidden(self):
        self.cb_device_port_label.pack_forget()
        self.enabled_uart_cb.pack_forget()

    def wiget_show(self):
        self.cb_device_port_label.pack(side=tk.LEFT, padx=5, fill=tk.X)
        self.enabled_uart_cb.pack(side=tk.LEFT, padx=5, fill=tk.X)

    # 定义回调函数
    def enabled_uart_combobox_select(self, event=None):
        global g_cb_selected_actived_ports
        g_cb_selected_actived_ports = self.enabled_uart_cb.get()
        self.close_all()
        #print(f"用户选择了串口: {g_cb_selected_actived_ports}")

    def close_all(self):
        if self.ranging_ui:
            self.ranging_ui.ranging_setting_frame.stop_ranging()
            self.send_rev.close_send_receive()
            self.close_ft_mode()

#注意，如果在做下载动作的时候，应该屏蔽禁止一些按键操作和UI更新，以免出现错误
    def update_firmware_ui(self, available_ports, cb_actived_ports):
        #print("update_firmware_ui")
        global g_log_txt
        frame = self.bt_frames["升级"]
        
        # 检查log_frame是否已经存在
        log_frame_exists = hasattr(self, 'log_frame')
        
        if log_frame_exists:
            # 先暂时移除log_frame以避免被销毁
            self.log_frame.grid_remove()
            self.up_settings_frame.grid_remove()
        else:
            # 如果log_frame不存在，先创建它，但不放置在界面上（稍后根据需要放置）
            self.log_frame = ttkb.Frame(frame)
            # self.create_exception_ports_button()
            self.log_txt = ScrolledText(master=self.log_frame, autohide=True, undo=True)
            self.log_txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            g_log_txt = self.log_txt
        # 清除frame中的所有子组件，除了log_frame
        for widget in frame.winfo_children():
            if widget != self.log_frame and widget !=self.up_settings_frame :  # 排除log_frame
                widget.destroy()
        
        # 重置row_num
        self.row_num = 1
        #self.enabled_uart_cb['values'] = cb_actived_ports
        if not available_ports:
            # available_ports 为空的处理逻辑
            self.loading_gif = AnimatedGif(frame)
            self.loading_gif.grid(row=self.row_num-1, column=0, sticky="w", padx=10)
            self.loading_gif.resize_image(50, 50)

            self.label = ttkb.Label(frame, text='正在查找端口，请检查是否已插入设备', padding=5)
            self.label.grid(row=self.row_num-1, column=0, sticky="w", padx=70)
            if self.log_need:
                cb_show_log("没有找到可用的串口。\n", 'red')
            self.enabled_uart_cb.set('无')
            self.enabled_uart_combobox_select()#手动执行回调函数
        else:
            # 更新 enabled_uart_cb 的值
            self.up_settings_frame.grid(row=self.row_num, column=0, sticky="w", padx=10)
            self.row_num += 1
            if cb_actived_ports:
                self.enabled_uart_cb.set(cb_actived_ports[0])
                self.enabled_uart_combobox_select()#手动执行回调函数
            # 遍历可用的串口
            for index, port in enumerate(available_ports, start=1):
                # firmware_selector = FirmwareSelector(frame, index, port,self.up_baudrate_combobox,self.up_version_entry, self.loop_upgrade_var)
                firmware_selector = FirmwareSelector(frame, index, port,self.up_baudrate_combobox,None, self.loop_upgrade_var)
                firmware_selector.frame.grid(row=self.row_num, column=0, sticky="nsew", pady=5)
                self.row_num += 1
                # 动态为self.bt_frames["升级"]添加属性
                setattr(self.bt_frames["升级"], f'firmware_selector_{index:02}', firmware_selector)
                # if port in cb_actived_ports:#放到别的地方去检测端口的可用性
                #     # 更新状态图标
                #     firmware_selector.update_status_icon('./icon/status_g.png')
                #     cb_show_log(f"{port} Chipsbank 板子已找到\n", 'green')
            # # 更新第一个固件选择器的状态图标（如果存在）
            # if hasattr(self.bt_frames["升级"], 'firmware_selector_01'):
            #     self.bt_frames["升级"].firmware_selector_01.update_status_icon('./icon/status_g.png')

        if log_frame_exists:
            # 如果log_frame已经存在，重新放置它
            self.log_frame.grid(row=self.row_num, column=0, sticky="nsew", pady=5)
            
        else:
            # 如果log_frame不存在，创建它
            self.log_frame = ttkb.Frame(frame)
            self.log_frame.grid(row=self.row_num, column=0, sticky="nsew", pady=5)
            #self.create_exception_ports_button() #不删除,当程序用于通用串口的时候，需要这个按钮
            self.log_txt = ScrolledText(master=self.log_frame, autohide=True, undo=True)
            self.log_txt.pack(fill=tk.BOTH, expand=True, padx=(10,5), pady=5)
            g_log_txt = self.log_txt
        # frame.grid_rowconfigure(self.row_num-1, weight=1) 
        # frame.grid_rowconfigure(self.row_num, weight=11-self.row_num)  # log Frame占据70%的高度比重
        total_weight = 100  # 总权重
        row_weight = 5  # 每行的权重
        # 配置self.row_num之前的行权重各占百分之十
        for i in range(self.row_num):
            frame.grid_rowconfigure(i, weight=row_weight)
        # 剩下的权重给self.row_num
        remaining_weight = total_weight - (self.row_num * row_weight)
        frame.grid_rowconfigure(self.row_num, weight=remaining_weight)
        frame.grid_columnconfigure(0, weight=1)

    def create_exception_ports_button(self,parent):
    # 创建一个新的 Frame 来存放控件
        global g_cb_baudrate_combobox
        self.up_settings_frame = ttkb.Frame(parent)
        self.up_settings_frame.grid(row=self.row_num, column=0, sticky="w", padx=10)
        
        # 创建波特率设置选择框
        self.up_baudrate_label = ttkb.Label(self.up_settings_frame, text="选择波特率:")
        self.up_baudrate_label.grid(row=0, column=0, pady=(0,0), padx=(5,5), sticky='w')
        self.up_baudrate_combobox = ttkb.Combobox(self.up_settings_frame, values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", 
                                                                                  "921600"], width=10)
        self.up_baudrate_combobox.set("921600")
        # self.up_baudrate_combobox.set("460800")
        self.up_baudrate_combobox.grid(row=0, column=1, pady=(0,0), padx=10, sticky='w')
        self.up_baudrate_combobox.bind("<<ComboboxSelected>>", self.on_baudrate_selected)
        self.selected_baudrate ="921600"
        g_cb_baudrate_combobox = self.up_baudrate_combobox
        # 创建版本号输入框
        # self.up_version_label = ttkb.Label(self.up_settings_frame, text="输入版本号:")
        # self.up_version_label.grid(row=0, column=2, pady=(0,0), padx=(20,5), sticky='w')
        # self.up_version_entry = ttkb.Entry(self.up_settings_frame, width=6, justify='center')
        # self.up_version_entry.insert(0, "0501")  # 设置默认值为0101
        # self.up_version_entry.grid(row=0, column=3, pady=(0,0), padx=10, sticky='w')
        # 创建勾选框用于决定是否循环升级
        self.loop_upgrade_var = tk.BooleanVar()
        self.loop_upgrade_checkbutton = ttkb.Checkbutton(self.up_settings_frame, text="启用循环升级", variable=self.loop_upgrade_var)
        self.loop_upgrade_checkbutton.grid(row=0, column=4, pady=(0,0), padx=10, sticky='w')

    def on_baudrate_selected(self, event):
        # 获取选择的波特率值
        self.selected_baudrate = self.up_baudrate_combobox.get()
        print(f"Selected baudrate: {self.selected_baudrate}")
        # 弹出选择框给用户选择需要跳过检测的端口
    def open_exception_ports_dialog(self):
        top = tk.Toplevel(self.log_frame, borderwidth=1, relief='ridge')
        top.title("选择无需检测端口")
        # top.overrideredirect(True)  # 去掉最小化和最大化按钮

        # 获取主窗口的位置和尺寸
        parent_x = self.top_root.winfo_rootx()
        parent_y = self.top_root.winfo_rooty()
        parent_width = self.top_root.winfo_width()
        parent_height = self.top_root.winfo_height()

        # 弹出框的预期尺寸
        dialog_width = 300
        dialog_height = 200

        # 计算弹出框居中于父窗口的位置
        x = parent_x + (parent_width / 2) - (dialog_width / 2)
        y = parent_y + (parent_height / 2) - (dialog_height / 2)

        # 设置弹出框的位置和最小尺寸
        top.geometry("+%d+%d" % ( x, y))
        top.minsize(dialog_width, dialog_height)
        # 用于存储复选框变量的临时字典
        temp_exception_ports_var = {}
        all_ports = self.get_serial_ports()  # 假设这是获取所有串行端口的函数
        label = ttkb.Label(top, text=f"{Emoji.get('BLACK QUESTION MARK ORNAMENT')} 请选择需要跳过检测的端口", padding=5, font=("微软雅黑", 10, "bold"))
        # print(f"{Emoji.get('BLACK QUESTION MARK ORNAMENT')}请选择需要跳过检测的端口")
        label.pack(anchor='center', padx=10, pady=10)
        
        frame = tk.Frame(top)  # 创建一个框架用于放置复选框，以实现一行显示两个 ,borderwidth=1,relief='groove'
        frame.pack(fill='both', anchor='center', padx=10)  # 填充整个x轴方向，并设置内边距

        for i, port in enumerate(all_ports):
            # 检查端口是否应该默认选中
            is_selected = port in self.exception_ports
            var = tk.BooleanVar(value=is_selected)  # 根据端口是否在self.exception_ports中来设置默认值
            chk = ttkb.Checkbutton(frame, text=port, variable=var)
            
            # 根据索引决定放在左边还是右边
            if i % 2 == 0:
                chk.grid(row=i//2, column=0, sticky='w', padx=(50, 10), pady=10)  # 偶数索引，放在左边
            else:
                chk.grid(row=i//2, column=1, sticky='w', padx=(50, 10), pady=10)  # 奇数索引，放在右边
            
            temp_exception_ports_var[port] = var  # 存储变量以便后续使用
        sp = ttkb.Separator(top).pack(fill='x', padx=30, pady=(15,0))
        # 确认按钮，点击后更新self.exception_ports_var并关闭窗口
        confirm_button = ttkb.Button(top, text="确认", command=lambda: self.update_exception_ports_var(temp_exception_ports_var, top), bootstyle='outline')
        confirm_button.pack(side='left', pady=15, padx=(50, 10))
        confirm_button.config(width=8)
        # 取消按钮，点击后不做任何操作，直接关闭窗口
        cancel_button = ttkb.Button(top, text="取消", command=top.destroy, bootstyle='outline')
        cancel_button.pack(side='right', pady=15, padx=(10, 50))
        cancel_button.config(width=8)

    def update_exception_ports_var(self, temp_vars, dialog):
        # 从复选框变量中提取被选中的端口
        selected_ports = [port for port, var in temp_vars.items() if var.get() == True]

        # 检查是否有之前选中现在未选中的端口
        deselected_ports = [port for port in self.exception_ports if port not in selected_ports]
        if deselected_ports:
            # 如果有端口之前被选中，现在未被选中，说明用户进行了反选操作
            cb_show_log(f"{deselected_ports}已被移出异常端口列表\n", 'green')

        # 检查是否有之前未选中现在选中的端口
        newly_selected_ports = [port for port in selected_ports if port not in self.exception_ports]
        if newly_selected_ports:
            # 如果有端口之前未被选中，现在被选中，说明用户进行了选择操作
            cb_show_log(f"{newly_selected_ports}已被添加到异常端口列表\n", 'red')

        # 更新异常端口列表
        self.exception_ports = selected_ports
        self.save_exception_ports()
        dialog.destroy()

    # def get_serial_ports(self):
    #     ports = serial.tools.list_ports.comports()
    #     port_list = [port.device for port in ports]
    #     print(f"找到的端口: {port_list}")
    #     return [port.device for port in ports]
    def get_serial_ports(self):
        target_vid = 0x1A86
        target_pid = 0x55DB
        ports = serial.tools.list_ports.comports()
        port_list = []
        for port in ports:
            port_info = {
                "device": port.device,
                "name": port.name,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": port.serial_number,
                "location": port.location,
                "manufacturer": port.manufacturer,
                "product": port.product,
                "interface": port.interface
            }
            #如果只识别demo板的端口就启用if
            # if port.vid == target_vid and port.pid == target_pid:
            #     port_list.append(port_info)
            port_list.append(port_info)#正式发布用这个

        return [port["device"] for port in port_list]
    


    def check_ports_async(self):
        print("check_ports_async")
        if self.is_thread_running:
            print("线程已经在运行中，避免重复启动")
            return
        self.is_thread_running = True
        def run():
            last_available_ports = self.get_serial_ports()  # 初始化为当前可用端口列表
            # 启动时强制触发一次更新
            self.update_ports_init(last_available_ports)
            
            while self.is_thread_running:  # 持续运行
            # while self.is_thread_running and not is_firmware_upgrading():  # 只在未升级时循环检测串口
                # print(is_firmware_upgrading())
                if is_firmware_upgrading():
                    # print("正在升级状态，停止检测端口")
                    time.sleep(1)  # 等待升级完成
                else:
                    # print("不在升级状态")
                    available_ports = self.get_serial_ports()

                    cb_actived_ports = available_ports
                    format_text = f"已找到的Chipsbank设备端口" if cb_actived_ports else "没有找到Chipsbank设备"
                    global g_cb_actived_ports
                    g_cb_actived_ports = cb_actived_ports

                    try:
                        if self.enabled_uart_cb and self.enabled_uart_cb.winfo_exists():
                            self.enabled_uart_cb['values'] = g_cb_actived_ports
                    except (AttributeError, TclError):
                        # 控件可能已经被销毁，处理异常
                        print("控件可能已经被销毁")
                        return

                    if self.cb_device_port_label:
                        self.cb_device_port_label.config(text=format_text)
                    self.log_need = False

                    # 检测端口插入和移除
                    inserted_ports = set(available_ports) - set(last_available_ports)
                    removed_ports = set(last_available_ports) - set(available_ports)
                    self.last_available_ports = available_ports
                    self.cb_actived_ports = cb_actived_ports
                    
                    if inserted_ports or removed_ports:
                        format_text = f"已找到的Chipsbank设备端口" if cb_actived_ports else "没有找到Chipsbank设备"
                        if self.cb_device_port_label:
                            self.cb_device_port_label.config(text=format_text)
                        self.log_need = True  # 端口发生变化的时候要打印一下
                        # 在主线程中更新UI
                        self.top_root.after(0, lambda: self.update_ui_with_ports(available_ports, cb_actived_ports))
                        # 处理端口插入和移除
                        if inserted_ports:
                            g_db_logger.info(f"端口插入: {inserted_ports}")
                            
                        if removed_ports:
                            g_db_logger.info(f"端口移除: {removed_ports}")
                            
                            if self.current_page == "工厂模式":
                                self.close_ft_mode()
                        
                        if g_cb_actived_ports:
                            self.enabled_uart_cb.set(g_cb_actived_ports[0])
                        else:
                            self.enabled_uart_cb.set('无')
                        self.enabled_uart_combobox_select()#手动执行回调函数
                    last_available_ports = available_ports
                    time.sleep(1)  # 每秒检查一次

        self.thread = threading.Thread(target=run)
        self.thread.daemon = True
        self.thread.start()

    def stop_check_ports(self):
        self.is_thread_running = False
        if self.thread:
            self.thread.join(timeout=5)

    def update_ports_init(self, ports):
        cb_actived_ports = ports
        format_text = f"已找到的Chipsbank设备端口：{cb_actived_ports}" if cb_actived_ports else "没有找到Chipsbank设备"
        global g_cb_actived_ports
        g_cb_actived_ports = cb_actived_ports
        if self.cb_device_port_label:
            self.cb_device_port_label.config(text=format_text)
        self.log_need = True  # 端口发生变化的时候要打印一下
        # 在主线程中更新UI
        self.top_root.after(0, lambda: self.update_ui_with_ports(ports, cb_actived_ports))

    def load_exception_ports(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
            # 从配置文件读取异常端口字符串，并使用逗号分隔符将其分割成列表
            exception_ports_str = self.config["DEFAULT"].get("port", "")
            if exception_ports_str:
                self.exception_ports = exception_ports_str.split(",")
            else:
                self.exception_ports = []  # 确保是空列表而不是空字符串
            self.last_available_bt_name = self.config["DEFAULT"].get("active_bt", "升级")  # 读取上次活动的按键名称
    
    def save_exception_ports(self):
        self.config.read(self.config_file, encoding='utf-8')
        if not hasattr(self, 'exception_ports') or not self.exception_ports:
            return  # 如果 exception_ports 不存在或为空，则不执行任何操作

        exception_ports_str = ",".join(self.exception_ports)  # 将列表转换为逗号分隔的字符串
        self.config["DEFAULT"]["port"] = exception_ports_str  # 保存字符串到配置文件

        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

    def save_last_active_bt(self, active_bt_name):
        self.last_available_bt_name = active_bt_name
        self.config.read(self.config_file, encoding='utf-8')
        self.config["DEFAULT"]["active_bt"] = active_bt_name  # 保存活动的按键名称到配置文件

        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

    def update_ui_with_ports(self, available_ports, cb_actived_ports):
        if self.current_page == "升级":
            try:
                self.update_firmware_ui(available_ports, cb_actived_ports)
            except Exception as e:
                print(f"更新UI时发生错误: {e}")

    def open_frame(self, name):
        if self.current_page == name:
            return#已经在按钮所在页面，不处理本次点击
        self.current_page = name

        # 隐藏所有frame
        for frame in self.bt_frames.values():
            frame.grid_remove()
        # 显示对应的frame
        self.bt_frames[name].grid()
        self.top_root.title(f"ChipsBank UWB {name}")
        self.save_last_active_bt(name)
         # 改变按键颜色
        for button in self.func_buttons.values():
            button.config(bootstyle = 'outline')  # 重置所有按钮颜色
        self.func_buttons[name].config(bootstyle = 'primary')  # 设置当前按钮颜色
        if not name == "工厂模式":
            self.close_ft_mode()
        if not name == "升级":
            self.wiget_show()
        if name == "升级":
            #如果在别的页面上，拔掉设备，再切换到升级页面，ui不会更新
            self.wiget_hidden()
            self.update_firmware_ui(self.last_available_ports, self.cb_actived_ports)
    def close_ft_mode(self):
        # 关闭工厂模式
        self.Cal_frame.close_ft_mode()


class FirmwareSelector:
    def __init__(self, master, selector_num,frame_text,baudrate_widget,version_widget, loop_upgrade_var=None):
        self.master = master
        self.loc_baudrate_widget = baudrate_widget
        self.loc_version_widget = version_widget
        self.loop_upgrade_var = loop_upgrade_var
        self.frame = ttkb.Frame(self.master)

        self.is_checking = False

        self.status_frame = ttkb.Frame(self.frame)
        self.status_frame.grid(row=0, column=0, sticky="w", padx=10)

        self.label = ttkb.Label(self.status_frame, text=frame_text)
        self.label.grid(row=0, column=0, sticky="w", padx=(35,5))#端口图标和端口号的间距
        self.myport = frame_text
        # 初始化状态图标
        self.status_icon_path = str(img_parent_path)+'./icon/status_none.png'  # 初始图标路径
        self.status_icon_image = tk.PhotoImage(file=self.status_icon_path).subsample(12, 12)
        self.status_icon_label = tk.Label(self.frame, text=frame_text, image=self.status_icon_image)
        self.status_icon_label.grid(row=0, column=0, sticky="w",padx=(5,0))
        self.status_icon_label.image = self.status_icon_image  # 保持对初始图像的引用


        self.check_port_button = ttkb.Button(
            self.status_frame, 
            text="检测端口", 
            command=lambda: self.check_port(),
            bootstyle='outline',
            takefocus=False
        )
        self.check_port_button.grid(row=0, column=1, padx=5, pady=2)
        self.check_port_button.config(width=8) # 设置按键的最小宽度为10

        self.update_pb = ttkb.Progressbar(
            master=self.status_frame,
            value=0,
            length = 450,
            bootstyle='success',#('success', 'striped')
            orient='horizontal'
        )
        self.update_pb.grid(row=0, column=2, sticky="w", padx=(10,0))
        self.update_pb.grid_remove()  # 隐藏进度条
        self.update_pb["maximum"] = 100
        self.update_pb_percent = ttkb.Label(self.status_frame, text="0%")
        self.update_pb_percent.grid(row=0, column=3, sticky="w", padx=(10,0))
        self.update_pb_percent.grid_remove()  # 隐藏进度百分比
        #self.update_pb.start()

        self.selected_file_path = tk.StringVar(self.master, value="")
        self.file_path_entry = ttkb.Entry(self.frame, textvariable=self.selected_file_path, width=90)
        self.file_path_entry.grid(row=1, column=0, sticky="w", padx=10, pady=2)
        #self.select_file_button = ttkb.Button(self.frame, text="选择文件", command=self.select_file, bootstyle='outline')


        self.select_file_button = ttkb.Button(
            master=self.frame, 
            text="选择文件", 
            bootstyle='outline',
            takefocus=False,
            command=self.select_file
        )
        self.select_file_button.config(width=10) # 设置按键的最小宽度为10
        self.select_file_button.grid(row=1, column=1, padx=5, pady=2)
        self.update_button = ttkb.Button(
            self.frame, 
            text="开始升级",
            command=lambda: self.do_update_firmware(self.myport), 
            bootstyle='outline',
            takefocus=False
        )
        self.update_button.grid(row=1, column=2, padx=5, pady=2)
        self.update_button.config(width=10) # 设置按键的最小宽度为10

        # self.select_file_button = ttkb.Button(
        #     master=self.frame,
        #     text="清空日志",
        #     command=self.clear_log,
        #     bootstyle='outline-danger',
        # )
        # self.select_file_button.config(width=10) # 设置按键的最小宽度为10
        # self.select_file_button.grid(row=2, column=7, padx=700, pady=2)

        self.config = configparser.ConfigParser()
        self.config_file = WIN_CONFIG_FILE
        self.load_default_path()

    # def clear_log(self):
    #     global g_log_txt
    #     if g_log_txt:
    #         g_log_txt.delete('1.0', tk.END)

    def check_port(self):
        if self.is_checking:
            cb_show_log("检测正在进行中，请稍候...\n", 'black')
            return

        self.is_checking = True
        threading.Thread(target=self._check_port_thread).start()

    def _check_port_thread(self):
        cb_show_log(f"\n正在检测端口是否可用......\n")
        port = self.myport
        baudrate = self.loc_baudrate_widget.get()
        # 检测端口是否可用
        if check_port_usable(port, baudrate):
            self.update_status_icon(str(img_parent_path)+'./icon/status_g.png')
            # cb_show_log(f"{port} 可用\n", 'green')
        else:
            self.update_status_icon(str(img_parent_path)+'./icon/status_r.png')
            cb_show_log(f"{port} 不可用\n", 'red')
        self.is_checking = False

    def update_status_icon(self, new_icon_path):
        """更新状态图标"""
        new_icon_image = tk.PhotoImage(file=new_icon_path).subsample(12, 12)
        self.status_icon_label.configure(image=new_icon_image)
        self.status_icon_label.image = new_icon_image  # 更新引用，防止图像被垃圾回收

    def load_default_path(self):
        # self.config = configparser.ConfigParser()
        # 读取配置文件中的默认路径
        if os.path.exists(self.config_file):
            # print(f"配置文件存在，读取默认路径")
            self.config.read(self.config_file, encoding='utf-8')
            # default_path = self.config.get('DEFAULT', 'path', fallback=f"{os.getcwd()}")
            default_path = self.config["DEFAULT"].get("path", f"{os.getcwd()}")
            self.selected_file_path.set(default_path)
        else:
            # 如果配置文件不存在，使用一个默认路径
            self.selected_file_path.set(f"{os.getcwd()}")

    def select_file(self):
        # 使用配置文件中的路径作为初始目录
        file_path = filedialog.askopenfilename(initialdir=self.selected_file_path.get())
        if file_path:
            self.selected_file_path.set(file_path)
            self.update_button.config(text="开始升级")
            # 更新配置文件中的路径
            self.update_config_file(file_path)

    def do_update_firmware(self, port):
        print(f"Updating firmware on port: {port}")
        # 先检测一下文件存在或者有效性
        file_path_value = self.selected_file_path.get()
        if not os.path.exists(file_path_value):
            custom_show_toast("选择的文件或路径不存在")
            return
        if not file_path_value.endswith('.bin'):
            custom_show_toast("文件格式错误，需要一个.bin文件")
            return
        # 进行固件更新的逻辑
        self.update_button.config(text="升级中...")
        self.update_pb.grid()
        self.update_pb_percent.grid()
        # self.update_pb.start()
        self.disable_all_controls() 
        # 创建并启动一个线程来处理固件更新
        updater = FirmwareUpdater(
            self,
            port,
            file_path_value,
            self.update_pb,
            self.update_pb_percent,
            self.update_button,
            self.frame,
            self.label,
            cb_show_log,
            custom_show_toast,
            self.enable_all_controls,
            self.disable_all_controls
        )
        update_thread = threading.Thread(target=updater.update_firmware_thread)
        update_thread.start()
    # # 创建并启动一个线程来处理固件更新
    #     update_thread = threading.Thread(target=self.update_firmware_thread(port))
    #     update_thread.start()
    
    def update_firmware_thread(self):

        try:
            # 假设这是更新固件的函数，需要替换为实际的更新逻辑
            max_value = 100
            for i in range(1, max_value+1, 1):
                self.update_pb["value"] = i
                time.sleep(0.1)  # 模拟固件更新过程
                self.frame.update_idletasks()  # 更新UI
                self.update_pb_percent.config(text=f"{i}%")
                if self.update_pb['value'] >= max_value:
                    break  # 当进度条达到最大值时跳出循环
            self.update_button.config(text="开始升级")
        except Exception as e:
            custom_show_toast("升级失败，错误码0x0001")
        finally:
            
            self.update_pb.stop()  # 停止进度条
            self.update_pb["value"] = 100
            cb_show_log(f"{self.label.cget('text')}升级完成\n", 'green')
            #self.cb_show_log(f"{self.label.cget('text')}升级完成\n", 'red')#测试一下颜色
            self.enable_all_controls()  # 假设这是启用所有控件的函数

    def disable_all_controls(self):
        global g_top_root
        self.select_file_button.config(state="disabled")
        self.update_button.config(state="disabled")
        g_top_root.can_close_window = False
        # g_self.nnb.config(state="disabled")
        #self.nnb.unbind("<<NotebookTabChanged>>")

    def enable_all_controls(self):
        global g_top_root
        self.select_file_button.config(state="normal")
        self.update_button.config(state="normal")
        g_top_root.can_close_window = True
        self.update_button.config(text="开始升级")

    def update_config_file(self, file_path):
        # 将新的路径保存到配置文件
        self.config.read(self.config_file, encoding='utf-8')
        self.config["DEFAULT"]["path"] = str(file_path)
        with open(self.config_file, 'w', encoding='utf-8') as configfile:
            self.config.write(configfile)

def cb_show_log( message, color_tag='black'):
    global g_log_txt
    color_tags = color_tag
    if g_log_txt:
        g_log_txt.tag_configure(color_tags, foreground=color_tag)
        # g_log_txt.tag_configure(color_tags,foreground=color_tag,font=('微软雅黑', 10))
        g_log_txt.insert('end', message, (color_tags,))
        g_log_txt.see('end')
    g_db_logger.info(message)
#toast固定显示在窗口左上角        
def custom_show_toast(message):
    global g_top_root
    x_position = g_top_root.winfo_x()
    y_position = g_top_root.winfo_y()
    position = (x_position, y_position, 'news')
    ToastNotification(
            "错误提示",
            message,
            duration=3000, # 显示时间3秒
            position=position
        ).show_toast()

