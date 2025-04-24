"""
UARTTool_Extension class provides an extension window for UARTTool with a tabbed interface.
Attributes:
    root (tk.Tk): The main Tkinter window.
    parent (tk.Widget): The parent widget for the extension.
    parent_class (object): The parent class instance.
    extension_created (bool): Flag to check if the extension has been created.
    tab_frames (dict): Dictionary to store frames for each tab.
    bg_frame (ttkb.Frame): Background frame for the extension.
    toggle_button (ttkb.Button): Button to toggle the visibility of the extension.
    labels_entries (list): List to store references to labels and entries.
Methods:
    __init__(root, parent, parent_class):
        Initializes the UARTTool_Extension class.
    toggle_bg_frame():
        Toggles the visibility of the background frame.
    create_notebook_frame(parent_bg):
        Creates a notebook frame with tabs.
    on_tab_changed(event):
        Handles the event when a tab is changed.
    create_tab1_content():
        Creates the content for the first tab.
    update_tab1_layout(frame):
        Updates the layout of the first tab based on the window size.
    edit_label(label):
        Allows editing of a label's text.
    save_entry(entry):
        Saves the content of an entry.
    save_entries_to_file():
        Saves all labels and entries to a file.
    load_entries_from_file():
        Loads labels and entries from a file.
    uarttool_send_data(data):
        Sends data through UARTTool.
"""
# author: Roja.Zeng
# description:
#    Extension window for UARTTool
# Date: 2024-12-01

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
import re
from ttkbootstrap.dialogs import Messagebox
from toast import CollapsingFrame
from ttkbootstrap.scrolled import ScrolledText,ScrolledFrame

from cb_const import *


from pathlib import Path
from ttkbootstrap.constants import *
from ttkbootstrap.style import Bootstyle


IMG_PATH = Path(__file__).parent / 'icon'
CONFIG_FILE_PATH = Path(__file__).parent / 'uart_config.ini'


