import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import serial.tools.list_ports
import configparser
import os
from datetime import datetime
from resizeable import ResizableDrawerApp, AnimatedGif
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
from random import choice
from ttkbootstrap.tooltip import ToolTip
import threading

from demo_board import Board_Functions,custom_show_toast
from cb_log_analysis import log_analysis_tochart
from cb_logger import CBLogger
# import customtkinter
from ttkbootstrap.scrolled import ScrolledText

CONFIG_FILE = "uart_config.ini"
WIN_CONFIG_FILE = "win_config.ini"
main_root = None
g_default_tap = 0
uart_app = None
init_config = None
g_is_maxed = 0

# customtkinter.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
# customtkinter.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class UARTTool_copy:
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
        self.serial_port = None
        self.send_timer = None
        self.create_widgets()
        self.logger = CBLogger.get_logger()
        #self.toggle_dark_mode()
        # self.update_ports()  # Dynamic port update, not needed for personal use

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
                "theme_back": "newtheme",
                "periodic_send": "False",
                "send_interval": "1000",
                "default_tap": "0",
            }
            with open(CONFIG_FILE, "w", encoding='utf-8') as configfile:
                config.write(configfile)
        else:
            config.read(CONFIG_FILE, encoding='utf-8')
        last_opened_port = config["DEFAULT"].get("last_opened_port", "None")  # Use default value None to prevent missing key
        self.theme_backup = config["DEFAULT"].get("theme_back", "newtheme")
        #self.init_theme(self.theme_backup)
        append_newline = config["DEFAULT"].getboolean("append_newline", False)
        self.default_directory = config["DEFAULT"].get("save_path", "./")
        self.append_newline_var.set(append_newline)
        g_default_tap = config["DEFAULT"].get("default_tap", "0")

        return config, last_opened_port

    def create_widgets(self):
        # Config area
        config_frame = ttkb.Frame(self.top_root)#top_root
        config_frame.grid(row=0, column=4, padx=10, pady=10, sticky='nsew')
        default_setting_width = 12

        self.port_label = ttkb.Label(config_frame, text="串口")
        self.port_label.pack(anchor='w', pady=2)
        self.port_combobox = ttkb.Combobox(config_frame, values=self.get_serial_ports(), width=default_setting_width, state='readonly')
        self.port_combobox.set(self.get_default_port())
        self.port_combobox.pack(anchor='w', pady=2)

        self.baudrate_label = ttkb.Label(config_frame, text="波特率")
        self.baudrate_label.pack(anchor='w', pady=2)
        self.baudrate_combobox = ttkb.Combobox(config_frame,
                                            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800",
                                                    "921600","1536000"], width=default_setting_width)
        self.baudrate_combobox.set(self.config["DEFAULT"].get("baudrate", "115200"))
        self.baudrate_combobox.pack(anchor='w', pady=2)
        ToolTip(
                self.baudrate_combobox,
                text="手动输入配置，需重新打开串口生效",
                bootstyle="primary-inverse",
            )
        
        # 数据位固定为8
        self.databits_label = ttkb.Label(config_frame, text="数据位: 8")
        self.databits_label.pack(anchor='w', pady=2)

        # self.databits_label = ttkb.Label(config_frame, text="数据位")
        # self.databits_label.pack(anchor='w', pady=2)
        # self.databits_combobox = ttkb.Combobox(config_frame, values=["5", "6", "7", "8"], width=default_setting_width, state='readonly')
        # self.databits_combobox.set(self.config["DEFAULT"].get("databits", "8"))
        # self.databits_combobox.pack(anchor='w', pady=2)

        self.stopbits_label = ttkb.Label(config_frame, text="停止位")
        self.stopbits_label.pack(anchor='w', pady=2)
        self.stopbits_combobox = ttkb.Combobox(config_frame, values=["1", "1.5", "2"], width=default_setting_width, state='readonly')
        self.stopbits_combobox.set(self.config["DEFAULT"].get("stopbits", "1"))
        self.stopbits_combobox.pack(anchor='w', pady=2)

        self.parity_label = ttkb.Label(config_frame, text="校验")
        self.parity_label.pack(anchor='w', pady=2)
        self.parity_combobox = ttkb.Combobox(config_frame, values=["None", "Even", "Odd", "Mark", "Space"], width=default_setting_width,
                                            state='readonly')
        self.parity_combobox = ttkb.Combobox(config_frame, values=["None", "Even", "Odd"], width=default_setting_width,
                                    state='readonly')
        self.parity_combobox.set(self.config["DEFAULT"].get("parity", "None"))
        self.parity_combobox.pack(anchor='w', pady=2)




        new_row_frame = ttkb.Frame(config_frame)
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



        port_bt_row_frame = ttkb.Frame(config_frame)
        port_bt_row_frame.pack(side='top', fill='x')
        self.open_button = ttkb.Button(port_bt_row_frame, text="打开串口", command=self.open_serial_port, bootstyle='outline')
        #self.open_button.pack(anchor='w', pady=2)
        self.open_button.pack(anchor='w', pady=5)
        self.close_button = ttkb.Button(port_bt_row_frame, text="关闭串口", command=self.close_serial_port, bootstyle='outline')
        #self.close_button.pack(anchor='w', pady=2)
        self.close_button.pack(anchor='w', pady=5)


        self.timestamp_var = tk.BooleanVar()
        self.timestamp_var.set(self.config["DEFAULT"].getboolean("show_timestamp", False))
        self.timestamp_checkbox = ttkb.Checkbutton(config_frame, text="显示时间戳", variable=self.timestamp_var,
                                                command=self.update_config)
        self.timestamp_checkbox.pack(side='top',anchor='w', pady=10)
        #self.timestamp_checkbox.invoke()
        # self.loading_gif = AnimatedGif(config_frame)
        # self.loading_gif.pack(pady=20,padx=0,expand=True,fill='both')

        # Receive and send area
        io_frame = ttkb.Frame(self.root)
        io_frame.grid(row=0, column=0, padx=0, pady=10, sticky='nsew')

        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        io_frame.grid_columnconfigure(0, weight=1)
        io_frame.grid_rowconfigure(0, weight=1)
        # io_frame.grid_rowconfigure(1, weight=1)

        # Receive area
        receive_frame = ttkb.Frame(io_frame)
        receive_frame.grid(row=0, column=0, padx=10, pady=0, sticky='nsew')

        receive_frame.grid_columnconfigure(0, weight=1)
        receive_frame.grid_columnconfigure(1, weight=1)
        receive_frame.grid_rowconfigure(1, weight=1)
        
        receive_label_row_frame = ttkb.Frame(receive_frame)
        receive_label_row_frame.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')
        self.receive_label = ttkb.Label(receive_label_row_frame, text="接收区域")
        self.receive_label.pack(padx=10, pady=5,side='left')

        # self.log_analysis_button = ttkb.Button(receive_label_row_frame, text="日志分析", command=self.save_data_and_analysis, bootstyle='outline',width=8)#bootstyle=INFO,
        # self.log_analysis_button.pack(padx=10, pady=5,side='left')
        
        self.save_button = ttkb.Button(receive_label_row_frame, text="清空接收区", command=self.clear_receive_data,bootstyle='outline')#bootstyle=INFO
        self.save_button.pack(padx=10, pady=5,side='left')

        self.save_button = ttkb.Button(receive_label_row_frame, text="保存接收内容", command=self.save_received_data,bootstyle='outline')#bootstyle=INFO, command=self.save_received_data,
        self.save_button.pack(padx=10, pady=5,side='left')

        self.hex_display_checkbox = ttkb.Checkbutton(receive_label_row_frame, text="HEX显示", variable=self.hex_display_var)#, variable=self.hex_display_var
        self.hex_display_checkbox.pack(padx=10, pady=5,side='left')

        custom_font = ("微软雅黑", 10)
        self.receive_text = ScrolledText(receive_frame, wrap=tk.WORD, font=custom_font,
                            highlightthickness=1,
                            autohide=True, bootstyle="primary")
                            
        self.receive_text.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky='nsew')


        # Send area
        send_frame = ttkb.Frame(io_frame)
        send_frame.grid(row=1, column=0, padx=10, pady=5, sticky='nsew')

        send_frame.grid_columnconfigure(0, weight=1)
        # send_frame.grid_rowconfigure(0, weight=1)

        send_lable_frame = ttkb.Frame(send_frame)
        send_lable_frame.grid(row=0, column=0, padx=0, pady=0, sticky='nsew')

        self.send_periodic_checkbox = ttkb.Checkbutton(send_lable_frame, text="定时发送", variable=self.periodic_send_var,command=self.toggle_periodic_send)#
        self.send_periodic_checkbox.pack(padx=10, pady=5,side='left')

        self.send_interval_entry = ttkb.Entry(send_lable_frame, textvariable=self.send_interval, width=5)
        self.send_interval_entry.pack(pady=5, padx=5,side='left')
        self.ms_label = ttkb.Label(send_lable_frame, text="ms")
        self.ms_label.pack(pady=5, padx=0,side='left')

        self.append_newline_checkbox = ttkb.Checkbutton(send_lable_frame, text="加回车换行", variable=self.append_newline_var, command=self.update_config)
        self.append_newline_checkbox.pack(pady=5, padx=10,side='left')

        self.hex_send_checkbox = ttkb.Checkbutton(send_lable_frame, text="HEX发送", command=self.toggle_hex_send,variable=self.hex_send_var)
        self.hex_send_checkbox.pack( pady=5, padx=5,side='left')


        self.send_text = tk.Text(send_frame, height=4, font=custom_font)
        self.send_text.grid(row=1, column=0, padx=10, pady=(0,5), sticky='ew')

        self.send_button = ttkb.Button(send_frame, text="发送", command=self.send_data, bootstyle=PRIMARY)
        self.send_button.grid(row=2, column=0, padx=10, pady=(10,0), sticky='ew')


        def config_cb_change(e):
            self.reopen_port()
        def config_cb_click(e):#用于打开软件后，动态拔插串口的时候，可以在选项卡中看到最新检测到的端口列表
            self.port_combobox['values'] = self.get_serial_ports()

        # 绑定鼠标左键点击事件
        self.port_combobox.bind("<Button-1>", config_cb_click)
        # 绑定选中值事件
        self.port_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        self.baudrate_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        # self.databits_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        self.stopbits_combobox.bind("<<ComboboxSelected>>", config_cb_change)
        self.parity_combobox.bind("<<ComboboxSelected>>", config_cb_change)

        #self.clear_receive_data()#初始化过程中会有一些数据，清空一下
        # Auto-refresh receive data
        self.root.after(100, self.receive_data)

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

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_data = f"{timestamp} "

            self.receive_text.insert(tk.END, formatted_data)
            self.red_tag = "green"
            self.receive_text.tag_configure(self.red_tag, foreground="green")
            self.receive_text.insert(tk.END, f"{self.serial_port.name}已打开 ", (self.red_tag,))
            self.receive_text.insert(tk.END, f"波特率：{baudrate} {databits} {int(stopbits)} {parity_str} {str_rcts} {str_dtr}\n")
            self.receive_text.see(tk.END)

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
            

            self.port_combobox.set(self.port_combobox.get().replace("（已打开）", ""))

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_data = f"{timestamp} "

            self.receive_text.insert(tk.END, formatted_data)
            self.red_tag = "red"
            self.receive_text.tag_configure(self.red_tag, foreground="red")
            self.receive_text.insert(tk.END, f"{self.serial_port.name}已关闭\n", (self.red_tag,))
            self.receive_text.see(tk.END)

            #messagebox.showinfo("信息", "串口已关闭")
        else:
            messagebox.showwarning("警告", "串口未打开")

    def receive_data(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                while self.serial_port.in_waiting:
                    encoding = self.config["DEFAULT"].get("encoding", "utf-8")
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if self.hex_display_var.get():
                        data = data.hex(' ').upper()
                    else:
                        data = data.decode(encoding, errors='replace')

                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3] if self.timestamp_var.get() else ""
                    received_label = "接收<< "
                    formatted_data = f"{timestamp} {received_label} {data}\n" if not data.endswith('\n') else f"{timestamp} {received_label} {data}"

                    self.receive_text.insert(tk.END, formatted_data)
                    self.receive_text.see(tk.END)

            except Exception as e:
                self.close_serial_port()
                messagebox.showerror("错误", f"请检查连接")
        self.root.after(100, self.receive_data)

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
            # self.save_send_history(self.data_str, self.send_data_prefix)
            print(f"成功Data sent: {data}")
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


    def clear_receive_data(self):
        # self.receive_text.configure(state='normal')
        self.receive_text.delete("1.0", tk.END)
        # self.receive_text.configure(state='disabled')

    def save_received_data(self):
        current_time = datetime.now().strftime("%H-%M-%S")
        default_filename = f"{current_time}.txt"
        
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