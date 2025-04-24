import tkinter as tk
from tkinter import PhotoImage, scrolledtext
from ttkbootstrap import Style
from ttkbootstrap.constants import *
import ttkbootstrap as ttkb
from ttkbootstrap.tooltip import ToolTip
from pathlib import Path
from PIL import Image, ImageTk,  ImageOps,ImageSequence
from itertools import cycle
from ttkbootstrap.scrolled import ScrolledText, ScrolledFrame

from cb_const import *

CB_UWB_INTRODUCE = """\n随着标准化日趋成熟，商用UWB芯片的可用领域正在迅速扩大。
国内已有多家芯片厂商发布了UWB芯片。
由Chipsbank开发的最新UWB芯片CBU5000V210是一款集成了UWB（6-9GHz）、
蓝牙（BLE）和32位微处理器（MCU）的单芯片CMOS SoC，
符合IEEE 802.15.4z、IEEE 802.15.4-2015和FiRa标准。
这款芯片可以支持测距、3D AOA和雷达功能。BLE系统支持BLE5.0，
具有低功耗特性，使得芯片可以支持更长的电池寿命。
SoC集成了高性能的32位MCU、硬件安全平台和丰富的功能模块，
使得芯片适用于通信、测距、物联网等应用。
接下来UWB芯片的普及度会不断提高，应用越来越广泛。
随着 2025 年即将推出的新 IEEE 802.15.4ab，
将会有新一代UWB芯片进入市场，其功耗进一步降低，
安全性提高，并支持流媒体音频。
我们的生活将会因为这些智能家居设备而更加便捷，让我们拭目以待。\n\n"""

g_meter_counter = 0

class AnimatedGif(ttkb.Frame):
    def __init__(self, master, file_path=None, new_width=100, new_height=100):
        super().__init__(master, width=new_width, height=new_height)
        self.playing = False
        self.file_path = file_path if file_path else str(img_parent_path) +'/icon/loading.gif'
        self.new_width = new_width
        self.new_height = new_height
        self.load_gif(self.file_path)

        self.img_container = ttkb.Label(self, image=next(self.image_cycle))
        self.img_container.pack(fill="both", expand="yes")
        self.img_container.bind("<Button-1>", self.toggle_animation)


    def load_gif(self, file_path):
        """Load GIF from the specified file path."""
        with Image.open(file_path) as im:
            sequence = ImageSequence.Iterator(im)
            self.style = ttkb.Style()
            self.theme_type = self.style.theme.type
            if self.style.theme.type == "dark":
                images = [ImageTk.PhotoImage(ImageOps.invert(s.convert("RGB")).resize((self.new_width, self.new_height))) for s in sequence]
            else:
                images = [ImageTk.PhotoImage(s.resize((self.new_width, self.new_height))) for s in sequence]
            self.image_cycle = cycle(images)
            self.framerate = im.info["duration"]

    def change_image(self, new_file_path):
        """Change the GIF image to a new one."""
        self.playing = False  # Stop the current animation
        self.load_gif(new_file_path)  # Load the new GIF
        self.img_container.configure(image=next(self.image_cycle))  # Update the image container
        # Optionally, restart the animation
        self.playing = True
        self.next_frame()

    def resize_image(self, new_width, new_height):
        """Resize the current GIF image."""
        self.playing = False  # Stop the current animation
        self.new_width = new_width
        self.new_height = new_height
        self.load_gif(self.file_path)  # Reload the GIF with the new size
        self.img_container.configure(image=next(self.image_cycle))  # Update the image container
        # Optionally, restart the animation
        self.playing = True
        self.next_frame()

    def toggle_animation(self, event):
        self.playing = not self.playing
        if self.playing:
            self.next_frame()

    def next_frame(self):
        if self.playing:
            style = ttkb.Style()
            if not style.theme.type == self.theme_type:#主题发生改变，则重新loading图片
                self.theme_type = style.theme.type
                print("主题发生改变")
                self.load_gif(self.file_path)
            self.img_container.configure(image=next(self.image_cycle))
            self.after(self.framerate, self.next_frame)
    
    def play_animation(self):
        """Start the animation."""
        if not self.playing:
            self.playing = True
            self.next_frame()

    def pause_animation(self):
        """Pause the animation."""
        self.playing = False


