import tkinter as tk
from ttkbootstrap import Style
import ttkbootstrap as ttkb
from ttkbootstrap.scrolled import ScrolledText
from tkinter import ttk


class CustomPanedWindow(tk.PanedWindow):
    def __init__(self, *args, **kwargs):
        self.orient = kwargs.get('orient', tk.HORIZONTAL)
        super().__init__(*args, **kwargs)
        self.bind_all("<Motion>", self.on_motion)
        self.bind_all("<ButtonPress-1>", self.on_button_press)
        self.bind_all("<ButtonRelease-1>", self.on_button_release)
        self.bind_all("<B1-Motion>", self.on_drag)
        self.sash_separator = ttkb.Separator(self, orient='vertical' if self.orient == tk.HORIZONTAL else 'horizontal', bootstyle="primary")

        self.sash_separator.place_forget()  # Initially hide the separator
        self.last_sash_pos = None
        self.mouse_in_sash_area = False
        self.dragging = False

    def in_sash_area(self, pos):
        sash_positions = [self.sash_coord(i)[0] if self.orient == tk.HORIZONTAL else self.sash_coord(i)[1] for i in range(self.sash_count())]
        threshold = 20  # Adjust this value to control the sash area size
        return any(abs(pos - sash_pos) < threshold for sash_pos in sash_positions)

    def closest_sash(self, pos):
        sash_positions = [self.sash_coord(i)[0] if self.orient == tk.HORIZONTAL else self.sash_coord(i)[1] for i in range(self.sash_count())]
        return min(sash_positions, key=lambda sash_pos: abs(pos - sash_pos))

    def on_motion(self, event):
        pos = event.x if self.orient == tk.HORIZONTAL else event.y
        if self.in_sash_area(pos):

            if not self.mouse_in_sash_area:
                self.mouse_in_sash_area = True
            sash_pos = self.closest_sash(pos)
            #print(f"sash_pos:{sash_pos}   last_sash_pos:{self.last_sash_pos}")
            self.sash_separator.place(x=sash_pos, y=0, height=self.winfo_height())
            if sash_pos != self.last_sash_pos:
                if self.orient == tk.HORIZONTAL:
                    self.sash_separator.place(x=sash_pos, y=0, height=self.winfo_height())
                else:
                    self.sash_separator.place(x=0, y=sash_pos, width=self.winfo_width())
                self.last_sash_pos = sash_pos
        else:
            if self.mouse_in_sash_area:
                self.mouse_in_sash_area = False
                self.sash_separator.place_forget()

    def on_button_press(self, event):
        pos = event.x if self.orient == tk.HORIZONTAL else event.y
        if self.in_sash_area(pos):
            self.dragging = True
            self.last_sash_pos = self.closest_sash(pos)

    def on_drag(self, event):
        if self.dragging:
            pos = event.x if self.orient == tk.HORIZONTAL else event.y
            sash_pos = self.closest_sash(pos)
            if self.orient == tk.HORIZONTAL:
                self.sash_separator.place(x=sash_pos, y=0, height=self.winfo_height())
            else:
                self.sash_separator.place(x=0, y=sash_pos, width=self.winfo_width())
            self.update_sash(pos)

    def on_button_release(self, event):
        if self.dragging:
            self.dragging = False
            self.sash_separator.place_forget()

    def sash_count(self):
        return self.panes_count() - 1

    def panes_count(self):
        return len(self.panes())

    def update_sash(self, pos):
        for i in range(self.sash_count()):
            sash_pos = self.sash_coord(i)[0] if self.orient == tk.HORIZONTAL else self.sash_coord(i)[1]
            #if abs(pos - sash_pos) < 20:
            if self.orient == tk.HORIZONTAL:
                self.sash_place(i, pos, 0)
            else:
                self.sash_place(i, 0, pos)
            break