from tkinter import font
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap import utility
import tkinter as tk

# https://www.fontspace.com/freeserif-font-f13277

DEFAULT_ICON_WIN32 = "\ue154"
DEFAULT_ICON = "\u25f0"


class ToastNotification:
    """A semi-transparent popup window for temporary alerts or messages.
    You may choose to display the toast for a specified period of time,
    otherwise you must click the toast to close it.

    ![toast notification](../assets/toast/toast.png)

    Examples:

        ```python
        import ttkbootstrap as ttk
        from ttkbootstrap.toast import ToastNotification

        app = ttk.Window()

        toast = ToastNotification(
            title="ttkbootstrap toast message",
            message="This is a toast message",
            duration=3000,
        )
        toast.show_toast()

        app.mainloop()
        ```
    """

    def __init__(
        self,
        title,
        message,
        duration=None,
        bootstyle=LIGHT,
        alert=False,
        icon=None,
        iconfont=None,
        position=None,
        **kwargs,
    ):
        """
        Parameters:

            title (str):
                The toast title.

            message (str):
                The toast message.

            duration (int):
                The number of milliseconds to show the toast. If None
                (default), then you must click the toast to close it.

            bootstyle (str):
                Style keywords used to updated the label style. One of
                the accepted color keywords.

            alert (bool):
                Indicates whether to ring the display bell when the
                toast is shown.

            icon (str):
                A unicode character to display on the top-left hand
                corner of the toast. The default symbol is OS specific.
                Pass an empty string to remove the symbol.

            iconfont (Union[str, Font]):
                The font used to render the icon. By default, this is
                OS specific. You may need to change the font to enable
                better character or emoji support for the icon you
                want to use. Windows (Segoe UI Symbol),
                Linux (FreeSerif), MacOS (Apple Symbol)

            position (Tuple[int, int, str]):
                A tuple that controls the position of the toast. Default
                is OS specific. The tuple cooresponds to
                (horizontal, vertical, anchor), where the horizontal and
                vertical elements represent the position of the toplevel
                releative to the anchor, which is "ne" or top-left by
                default. Acceptable anchors include: n, e, s, w, nw, ne,
                sw, se. For example: (100, 100, 'ne').

            **kwargs (Dict):
                Other keyword arguments passed to the `Toplevel` window.
        """
        self.message = message
        self.title = title
        self.duration = duration
        self.bootstyle = bootstyle
        self.icon = icon
        self.iconfont = iconfont
        self.iconfont = None
        self.titlefont = None
        self.toplevel = None
        self.kwargs = kwargs
        self.alert = alert
        self.position = position

        if "overrideredirect" not in self.kwargs:
            self.kwargs["overrideredirect"] = True
        if "alpha" not in self.kwargs:
            self.kwargs["alpha"] = 0.95

        if position is not None:
            if len(position) != 3:
                self.position = None

    def show_toast(self, *_):
        """Create and show the toast window."""

        # build toast
        self.toplevel = ttk.Toplevel(**self.kwargs)
        self._setup(self.toplevel)

        self.container = ttk.Frame(self.toplevel, bootstyle=self.bootstyle)
        self.container.pack(fill=BOTH, expand=YES)
        ttk.Label(
            self.container,
            text=self.icon,
            font=self.iconfont,
            bootstyle=f"{self.bootstyle}-inverse",
            anchor=NW,
        ).grid(row=0, column=0, rowspan=2, sticky=NSEW, padx=(5, 0))
        ttk.Label(
            self.container,
            text=self.title,
            font=self.titlefont,
            bootstyle=f"{self.bootstyle}-inverse",
            anchor=NW,
        ).grid(row=0, column=1, sticky=NSEW, padx=10, pady=(5, 0))
        ttk.Label(
            self.container,
            text=self.message,
            wraplength=utility.scale_size(self.toplevel, 300),
            bootstyle=f"{self.bootstyle}-inverse",
            anchor=NW,
        ).grid(row=1, column=1, sticky=NSEW, padx=10, pady=(0, 5))

        self.toplevel.bind("<ButtonPress>", self.hide_toast)

        # alert toast
        if self.alert:
            self.toplevel.bell()

        # specified duration to close
        if self.duration:
            self.toplevel.after(self.duration, self.hide_toast)

    def hide_toast(self, *_):
        """Destroy and close the toast window."""
        try:
            alpha = float(self.toplevel.attributes("-alpha"))
            if alpha <= 0.1:
                self.toplevel.destroy()
            else:
                self.toplevel.attributes("-alpha", alpha - 0.1)
                self.toplevel.after(25, self.hide_toast)
        except:
            if self.toplevel:
                self.toplevel.destroy()

    def _setup(self, window: ttk.Toplevel):
        winsys = window.tk.call("tk", "windowingsystem")

        self.toplevel.configure(relief=RAISED)

        # minsize
        if "minsize" not in self.kwargs:
            w, h = utility.scale_size(self.toplevel, [300, 75])
            self.toplevel.minsize(w, h)

        # heading font
        _font = font.nametofont("TkDefaultFont")
        self.titlefont = font.Font(
            family=_font["family"],
            size=_font["size"] + 1,
            weight="bold",
        )
        # symbol font
        self.iconfont = font.Font(size=30, weight="bold")
        if winsys == "win32":
            self.iconfont["family"] = "Segoe UI Symbol"
            self.icon = DEFAULT_ICON_WIN32 if self.icon is None else self.icon
            if self.position is None:
                x, y = utility.scale_size(self.toplevel, [5, 50])
                self.position = (x, y, SE)
        elif winsys == "x11":
            self.iconfont["family"] = "FreeSerif"
            self.icon = DEFAULT_ICON if self.icon is None else self.icon
            if self.position is None:
                x, y = utility.scale_size(self.toplevel, [0, 0])
                self.position = (x, y, SE)
        else:
            self.iconfont["family"] = "Apple Symbols"
            self.toplevel.update_idletasks()
            self.icon = DEFAULT_ICON if self.icon is None else self.icon
            if self.position is None:
                x, y = utility.scale_size(self.toplevel, [50, 50])
                self.position = (x, y, NE)

        self.set_geometry()

    def set_geometry(self):
        self.toplevel.update_idletasks()  # actualize geometry
        anchor = self.position[-1]
        x_anchor = "-" if "w" not in anchor else "+"
        y_anchor = "-" if "n" not in anchor else "+"
        screen_w = self.toplevel.winfo_screenwidth() // 2
        screen_h = self.toplevel.winfo_screenheight() // 2
        top_w = self.toplevel.winfo_width() // 2
        top_h = self.toplevel.winfo_height() // 2

        if all(["e" not in anchor, "w" not in anchor]):
            xpos = screen_w - top_w
        else:
            xpos = self.position[0]
        if all(["n" not in anchor, "s" not in anchor]):
            ypos = screen_h - top_h
        else:
            ypos = self.position[1]

        self.toplevel.geometry(f"{x_anchor}{xpos}{y_anchor}{ypos}")