class UARTTool_Extension():
    def __init__(self, root,parent,parent_class):
        self.root = root
        self.parent = parent
        self.parent_class = parent_class
        self.extension_created = False
        
        self.tab_frames = {}



        self.add_bt_image = ImageTk.PhotoImage(Image.open(IMG_PATH/'add.png').resize((24, 24)))
        self.bg_frame = ttkb.Frame(self.parent, bootstyle=EXTENSION_BG_COLOR)#,borderwidth=2, relief='ridge', padding=5
        self.bg_frame.grid(row=1, column=0, columnspan=5, sticky="sew",padx=(15,10), pady=0)


        self.toggle_button = ttkb.Button(parent_class.config_frame, text="显示插件", width=10,command=self.toggle_bg_frame)
        self.toggle_button.pack(side='top',anchor='w', pady=0)
        self.bg_frame.grid_remove()#默认隐藏页面
        self.labels_entries = []  # 存储label和entry的引用
        self.labels_entries2 = []  # 存储label和entry的引用

    def toggle_bg_frame(self):
        if  not self.extension_created:
            self.extension_created = True
            nnb = self.create_notebook_frame(self.bg_frame)
            self.create_tab1_content()
            self.create_tab2_content()
            self.create_tab3_content()

            nnb.select(self.parent_class.ext_tab_select)
            # ttkb.Label(self.tab_frames['tab1_frame'], text="测试1").pack()
            # ttkb.Label(self.tab_frames['tab2_frame'], text="测试2").pack()

        if self.bg_frame.winfo_viewable():
            self.bg_frame.grid_remove()  # 隐藏 bg_frame
            self.parent.rowconfigure(1, weight=0)
            self.toggle_button.config(text="显示插件")
        else:
            self.bg_frame.configure(bootstyle='default')
            self.bg_frame.grid()  # 显示 bg_frame
            self.parent.rowconfigure(1, weight=1)
            self.toggle_button.config(text="隐藏插件")

    def create_notebook_frame(self, parent_bg):
        sp = ttkb.Separator(parent_bg, orient='horizontal',bootstyle='primary')
        sp.pack(fill='x', padx=0, pady=5)
        nb = ttk.Notebook(parent_bg)
        nb.pack(padx=3, pady=3, fill=BOTH, expand=YES)  # 确保 notebook 能够扩展和填充

        # 创建标签页和对应的Frame
        tabs = [
            ("自定义命令", "tab1_frame"),#tab_text, frame_name
            ("常用命令", "tab2_frame"),
            ("命令生成", "tab3_frame")
        ]

        for tab_text, frame_name in tabs:
            frame = ttk.Frame(nb)
            frame.pack(fill=BOTH, expand=YES)  # 确保 frame 能够扩展和填充
            sframe = ScrolledFrame(frame, height=EXTENSION_HEIGHT, autohide=True, borderwidth=0, relief="flat")#, borderwidth=1, relief="groove" 
            sframe.pack(fill=BOTH, expand=YES,  padx=10, pady=10)
            
            nb.add(frame, text=tab_text)
            self.tab_frames[frame_name] = sframe

        # 绑定事件
        nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        return nb
    
    def on_tab_changed(self, event):
        # 获取当前选中的标签页索引
        selected_tab_index = event.widget.index("current")
        # 获取当前选中的标签页的文本（标题）
        selected_tab_text = event.widget.tab(selected_tab_index, "text")
        self.parent_class.config["DEFAULT"]["ext_tab"] = str(selected_tab_index)
        with open(CONFIG_FILE_PATH, "w", encoding='utf-8') as configfile:
            self.parent_class.config.write(configfile)
        # print(f"当前选中的标签页索引是: {selected_tab_index}, 标题是: {selected_tab_text}")

    def create_tab1_content(self):
        tab1_frame = self.tab_frames['tab1_frame']
        self.update_tab1_layout(tab1_frame)

        # 绑定窗口大小变化事件
        #tab1_frame.bind("<Configure>", lambda event: self.update_tab1_layout(tab1_frame))

    def update_tab1_layout(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

        # 获取窗口宽度
        width = frame.winfo_width()
        if width == 1:
            width = self.root.winfo_reqwidth()  # 如果窗口还没有被显示，winfo_width() 返回1，这时使用 winfo_reqwidth() 返回
            
        column_count = min(5, max(1, width // 500))  # 每列宽度约300像素，最多5列
        padding_y_value=5
        for i in range(40):  # 假设有10组控件
            row = i // column_count
            col = i % column_count

            label = ttk.Label(frame, text=f"Label {i+1}")
            label.grid(row=row, column=col*4, padx=(15,5), pady=padding_y_value, sticky=W)
            label.bind("<Double-1>", lambda event, lbl=label: self.edit_label(lbl))

            entry = ttk.Entry(frame)
            entry.grid(row=row, column=col*4+1, padx=5, pady=padding_y_value, sticky=EW)
            entry.bind("<FocusOut>", lambda event, ent=entry: self.save_entry(ent))

            button = ttk.Button(frame, text="左发",bootstyle='outline-primary', command=lambda ent=entry: self.uarttool_send_data(ent.get()))
            button.grid(row=row, column=col*4+2, padx=(5,5), pady=padding_y_value, sticky=W)
            button_new = ttk.Button(frame, text="右发", bootstyle='outline-primary', command=lambda ent=entry: self.uarttool_send_data_r(ent.get()))
            button_new.grid(row=row, column=col*4+3, padx=(5, 15), pady=padding_y_value, sticky=W)

            self.labels_entries.append((label, entry))
        # 使所有entry所在的列具有相同的权重，以便它们均匀分布
        for col in range(column_count):
            frame.columnconfigure(col*4+1, weight=1)
        self.load_entries_from_file()

    def edit_label(self, label):
            def save_edit(event):
                new_text = entry.get()
                truncated_text = self.truncate_text(new_text)
                label.config(text=truncated_text)
                entry.destroy()
                label.grid()  # 重新显示修改后的label
                # 保存所有label和entry的内容到文件
                self.save_entries_to_file()

            entry = ttk.Entry(label.master)
            entry.insert(0, label.cget("text"))
            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", save_edit)
            entry.grid(row=label.grid_info()["row"], column=label.grid_info()["column"], padx=5, pady=5, sticky=EW)
            entry.focus()
            label.grid_remove()

    def save_entry(self, entry):
        # 保存所有label和entry的内容到文件
        self.save_entries_to_file()

    def save_entries_to_file(self):
        with open(str(img_parent_path) + '/configs/label_texts.txt', "w", encoding="utf-8") as file:
            for label, entry in self.labels_entries:
                file.write(f"{label.cget('text')}:{entry.get()}\n")

    def load_entries_from_file(self):
        try:
            with open(str(img_parent_path) + '/configs/label_texts.txt', "r", encoding="utf-8") as file:
                lines = file.readlines()
                for i, line in enumerate(lines):
                    if i < len(self.labels_entries):
                        try:
                            label_text, entry_text = line.strip().split(":", 1)
                            label, entry = self.labels_entries[i]
                            truncated_label_text = self.truncate_text(label_text)
                            label.config(text=truncated_label_text)
                            entry.delete(0, tk.END)
                            entry.insert(0, entry_text)
                        except ValueError:
                            # 跳过出错的行
                            continue
        except FileNotFoundError:
            # messagebox.showinfo("提示", "文件不存在")
            pass  # 文件不存在时不做任何处理


    def truncate_text(self, text):
        """
        将输入文本截断为最大长度为16，其中每个中文字符计为2个长度单位，每个非中文字符计为1个长度单位。
        主要是为了限制label的长度，避免过长。
        参数:
            text (str): 要截断的输入文本。
        返回:
            str: 截断后的文本。
        """
        length = 0
        result = ""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                length += 2
            else:
                length += 1
            if length > 16:
                break
            result += char
        return result
    
    def create_tab2_content(self):
        tab2_frame = self.tab_frames['tab2_frame']
        self.update_tab2_layout(tab2_frame)

    def update_tab2_layout(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()

        # 获取窗口宽度
        width = frame.winfo_width()
        if width == 1:
            width = self.root.winfo_reqwidth()  # 如果窗口还没有被显示，winfo_width() 返回1，这时使用 winfo_reqwidth() 返回

        # column_count = min(5, max(1, width // 500))  # 每列宽度约300像素，最多5列
        column_count = min(2, max(1, width // 500))  # 每列宽度约300像素，最多5列
        padding_y_value = 5

        self.labels_entries2 = []  # 存储label和entry的引用
        # 从文件读取内容
        labels_entries_data = self.load_entries_from_file2()

        # 判断数据长度
        data_length = len(labels_entries_data)
        total_entries = max(40, data_length)  # 确保至少有40个条目

        for i in range(total_entries):
            row = i // column_count
            col = i % column_count

            if i < data_length:
                label_text, entry_text, tips_text = labels_entries_data[i]
            else:
                label_text = f"Label2 {i+1}"
                entry_text = ""
                tips_text = ""     # 确保提示文本不被填充

            label = ttk.Label(frame, text=label_text)
            label.grid(row=row, column=col*4, padx=(15, 5), pady=padding_y_value, sticky=W)
            label.bind("<Double-1>", lambda event, lbl=label: self.edit_label2(lbl))

            entry = ttk.Entry(frame)
            entry.grid(row=row, column=col*4+1, padx=5, pady=padding_y_value, sticky=EW)
            entry.insert(0, entry_text)
            entry.bind("<FocusOut>", lambda event, ent=entry: self.save_entry2(ent))
            # entry.configure(state='readonly')
            if tips_text:
                ToolTip(
                    entry,
                    text=tips_text,
                    bootstyle="primary-inverse"#"success-inverse",
                )


            button = ttk.Button(frame, text="左发", bootstyle='outline-primary', command=lambda ent=entry: self.uarttool_send_data(ent.get()))
            button.grid(row=row, column=col*4+2, padx=(5, 5), pady=padding_y_value, sticky=W)

            button_r = ttk.Button(frame, text="右发", bootstyle='outline-primary', command=lambda ent=entry: self.uarttool_send_data_r(ent.get()))
            button_r.grid(row=row, column=col*4+3, padx=(5, 15), pady=padding_y_value, sticky=W)
            self.labels_entries2.append((label, entry, tips_text))

        # 使所有entry所在的列具有相同的权重，以便它们均匀分布
        for col in range(column_count):
            frame.columnconfigure(col*4+1, weight=1)
        # # 添加新的按钮
        # new_button = ttk.Button(frame, image=self.add_bt_image,text="新增", command=self.add_command,bootstyle='link',takefocus=False,compound='left')
        # new_button.grid(row=(total_entries // column_count) + 1, column=0,  pady=padding_y_value, sticky=EW)

    def add_command(self):
        print("添加新按钮")
        with open(str(img_parent_path) + '/configs/label_texts2.txt', "a", encoding="utf-8") as file:
            file.write(f"default:ChipsBank\n")
        self.create_tab2_content()


    def load_entries_from_file2(self):
        entries = []
        try:
            with open(str(img_parent_path) + '/configs/label_texts2.txt', "r", encoding="utf-8") as file:
                lines = file.readlines()
                for line in lines:
                    try:
                        parts = line.strip().split(":", 2)
                        if len(parts) == 3:
                            label_text, entry_text, tips_text = parts
                        elif len(parts) == 2:
                            label_text, entry_text = parts
                            tips_text = ""
                        elif len(parts) == 1:
                            label_text = parts[0]
                            entry_text = ""
                            tips_text = ""
                        else:
                            continue  # 跳过空行或格式不正确的行
                        entries.append((label_text, entry_text, tips_text))
                    except ValueError:
                        # 跳过出错的行
                        continue
        except FileNotFoundError:
            # messagebox.showinfo("提示", "文件不存在")
            pass  # 文件不存在时不做任何处理
        return entries

    def edit_label2(self, label):
            def save_edit(event):
                new_text = entry.get()
                truncated_text = self.truncate_text(new_text)
                label.config(text=truncated_text)
                entry.destroy()
                label.grid()  # 重新显示修改后的label
                # 保存所有label和entry的内容到文件
                self.save_entries_to_file2()

            entry = ttk.Entry(label.master)
            entry.insert(0, label.cget("text"))
            entry.bind("<Return>", save_edit)
            entry.bind("<FocusOut>", save_edit)
            entry.grid(row=label.grid_info()["row"], column=label.grid_info()["column"], padx=5, pady=5, sticky=EW)
            entry.focus()
            label.grid_remove()

    def save_entry2(self, entry):
        # 保存所有label和entry的内容到文件
        self.save_entries_to_file2()

    def save_entries_to_file2(self):
        with open(str(img_parent_path) + '/configs/label_texts2.txt', "w", encoding="utf-8") as file:
            for label, entry, tips_text in self.labels_entries2:
                file.write(f"{label.cget('text')}:{entry.get()}:{tips_text}\n")

    def uarttool_send_data(self,data):
        if not data:
            messagebox.showinfo("提示", "请输入数据")
            return
        self.parent_class.send_text.delete("1.0", tk.END)
        self.parent_class.send_text.insert(tk.END, data)
        self.parent_class.send_data()
        
    def uarttool_send_data_r(self,data):
        if not data:
            messagebox.showinfo("提示", "请输入数据")
            return
        self.parent_class.uart2app.send_text.delete("1.0", tk.END)
        self.parent_class.uart2app.send_text.insert(tk.END, data)
        self.parent_class.uart2app.send_data()


    def create_tab3_content(self):
        tab3_frame = self.tab_frames['tab3_frame']

        headers = ["起始码", "命令码高", "命令码低", "响应位", "数据长度", "数据", "校验和"]
        sub_headers = ["1Byte", "1Byte", "1Byte", "1Byte", "1Byte", "0~255", "1Byte"]
        values = ["0x5A", "CMD_H", "CMD_L", "RESP", "DL", "DATA_H ... DATA_L", "CHECKSUM"]
        entry_widths = [5, 5, 5, 5, 5, 20, 5]  # 每个 Entry 的宽度
        entry_values = [0x5A, 0x00, 0x00, 0x00, 0x01, 0x00, "01", 0x5B]

        for i, header in enumerate(headers):
            ttk.Label(tab3_frame, text=header).grid(row=0, column=i, padx=5, pady=5, sticky=W)
        sp1 = ttk.Separator(tab3_frame, orient='horizontal',bootstyle='light')
        sp1.grid(row=1, column=0, columnspan=7, sticky="ew", pady=0)
        for i, sub_header in enumerate(sub_headers):
            ttk.Label(tab3_frame, text=sub_header).grid(row=2, column=i, padx=5, pady=5, sticky=W)
        sp2 = ttk.Separator(tab3_frame, orient='horizontal',bootstyle='light')
        sp2.grid(row=3, column=0, columnspan=7, sticky="ew", pady=0)
        for i, value in enumerate(values):
            ttk.Label(tab3_frame, text=value).grid(row=4, column=i, padx=5, pady=5, sticky=W)
        sp3 = ttk.Separator(tab3_frame, orient='horizontal',bootstyle='light')
        sp3.grid(row=5, column=0, columnspan=7, sticky="ew", pady=0)

        def on_len_entry_change(*args):
            try:
                data_len = int(self.entry_data_len_var.get(), 16)
                current_data = self.entry_data_var.get().split()
                current_len = len(current_data)
                
                if data_len > current_len:
                    current_data.extend(["00"] * (data_len - current_len))
                elif data_len < current_len:
                    current_data = current_data[:data_len]

                self.entry_data_var.set(" ".join(current_data))
                
                if 20 <= data_len <= 40:
                    self.entry_data.config(width=data_len*2)
                else:
                    self.entry_data.config(width=20 if data_len < 20 else 40*2)
                
                start_code = int(self.entry_start_code_var.get(), 16)
                cmd_h = int(self.entry_cmd_h_var.get(), 16)
                cmd_l = int(self.entry_cmd_l_var.get(), 16)
                resp = int(self.entry_resp_var.get(), 16)
                
                checksum = start_code + cmd_h + cmd_l + resp + data_len
                for byte in current_data:
                    checksum += int(byte, 16)
                checksum %= 256
                
                self.entry_checksum_var.set(f"{checksum:02X}")
            except ValueError:
                pass
        def on_entry_change(*args):
            try:
                data_len = int(self.entry_data_len_var.get(), 16)
                data = self.entry_data_var.get().split()
                curren_data_len = len(data)
                if curren_data_len != data_len:
                    self.entry_data_len_var.set(f"{curren_data_len:02X}")
                    return
                start_code = int(self.entry_start_code_var.get(), 16)
                cmd_h = int(self.entry_cmd_h_var.get(), 16)
                cmd_l = int(self.entry_cmd_l_var.get(), 16)
                resp = int(self.entry_resp_var.get(), 16)
                
                # 计算校验和时包括所有数据字节
                checksum = start_code + cmd_h + cmd_l + resp + data_len
                for byte in data:
                    checksum += int(byte, 16)
                checksum %= 256
                
                self.entry_checksum_var.set(f"{checksum:02X}")
            except ValueError:
                pass
        self.entry_start_code_var = tk.StringVar()
        self.entry_start_code_var.trace("w", on_entry_change)
        self.entry_start_code = ttk.Entry(tab3_frame, width=entry_widths[0], textvariable=self.entry_start_code_var)
        self.entry_start_code.grid(row=6, column=0, padx=5, pady=5)
        
        self.entry_cmd_h_var = tk.StringVar()
        self.entry_cmd_h_var.trace("w", on_entry_change)
        self.entry_cmd_h = ttk.Entry(tab3_frame, width=entry_widths[1], textvariable=self.entry_cmd_h_var)
        self.entry_cmd_h.grid(row=6, column=1, padx=5, pady=5)

        self.entry_cmd_l_var = tk.StringVar()
        self.entry_cmd_l_var.trace("w", on_entry_change)
        self.entry_cmd_l = ttk.Entry(tab3_frame, width=entry_widths[2], textvariable=self.entry_cmd_l_var)
        self.entry_cmd_l.grid(row=6, column=2, padx=5, pady=5)

        self.entry_resp_var = tk.StringVar()
        self.entry_resp_var.trace("w", on_entry_change)
        self.entry_resp = ttk.Entry(tab3_frame, width=entry_widths[3], textvariable=self.entry_resp_var)
        self.entry_resp.grid(row=6, column=3, padx=5, pady=5)

        self.entry_data_len_var = tk.StringVar()
        self.entry_data_len_var.trace("w", on_len_entry_change)
        self.entry_data_len = ttk.Entry(tab3_frame, width=entry_widths[4], textvariable=self.entry_data_len_var)
        self.entry_data_len.grid(row=6, column=4, padx=5, pady=5)

        self.entry_data_var = tk.StringVar()
        self.entry_data_var.trace("w", on_entry_change)
        self.entry_data = ttk.Entry(tab3_frame, width=entry_widths[5], textvariable=self.entry_data_var)
        self.entry_data.grid(row=6, column=5, padx=5, pady=5)

        self.entry_checksum_var = tk.StringVar()
        self.entry_checksum = ttk.Entry(tab3_frame, width=entry_widths[6], textvariable=self.entry_checksum_var)
        self.entry_checksum.grid(row=6, column=6, padx=5, pady=5)


        self.entry_start_code.insert(0, "5A")
        self.entry_cmd_h.insert(0, "00")
        self.entry_cmd_l.insert(0, "00")
        self.entry_resp.insert(0, "00")
        self.entry_data_len.insert(0, "01")




        left_button = ttkb.Button(tab3_frame, text="左窗发送", bootstyle='outline-primary',command=lambda: self.uarttool_send_data_hex())
        left_button.grid(row=7, column=0, columnspan=2, pady=10,sticky='we')
        right_button = ttkb.Button(tab3_frame, text="右窗发送", bootstyle='outline-primary',command=lambda: self.uarttool_send_data_hex_r())
        right_button.grid(row=7, column=3, columnspan=2, pady=10,sticky='we')

    def uarttool_send_data_hex(self):
        all_entries_data = [
            self.entry_start_code_var.get(),
            self.entry_cmd_h_var.get(),
            self.entry_cmd_l_var.get(),
            self.entry_resp_var.get(),
            self.entry_data_len_var.get(),
            self.entry_data_var.get(),
            self.entry_checksum_var.get()
        ]
        send_text = " ".join(all_entries_data)
        #勾选一下hex发送
        self.parent_class.hex_send_var.set(1)
        self.parent_class.send_text.delete("1.0", tk.END)
        self.parent_class.send_text.insert(tk.END, send_text)
        self.parent_class.send_data()
        
    def uarttool_send_data_hex_r(self):
        all_entries_data = [
            self.entry_start_code_var.get(),
            self.entry_cmd_h_var.get(),
            self.entry_cmd_l_var.get(),
            self.entry_resp_var.get(),
            self.entry_data_len_var.get(),
            self.entry_data_var.get(),
            self.entry_checksum_var.get()
        ]
        #勾选一下hex发送
        self.parent_class.uart2app.hex_send_var.set(1)
        send_text = " ".join(all_entries_data)
        self.parent_class.uart2app.send_text.delete("1.0", tk.END)
        self.parent_class.uart2app.send_text.insert(tk.END, send_text)
        self.parent_class.uart2app.send_data()