def open_link():
    import webbrowser
    webbrowser.open("www.chipsbank.com")

class ResizableDrawerApp:
    drawer_opened = {}
    drawer_frames = {}
    main_self = {}
    open_buttons = {}

    def __init__(self, parent, top_root, root, parent_frame, image_path, drawer_number):
        self.root = root
        self.top_root = top_root
        self.parent = parent
        self.parent_frame = parent_frame
        self.drawer_number = drawer_number
        self.drawer_width =  (root.winfo_screenwidth()//9)*2-50
        self.init_alpha = 0.9  # 默认透明度
        self.icon_image = PhotoImage(file=image_path).subsample(8, 8)
        self.meter_update_timer = None

        # Initialize the drawer state in the class-level dictionary
        ResizableDrawerApp.drawer_opened[drawer_number] = False

        # Create the drawer as a Toplevel window
        # self.drawer = ttkb.Frame(root)
        # self.drawer.configure(bg='gray', borderwidth=1, relief="raised")
        #self.drawer.wm_overrideredirect(True)  # Remove window decorations
        #self.drawer.withdraw()  # Start with the drawer hidden
        if drawer_number == 3:
            self.drawer_width =  self.drawer_width*4
        self.drawer = ttkb.Frame(root, width=self.drawer_width, height=root.winfo_screenheight())#,borderwidth=1, relief="raised"
        self.drawer.pack_propagate(False)  # Prevent resizing
        #self.drawer.minsize(self.drawer_width, root.winfo_screenheight())
        self.drawer.place(x=root.winfo_screenwidth(), y=0)  # Hide off-screen
        ResizableDrawerApp.drawer_frames[drawer_number] = self.drawer
        ResizableDrawerApp.main_self[drawer_number] = self

        # Create a button to open the drawer
        self.open_button = ttkb.Button(self.parent_frame, image=self.icon_image, command=self.open_drawer,
                                       bootstyle="link", takefocus=False)
        self.open_button.grid(row=drawer_number - 1, column=0, padx=(0,0), pady=10)
        ResizableDrawerApp.open_buttons[drawer_number] = self.open_button
        # Add tooltip to the button
        self.tip_text = f"Open Drawer {drawer_number}"
        if drawer_number == 1:
            self.tip_text = "发送记录"
        elif drawer_number == 2:
            self.tip_text = "芯邦UWB介绍"
        elif drawer_number == 3:
            self.tip_text = "UWB测试"
        else:
            self.tip_text = f"Open Drawer {drawer_number}"
            # create_tooltip(self.open_button, f"Open Drawer {drawer_number}")
        ToolTip(
                self.open_button,
                text= self.tip_text,
                bootstyle="primary-inverse",
            )
        # Add some content to the drawer
        # self.drawer_content = ttkb.Label(self.drawer, text=f"This is the drawer content {self.drawer_number}")
        # self.drawer_content.pack(padx=0,pady=20)
        # ttkb.Separator(self.drawer).pack(fill=X, pady=0, padx=20)
        # Bind mouse events
        # if drawer_number != 1:  # 历史记录抽屉不让更改窗口大小
        self.drawer.bind("<Button-1>", self.start_resize)
        self.drawer.bind("<B1-Motion>", self.perform_resize)

        self.is_resizing = False
        self.start_x = 0
        self.drawer_initial_width = 200

        if drawer_number == 1:
            # sb = ttkb.Scrollbar(self.drawer,orient = tk.VERTICAL)
            # sb.pack(padx=5, pady=5, fill=tk.X, side=tk.RIGHT)
            # sb.set(0.1, 0.3)
            self.frame_sp_left = ttkb.Separator(self.drawer, orient='vertical', bootstyle='primary')
            self.frame_sp_left.pack(fill=Y, pady=0, padx=(0,20),side=LEFT)
            self.frame_sp = ttkb.Separator(self.drawer, bootstyle='primary',orient='vertical')
            self.frame_sp.pack(fill=Y, pady=0, padx=20,side=RIGHT)
            self.drawer_content = ttkb.Label(self.drawer, text=f"This is the drawer content {self.drawer_number}")
            self.drawer_content.pack(padx=0,pady=20)
            self.drawer_content.configure(text='历史发送记录')
            # self.lb = ttkb.Button(master=self.drawer, text="芯邦官网", command=open_link,bootstyle=LINK)
            # self.lb.pack(fill=X, pady=5)   
            #ttkb.Separator(self.drawer).pack(fill=X, pady=0, padx=20)
            self.load_history()

        elif drawer_number == 2:
            #self.drawer_content.configure(text="关于芯邦和UWB")
            # self.drawer_content.pack(padx=0,pady=(40,5))
            self.frame_sp_left = ttkb.Separator(self.drawer, orient='vertical', bootstyle='primary')
            self.frame_sp_left.pack(fill=Y, pady=0, padx=(0,20),side=LEFT)
            self.frame_sp = ttkb.Separator(self.drawer, bootstyle='primary',orient='vertical')
            self.frame_sp.pack(fill=Y, pady=0, padx=20,side=RIGHT)
            header_frame = ttkb.Frame(self.drawer)
            header_frame.pack(padx=20, pady=(25,0))
            gif = AnimatedGif(header_frame)
            gif.resize_image(25, 25)
            gif.change_image(str(img_parent_path) +"/icon/click.gif")
            
            gif.grid(row=0, column=1, padx=0, pady=5)
            self.lb = ttkb.Button(master=header_frame, text="芯邦官网", command=open_link,bootstyle=(LINK,SUCCESS))
            self.lb.grid(row=0, column=0, padx=0, pady=5) 

            self.intro_txt = ttkb.Label(self.drawer, text=CB_UWB_INTRODUCE,anchor='center')#scrolledtext.ScrolledText(master=self.drawer, undo=True, height=20)#30行吧
            self.intro_txt.pack(fill=X, padx=30, pady=5)    

            # 配置一个名为'center'的标签，用于居中对齐文本
            # self.intro_txt.tag_configure('center', justify='center')

            # # 在插入文本后，将'center'标签应用到所有文本上
            # self.intro_txt.insert(tk.END, CB_UWB_INTRODUCE)
            # self.intro_txt.tag_add('center', '1.0', 'end')
            # self.intro_txt.configure(state='disabled')
            # self.ver_lb = ttkb.Label(self.drawer, text=SOFTWARE_VERSION)
            # self.ver_lb.pack(padx=5,pady=10)
            

        elif drawer_number == 3:
            self.drawer_content.configure(text='开发板功能验证')
            self.drawer_content.pack(anchor='w',padx=20)
            ttkb.Separator(self.drawer).pack(fill=X, pady=0, padx=20)
            # self.meter = ttkb.Meter(
            #     master=self.drawer,
            #     metersize=150,
            #     amountused=45,
            #     subtext="meter widget",
            #     bootstyle=INFO,
            #     interactive=True,
            # )
            # self.meter.pack(pady=10)
            # self.meter.configure(amountused=0)
            #self.arrow = pic_ArrowApp(self.drawer)
            self.lb3 = ttkb.Button(master=self.drawer, text="芯邦官网", command=open_link,bootstyle=LINK)
            self.lb3.pack(side=BOTTOM, fill=X, pady=150)
            #self.arrow = ArrowApp(self.drawer)
         
        # Bind global click event to root window
        self.top_root.bind("<Button-1>", self.global_click, add='+')  # Ensure add mode

    def start_meter_update_timer(self):
        if self.meter_update_timer:
            self.root.after_cancel(self.meter_update_timer)
        self.meter_update_timer = self.root.after(10, self.meter_update)

    def meter_update(self):
        return#暂时不用
        global g_meter_counter
        #print(f"meter_update:{g_meter_counter}")
        g_meter_counter += 1
        if g_meter_counter > 100:
            g_meter_counter = 0
        # self.arrow.rotate_arrow(g_meter_counter*3.6)
        # self.meter.configure(amountused=g_meter_counter)
        self.start_meter_update_timer()

    def open_drawer(self):
        for num, main_self in ResizableDrawerApp.main_self.items():
            if num != self.drawer_number and ResizableDrawerApp.drawer_opened[num]:
                main_self.close_drawer()

        if not ResizableDrawerApp.drawer_opened[self.drawer_number]:
            ResizableDrawerApp.drawer_opened[self.drawer_number] = True

            button_x = self.open_button.winfo_rootx()
            button_y = self.open_button.winfo_rooty()
            button_height = self.open_button.winfo_height()
            parent_height = self.parent_frame.winfo_height()

            if self.drawer_number == 1:
                self.clear_history_entries()  # Clear current history entries
                self.load_history()  # Reload the history from the file

            # Set drawer's size and position
            # self.drawer.geometry(
            #     f"{self.drawer_width}x{parent_height}+{button_x + self.open_button.winfo_width()}+{button_y - (2 * self.drawer_number - 1) * 10 - (self.drawer_number - 1) * button_height}")
            # self.drawer.deiconify()  # Show the drawer
            self.open_button.configure(bootstyle="primary")  # Change button color when drawer is open
            self.drawer.place(x=self.parent_frame.winfo_width(), y=0)
            # self.set_transparent(self.drawer, self.init_alpha)  # Set transparency to 80%
            if self.drawer_number == 3:
                self.start_meter_update_timer()
        else:
            self.close_drawer()


    def close_drawer(self):
        ResizableDrawerApp.drawer_opened[self.drawer_number] = False
        # self.drawer.withdraw()  # Hide the drawer
        #self.drawer.place(x=self.parent_frame.winfo_width(), y=0)
        self.open_button.configure(bootstyle="link")
        self.drawer.place(x=self.root.winfo_screenwidth(), y=0)
        if self.meter_update_timer:
            self.root.after_cancel(self.meter_update_timer)

    def start_resize(self, event):
        self.is_resizing = True
        self.start_x = event.x
        self.drawer_initial_width = self.drawer.winfo_width()

    def perform_resize(self, event):
        if self.is_resizing:
            new_width = self.drawer_initial_width + (event.x - self.start_x)
            if new_width > 200:  # Minimum width
                self.drawer.config(width=new_width)


    def load_history(self):
        try:
            with open(str(img_parent_path)+'/send_history.txt', 'r', encoding='utf-8') as file:
                history = file.readlines()
        except FileNotFoundError:
            history = []

        hex_entries = [line for line in history if line.startswith("[HEX]")]
        text_entries = [line for line in history if line.startswith("[TEXT]")]

        # Only keep the latest 10 entries for each type
        hex_entries = hex_entries[-10:]
        text_entries = text_entries[-10:]

        

        screen_height = self.drawer.winfo_screenheight()
        height = screen_height//2.5
        height = height -100

        self.history_frame_bg = ScrolledFrame(self.drawer, height=height, autohide=True)#, borderwidth=1, relief="groove" 
        self.history_frame_bg.pack(fill=tk.X,  padx=10, pady=10)
        

        for line in text_entries + hex_entries :
            label_text = "HEX" if line.startswith("[HEX]") else "TEXT"
            self.create_history_entry(line.strip(), label_text)
        #增加常用命令按键
        # 创建并配置 Combobox 组件
        # ttkb.Separator(self.drawer, bootstyle= 'primary').pack(fill=X, pady=0, padx=20)
        self.command = None
        cobbox_width = 12
        self.gen_cmd_frame_bg = ttkb.Frame(self.drawer)#, borderwidth=1, relief="groove" 
        self.gen_cmd_frame_bg.pack(fill=tk.X,  padx=10, pady=10)
        ttkb.Label(self.gen_cmd_frame_bg, text="选择接收发送模式:").grid(column=0, row=0, padx=10, pady=5)
        self.combobox_arg_1 = ttkb.Combobox(self.gen_cmd_frame_bg, values=["0: 发送", "1: 接收"],width=cobbox_width)
        self.combobox_arg_1.grid(column=1, row=0, padx=10, pady=5)
        self.combobox_arg_1.current(1)
        self.combobox_arg_1.bind("<<ComboboxSelected>>", self.update_arg_4_options)

        ttkb.Label(self.gen_cmd_frame_bg, text="选择 Packet mode:").grid(column=0, row=1, padx=10, pady=5)
        self.combobox_arg_2 = ttkb.Combobox(self.gen_cmd_frame_bg,width=cobbox_width, values=["0: BPRF_6P81", "1: LG4A_0P85", "2: HPRF_6P81", "3: HPRF_7P80", "4: HPRF_27P2", "5: HPRF_31P2"])
        self.combobox_arg_2.grid(column=1, row=1, padx=10, pady=5)
        self.combobox_arg_2.current(0)

        ttkb.Label(self.gen_cmd_frame_bg, text="选择 STS mode:").grid(column=0, row=2, padx=10, pady=5)
        self.combobox_arg_3 = ttkb.Combobox(self.gen_cmd_frame_bg,width=cobbox_width, values=["0: SP0", "1: SP1", "2: SP3"])
        self.combobox_arg_3.grid(column=1, row=2, padx=10, pady=5)
        self.combobox_arg_3.current(0)

        self.label_arg_4 = ttkb.Label(self.gen_cmd_frame_bg, text="选择接收天线端口:")
        self.label_arg_4.grid(column=0, row=3, padx=10, pady=5)
        self.combobox_arg_4 = ttkb.Combobox(self.gen_cmd_frame_bg,width=cobbox_width, values=["0: RX0", "1: RX1", "2: RX2"])
        self.combobox_arg_4.grid(column=1, row=3, padx=10, pady=5)
        self.combobox_arg_4.current(0)

        # 创建生成命令按钮
        self.generate_button = ttkb.Button(self.gen_cmd_frame_bg, text="生成命令", command=self.generate_command)
        self.generate_button.grid(column=0, row=4,  padx=10, pady=10)
        # 创建复制命令按钮
        self.copy_button = ttkb.Button(self.gen_cmd_frame_bg, text="复制命令", command=self.copy_command)
        self.copy_button.grid(column=1, row=4, padx=10, pady=10)
        # 显示生成的命令
        self.result_label = ttkb.Label(self.gen_cmd_frame_bg, text="")
        self.result_label.grid(column=0, row=5, columnspan=2, padx=10, pady=10)

    def copy_command(self):
        if self.command is None:
            return
        self.gen_cmd_frame_bg.clipboard_clear()
        self.gen_cmd_frame_bg.clipboard_append(self.command)
        self.gen_cmd_frame_bg.update()  # 现在剪贴板内容已经更新

    def generate_command(self):
        arg_1 = self.combobox_arg_1.get().split(':')[0]
        arg_2 = self.combobox_arg_2.get().split(':')[0]
        arg_3 = self.combobox_arg_3.get().split(':')[0]
        arg_4 = self.combobox_arg_4.get().split(':')[0]
        
        self.command = f"a,{arg_1},{arg_2},{arg_3},{arg_4}"
        self.result_label.config(text=f"生成的命令: {self.command}")

    def update_arg_4_options(self, event):
        arg_1_value = self.combobox_arg_1.get().split(':')[0]
        if arg_1_value == '0':  # TX
            power_codes = [f"{i}: {(i * 0.5 - 55):.1f} dBm/MHz" for i in range(63) if i not in [8, 9, 10, 11]]
            self.combobox_arg_4.config(values=power_codes)
            self.label_arg_4.config(text="选择 Power Code:")
            self.combobox_arg_4.current(38)
        else:  # RX
            self.combobox_arg_4.config(values=["0: RX0", "1: RX1", "2: RX2"])
            self.label_arg_4.config(text="选择接收天线端口:")
            self.combobox_arg_4.current(0)


    def clear_history_entries(self):
        for widget in self.drawer.winfo_children():
            if isinstance(widget, ttkb.Frame):
                widget.destroy()

    def create_history_entry(self, data_str, label_text):
        # Create a frame to hold the label, entry, and button
        history_frame = ttkb.Frame(self.history_frame_bg)
        history_frame.pack(pady=5, expand=YES, fill=tk.X)
        # history_frame = ScrolledFrame(self.drawer, autohide=True)
        # history_frame.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Create and pack the label (convert to uppercase)
        label = ttkb.Label(history_frame, text=label_text.upper(), width=5)
        label.pack(side=tk.LEFT, padx=10)

        # Remove prefix and format data accordingly

        if label_text == "TEXT":
            data_str = data_str.lstrip("[TEXT]").strip()
            formatted_data = data_str
        elif label_text == "HEX":
            data_str = data_str.lstrip("[HEX]").strip()
            formatted_data = " ".join(data_str[i:i + 2] for i in range(0, len(data_str), 2))
        # Create the entry variable to hold the entry widget
        entry_var = tk.StringVar(value=formatted_data)

        # Create and pack the entry
        entry = ttkb.Entry(history_frame, width=self.drawer_width//20, textvariable=entry_var)
        entry.pack(side=tk.LEFT,fill=tk.X, expand=YES)

        # Create and pack the send button
        send_button = ttkb.Button(history_frame, text="选择",
                                    command=lambda e=entry_var, t=label_text: self.send_history(e.get(), t))
        send_button.pack(side=tk.LEFT, padx=10)

    def send_history(self, data_str, label_text):
        # Assumes send_text is a Text widget available in the app context
        if label_text == "HEX":
            self.parent.hex_send_var.set(True)  # Set hex_send_var to True
            formatted_data = data_str
        else:
            self.parent.hex_send_var.set(False)  # Set hex_send_var to False
            formatted_data = data_str

        self.parent.send_text.delete("1.0", tk.END)
        self.parent.send_text.insert(tk.END, formatted_data)
        self.close_drawer()  # Close the drawer after sending history

    @classmethod
    def close_all_drawers(cls):
        for main_self in cls.main_self.values():
            if ResizableDrawerApp.drawer_opened[main_self.drawer_number]:
                main_self.close_drawer()

    def global_click(self, event):
        #print(f"global_click:{event.x_root},{event.y_root}")
        x, y = event.x_root, event.y_root
        clicked_outside_any_drawer = True
        for main_self in ResizableDrawerApp.main_self.values():
            if ResizableDrawerApp.drawer_opened[main_self.drawer_number]:
                if (
                        x < main_self.drawer.winfo_rootx() + main_self.drawer.winfo_width() and
                        main_self.drawer.winfo_rooty() < y < main_self.drawer.winfo_rooty() + main_self.drawer.winfo_height()):
                    clicked_outside_any_drawer = False
                    break

        if clicked_outside_any_drawer:
            ResizableDrawerApp.close_all_drawers()
        #ResizableDrawerApp.drawer_opened[self.drawer_number] = True
    def set_transparent(self, widget, alpha):
        self.drawer.attributes('-alpha', alpha)