from pathlib import Path
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.style import Bootstyle
from PIL import Image, ImageTk

IMG_PATH = Path(__file__).parent / 'icon'


class CollapsingFrame(ttk.Frame):
    """A collapsible frame widget that opens and closes with a click."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.columnconfigure(0, weight=1)
        self.cumulative_rows = 0

        # widget images
        self.images = [
        #     ImageTk.PhotoImage(file=IMG_PATH/'icons8_double_up_24px.png').resize((16, 16), Image.LANCZOS),
        #     ImageTk.PhotoImage(file=IMG_PATH/'icons8_double_right_24px.png').resize((16, 16), Image.LANCZOS),
            ImageTk.PhotoImage(Image.open(IMG_PATH/'icons8_double_up_24px.png').resize((16, 16), Image.LANCZOS)),
            ImageTk.PhotoImage(Image.open(IMG_PATH/'icons8_double_right_24px.png').resize((16, 16), Image.LANCZOS)),
        ]

    def add(self, child, title="", bootstyle=PRIMARY, **kwargs):
        """Add a child to the collapsible frame

        Parameters:

            child (Frame):
                The child frame to add to the widget.

            title (str):
                The title appearing on the collapsible section header.

            bootstyle (str):
                The style to apply to the collapsible section header.

            **kwargs (Dict):
                Other optional keyword arguments.
        """
        if child.winfo_class() != 'TFrame':
            return
        
        style_color = Bootstyle.ttkstyle_widget_color(bootstyle)
        #style_color = 'info'
        frm = ttk.Frame(self, bootstyle=style_color)
        frm.grid(row=self.cumulative_rows, column=0, sticky=EW)

        # header title
        header = ttk.Label(
            master=frm,
            text=title,
            bootstyle=(style_color, INVERSE)
        )
        if kwargs.get('textvariable'):
            header.configure(textvariable=kwargs.get('textvariable'))
        header.pack(side=LEFT, fill=BOTH, padx=10)

        # header toggle button
        def _func(c=child): 
            return self._toggle_open_close(c)
            
        btn = ttk.Button(
            master=frm,
            image=self.images[0],
            bootstyle=style_color,
            command=_func,
            takefocus=False
        )
        btn.pack(side=RIGHT)

        # assign toggle button to child so that it can be toggled
        child.btn = btn
        child.grid(row=self.cumulative_rows + 1, column=0, sticky=NSEW)

        # increment the row assignment
        self.cumulative_rows += 2
        
        # Default to closed state
        # child.grid_remove()
        # child.btn.configure(image=self.images[1])

    def _toggle_open_close(self, child):
        """Open or close the section and change the toggle button 
        image accordingly.

        Parameters:
            
            child (Frame):
                The child element to add or remove from grid manager.
        """
        if child.winfo_viewable():
            child.grid_remove()
            child.btn.configure(image=self.images[1])
        else:
            child.grid()
            child.btn.configure(image=self.images[0])


    def expand(self, child):
        child.grid()
        child.btn.configure(image=self.images[0])
        self.after(500, self.expand_close, child)

    def expand_close(self, child):
        child.grid_remove()
        child.btn.configure(image=self.images[1])
    