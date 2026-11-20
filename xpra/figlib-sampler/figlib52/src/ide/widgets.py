import tkinter as tk
import math

class DraggableWidget:
    def __init__(self, canvas, widget_id, target, default_val, x, y, move_callback=None, display_name=None):
        self.canvas = canvas
        self.widget_id = widget_id
        self.target = target
        self.display_name = display_name if display_name else target
        self.value = default_val
        self.x = x
        self.y = y
        self.move_callback = move_callback
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.lock_check = None # Callback to check if dragging is locked
        self.rand_range = None # (min, max) tuple if set
        
    def make_draggable(self, tag):
        self.canvas.tag_bind(tag, "<ButtonPress-1>", self.on_drag_start)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag_motion)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_drag_end)
        
    def on_drag_start(self, event):
        if self.lock_check and self.lock_check():
            return
        self.drag_data["item"] = self.canvas.find_withtag("current")[0]
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def on_drag_motion(self, event):
        if not self.drag_data["item"]: return
        if self.lock_check and self.lock_check():
            return
            
        delta_x = event.x - self.drag_data["x"]
        delta_y = event.y - self.drag_data["y"]
        self.move_by(delta_x, delta_y)
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y

    def move_by(self, dx, dy):
        self.canvas.move(self.widget_id, dx, dy)
        self.x += dx
        self.y += dy

    def on_drag_end(self, event):
        if not self.drag_data["item"]: return
        self.drag_data["item"] = None
        if self.move_callback:
            self.move_callback(self.target, self.x, self.y)

class CanvasSlider(DraggableWidget):
    def __init__(self, canvas, x, y, width, target, min_val, max_val, default_val, move_callback=None, display_name=None):
        group_tag = f"group_slider_{id(self)}"
        super().__init__(canvas, group_tag, target, default_val, x, y, move_callback, display_name)
        self.min_val = min_val
        self.max_val = max_val
        self.width = width
        self.height = 15
        
        # Pure Data Style: White box with thin black border
        self.track_id = self.canvas.create_rectangle(
            x, y, x + width, y + self.height, 
            fill="white", outline="black", width=1, tags=(group_tag, "track")
        )
        
        # Calculate handle position
        pct = (default_val - min_val) / (max_val - min_val) if max_val > min_val else 0
        h_x = x + (width * pct)
        
        # Handle: Narrow black bar
        self.handle_id = self.canvas.create_rectangle(
            h_x - 1, y, h_x + 1, y + self.height,
            fill="black", outline="black", tags=(group_tag, "handle")
        )
        
        # Label: Monospaced
        label_text = f"{self.display_name}: {default_val:.2f}"
        self.label_id = self.canvas.create_text(
            x, y - 8, text=label_text, fill="black", anchor=tk.W, font=("Consolas", 8), tags=(group_tag, "label")
        )
        
        self.make_draggable(self.track_id)
        self.make_draggable(self.label_id)
        
        self.canvas.tag_bind(self.handle_id, "<B1-Motion>", self.on_slide)
        self.canvas.tag_bind(self.track_id, "<Button-1>", self.on_click_track)

    def update_value(self, event_x):
        coords = self.canvas.coords(self.track_id)
        rx = coords[0]
        rw = coords[2] - coords[0]
        new_x = max(rx, min(event_x, rx + rw))
        
        hx1, hy1, hx2, hy2 = self.canvas.coords(self.handle_id)
        self.canvas.coords(self.handle_id, new_x - 1, hy1, new_x + 1, hy2)
        
        pct = (new_x - rx) / rw
        self.value = self.min_val + (pct * (self.max_val - self.min_val))
        self.canvas.itemconfig(self.label_id, text=f"{self.display_name}: {self.value:.2f}")
        
    def on_slide(self, event):
        self.update_value(event.x)
        
    def on_click_track(self, event):
        self.update_value(event.x)


class CanvasKnob(DraggableWidget):
    def __init__(self, canvas, x, y, radius, target, min_val, max_val, default_val, move_callback=None, display_name=None):
        group_tag = f"group_knob_{id(self)}"
        super().__init__(canvas, group_tag, target, default_val, x, y, move_callback, display_name)
        self.min_val = min_val
        self.max_val = max_val
        self.radius = radius
        self.r = radius # Alias for interpreter consistency
        
        # Pure Data Style: Minimalist white circle with black outline
        self.bg_id = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill="white", outline="black", width=1, tags=(group_tag, "knob_bg")
        )
        
        # Thin black indicator line
        self.line_id = self.canvas.create_line(x, y, x, y-radius, fill="black", width=1, tags=(group_tag, "knob_line"))
        self.update_indicator(default_val, x, y)
        
        # Monospaced label
        label_text = f"{self.display_name}\n{default_val:.2f}"
        self.label_id = self.canvas.create_text(
            x, y + radius + 12, text=label_text, fill="black", justify=tk.CENTER, font=("Consolas", 8), tags=(group_tag, "label")
        )
        
        self.make_draggable(group_tag)
        self.canvas.tag_bind(self.bg_id, "<ButtonPress-1>", self.on_knob_press)
        self.canvas.tag_bind(self.bg_id, "<B1-Motion>", self.on_knob_drag)
        self.last_y = 0

    def update_indicator(self, val, cx=None, cy=None):
        if cx is None or cy is None:
            coords = self.canvas.coords(self.bg_id)
            cx = (coords[0] + coords[2]) / 2
            cy = (coords[1] + coords[3]) / 2
        pct = (val - self.min_val) / (self.max_val - self.min_val) if self.max_val > self.min_val else 0
        angle_deg = 225 - (pct * 270)
        angle_rad = math.radians(angle_deg)
        r_actual = self.radius * 0.9
        x2 = cx + r_actual * math.cos(angle_rad)
        y2 = cy - r_actual * math.sin(angle_rad)
        self.canvas.coords(self.line_id, cx, cy, x2, y2)

    def on_knob_press(self, event):
        self.last_y = event.y
        self.on_drag_start(event)

    def on_knob_drag(self, event):
        dy = self.last_y - event.y
        self.last_y = event.y
        pct_change = dy * 0.01 
        current_pct = (self.value - self.min_val) / (self.max_val - self.min_val)
        new_pct = max(0.0, min(1.0, current_pct + pct_change))
        self.value = self.min_val + (new_pct * (self.max_val - self.min_val))
        self.update_indicator(self.value)
        self.canvas.itemconfig(self.label_id, text=f"{self.display_name}\n{self.value:.2f}")

class CanvasButton(DraggableWidget):
    def __init__(self, canvas, x, y, width, height, label, command=None, move_callback=None):
        group_tag = f"group_btn_{id(self)}"
        super().__init__(canvas, group_tag, label, None, x, y, move_callback)
        self.command = command
        
        # Pure Data Style: White rectangle with black outline
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill="white", outline="black", width=1, tags=(group_tag, "btn_bg")
        )
        self.label_id = self.canvas.create_text(
            x + width/2, y + height/2, text=label, fill="black", font=("Consolas", 9, "bold"), tags=(group_tag, "label")
        )
        
        self.make_draggable(group_tag)
        self.canvas.tag_bind(self.bg_id, "<ButtonRelease-1>", self.on_btn_release)
        self.canvas.tag_bind(self.label_id, "<ButtonRelease-1>", self.on_btn_release)
        self.press_pos = (0, 0)
        self.canvas.tag_bind(group_tag, "<ButtonPress-1>", self.on_btn_press, add="+")

    def on_btn_press(self, event):
        self.press_pos = (event.x, event.y)

    def on_btn_release(self, event):
        self.on_drag_end(event)
        dist = math.sqrt((event.x - self.press_pos[0])**2 + (event.y - self.press_pos[1])**2)
        if dist < 5 and self.command:
            self.command()

class BusContainer(DraggableWidget):
    def __init__(self, canvas, x, y, w, h, bus_id, color="#ffffff", move_callback=None):
        group_tag = f"group_bus_{id(self)}"
        super().__init__(canvas, group_tag, bus_id, None, x, y, move_callback)
        self.w = w
        self.h = h
        
        # Pure Data Style: Outline only
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill="", outline="black", width=1, dash=(2, 2), tags=(group_tag, "bus_bg")
        )
        
        # Monospaced label in upper left
        self.label_id = self.canvas.create_text(
            x + 5, y + 8, text=f"bus {bus_id}", fill="black", anchor=tk.W, font=("Consolas", 8, "italic"), tags=(group_tag, "label")
        )
        self.make_draggable(group_tag)

    def move_by(self, dx, dy):
        super().move_by(dx, dy)
        if hasattr(self, 'children'):
            for child in self.children:
                child.move_by(dx, dy)

    def on_drag_motion(self, event):
        # We use the standard DraggableWidget motion which now calls move_by
        super().on_drag_motion(event)

    def resize(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.canvas.coords(self.bg_id, x, y, x + w, y + h)
        self.canvas.coords(self.label_id, x + 5, y + 8)

class CanvasTextbox(DraggableWidget):
    def __init__(self, canvas, x, y, width, height, target, default_val, move_callback=None, display_name=None):
        group_tag = f"group_txt_{id(self)}"
        super().__init__(canvas, group_tag, target, default_val, x, y, move_callback, display_name)
        self.w = width
        self.h = height
        
        # Pure Data Style: White box with thin black border
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill="white", outline="black", width=1, tags=(group_tag, "txt_bg")
        )
        
        # Label: Monospaced
        self.label_id = self.canvas.create_text(
            x, y - 8, text=self.display_name, fill="black", anchor=tk.W, font=("Consolas", 8), tags=(group_tag, "label")
        )
        
        # Embed a tk.Entry
        self.entry_var = tk.StringVar(value=default_val)
        self.entry = tk.Entry(self.canvas, textvariable=self.entry_var, bg="white", fg="black", 
                             insertbackground="black", relief=tk.FLAT, font=("Consolas", 9), borderwidth=0)
        self.entry.bind("<KeyRelease>", self.on_text_change)
        
        self.window_id = self.canvas.create_window(
            x + 1, y + 1, anchor=tk.NW, window=self.entry, width=width-2, height=height-2, tags=(group_tag, "txt_entry")
        )
        
        self.make_draggable(self.label_id)
        self.make_draggable(self.bg_id)

    def on_text_change(self, event):
        self.value = self.entry_var.get()

    def get_text(self):
        """Return the current text value."""
        return self.entry_var.get()

    def on_drag_motion(self, event):
        super().on_drag_motion(event)

class CanvasDropdown(DraggableWidget):
    def __init__(self, canvas, x, y, width, height, target, default_val, choices, move_callback=None, display_name=None):
        group_tag = f"group_drop_{id(self)}"
        super().__init__(canvas, group_tag, target, default_val, x, y, move_callback, display_name)
        self.w = width
        self.h = height
        self.choices = choices
        
        # Pure Data Style: White box with thin black border
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill="white", outline="black", width=1, tags=(group_tag, "drop_bg")
        )
        
        # Arrow indicator (minimalist)
        self.arrow_id = self.canvas.create_text(
            x + width - 10, y + height/2, text="v", fill="black", font=("Consolas", 8), tags=(group_tag, "arrow")
        )
        
        # Current selection text
        self.text_id = self.canvas.create_text(
            x + 5, y + height/2, text=default_val, fill="black", anchor=tk.W, font=("Consolas", 9), tags=(group_tag, "drop_text")
        )
        
        # Label: Monospaced above
        self.label_id = self.canvas.create_text(
            x, y - 8, text=self.display_name, fill="black", anchor=tk.W, font=("Consolas", 8), tags=(group_tag, "label")
        )
        
        self.make_draggable(self.label_id)
        self.make_draggable(self.bg_id)
        
        self.canvas.tag_bind(self.bg_id, "<Button-1>", self.show_menu)
        self.canvas.tag_bind(self.text_id, "<Button-1>", self.show_menu)
        self.canvas.tag_bind(self.arrow_id, "<Button-1>", self.show_menu)

    def show_menu(self, event):
        if self.lock_check and self.lock_check():
            pass # Allow clicking even when locked or not? Pd allows changing values when "run"
        
        menu = tk.Menu(self.canvas, tearoff=0, font=("Consolas", 9))
        for i, choice in enumerate(self.choices):
            # Add columnbreak every 12 items to avoid vertical overflow on small screens
            break_col = (i > 0 and i % 12 == 0)
            menu.add_command(label=choice, command=lambda c=choice: self.set_selection(c), columnbreak=break_col)
        
        # Get absolute screen coords
        root_x = self.canvas.winfo_rootx() + int(self.x)
        root_y = self.canvas.winfo_rooty() + int(self.y) + self.h
        menu.post(root_x, root_y)

    def set_selection(self, choice):
        self.value = choice
        self.canvas.itemconfig(self.text_id, text=choice)

class CanvasToggle(DraggableWidget):
    def __init__(self, canvas, x, y, size, target, default_val, move_callback=None, display_name=None):
        group_tag = f"group_tog_{id(self)}"
        # Convert default_val to bool
        if isinstance(default_val, str):
             initial_val = default_val.lower() == 'true'
        else:
             initial_val = bool(default_val)
             
        super().__init__(canvas, group_tag, target, initial_val, x, y, move_callback, display_name)
        self.size = size
        
        # Outer box
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + size, y + size,
            fill="white", outline="black", width=1, tags=(group_tag, "tog_bg")
        )
        
        # The 'X' mark
        self.x_id1 = self.canvas.create_line(x+2, y+2, x+size-2, y+size-2, fill="black", width=2, state=tk.NORMAL if initial_val else tk.HIDDEN, tags=(group_tag, "tog_x"))
        self.x_id2 = self.canvas.create_line(x+size-2, y+2, x+2, y+size-2, fill="black", width=2, state=tk.NORMAL if initial_val else tk.HIDDEN, tags=(group_tag, "tog_x"))
        
        # Label: Monospaced
        self.label_id = self.canvas.create_text(
            x + size + 5, y + size/2, text=self.display_name, fill="black", anchor=tk.W, font=("Consolas", 8), tags=(group_tag, "label")
        )
        
        self.make_draggable(self.label_id)
        self.make_draggable(self.bg_id)
        
        self.canvas.tag_bind(self.bg_id, "<Button-1>", self.on_click)

    def on_click(self, event):
        if self.lock_check and self.lock_check():
             pass # In Pd you can click values even in runtime
        self.value = not self.value
        state = tk.NORMAL if self.value else tk.HIDDEN
        self.canvas.itemconfig(self.x_id1, state=state)
        self.canvas.itemconfig(self.x_id2, state=state)
        # Call move_callback or similar to trigger sync?
        if self.move_callback:
             self.move_callback(self.target, self.x, self.y)

class CanvasSampleBrowser(DraggableWidget):
    """
    A unified widget that displays a scrollable list of WAV files in a folder,
    with play/stop options using the low-latency sounddevice library.
    """
    def __init__(self, canvas, x, y, width, height, target, default_val, move_callback=None, display_name=None):
        group_tag = f"group_browser_{id(self)}"
        super().__init__(canvas, group_tag, target, default_val, x, y, move_callback, display_name)
        self.w = width
        self.h = height
        self.folder = default_val
        self.files = []
        self._playing = False
        self._sd_stream = None

        # Minimalist background box
        self.bg_id = self.canvas.create_rectangle(
            x, y, x + width, y + height,
            fill="#e8f4fc", outline="#3498db", width=1, tags=(group_tag, "browser_bg")
        )

        # Header bar
        header_h = 24
        self.header_id = self.canvas.create_rectangle(
            x, y, x + width, y + header_h,
            fill="#3498db", outline="black", width=0, tags=(group_tag, "browser_hdr")
        )
        
        # Label: Title
        self.label_id = self.canvas.create_text(
            x + 5, y + header_h/2, text=f"Samples ({self.display_name})", fill="white",
            anchor=tk.W, font=("Consolas", 8, "bold"), tags=(group_tag, "label")
        )
        
        # Make the header and label draggable
        self.make_draggable(self.bg_id)
        self.make_draggable(self.header_id)
        self.make_draggable(self.label_id)

        # Main Listbox frame to sit on canvas
        self.frame = tk.Frame(self.canvas, bg="white")
        self.scrollbar = tk.Scrollbar(self.frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(
            self.frame, font=("Consolas", 9), yscrollcommand=self.scrollbar.set,
            selectbackground="#3498db", selectforeground="white",
            activestyle="none", highlightthickness=0, bd=0
        )
        self.scrollbar.config(command=self.listbox.yview)
        
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox.bind("<Double-Button-1>", self.on_double_click)

        # Embed the frame inside the canvas window
        list_y = y + header_h + 2
        list_h = height - header_h - 32 # Leave room for controls at bottom
        self.window_id = self.canvas.create_window(
            x + 2, list_y, anchor=tk.NW, window=self.frame, 
            width=width - 4, height=list_h, tags=(group_tag, "browser_list")
        )

        # Controls at bottom
        ctrl_y = y + height - 26
        
        self.play_btn_id = self.canvas.create_rectangle(
            x + 4, ctrl_y, x + 64, ctrl_y + 22, fill="#2ecc71", outline="#27ae60",
            tags=(group_tag, "browser_play")
        )
        self.play_txt_id = self.canvas.create_text(
            x + 34, ctrl_y + 11, text="▶ Play", fill="white", font=("Consolas", 8, "bold"),
            tags=(group_tag, "browser_play_txt")
        )
        
        self.stop_btn_id = self.canvas.create_rectangle(
            x + 68, ctrl_y, x + 128, ctrl_y + 22, fill="#e74c3c", outline="#c0392b",
            tags=(group_tag, "browser_stop")
        )
        self.stop_txt_id = self.canvas.create_text(
            x + 98, ctrl_y + 11, text="■ Stop", fill="white", font=("Consolas", 8, "bold"),
            tags=(group_tag, "browser_stop_txt")
        )

        # Bind clicks
        self.canvas.tag_bind(self.play_btn_id, "<ButtonPress-1>", self.play_selected)
        self.canvas.tag_bind(self.play_txt_id, "<ButtonPress-1>", self.play_selected)
        self.canvas.tag_bind(self.stop_btn_id, "<ButtonPress-1>", self.stop_playback)
        self.canvas.tag_bind(self.stop_txt_id, "<ButtonPress-1>", self.stop_playback)

        self.refresh()

    def refresh(self):
        """Scan the folder and update the listbox."""
        import os, glob
        self.listbox.delete(0, tk.END)
        self.files = []
        
        if not self.folder or not os.path.isdir(self.folder):
            self.listbox.insert(tk.END, " (Empty/Invalid Folder)")
            return
            
        wavs = sorted(glob.glob(os.path.join(self.folder, "*.wav")), key=os.path.getmtime, reverse=True)
        self.files = wavs
        
        if not wavs:
            self.listbox.insert(tk.END, " (No WAV files)")
            return
            
        for f in wavs:
            self.listbox.insert(tk.END, " " + os.path.basename(f))

    def on_double_click(self, event):
        self.play_selected(event)

    def play_selected(self, event=None):
        sel = self.listbox.curselection()
        if not sel or not self.files: return
        idx = sel[0]
        if idx >= len(self.files): return
        
        filepath = self.files[idx]
        self.stop_playback() # Stop existing
        
        try:
            import sounddevice as sd
            import soundfile as sf
            data, fs = sf.read(filepath)
            sd.play(data, fs)
            self._playing = True
        except Exception as e:
            print(f"[IDE] Error playing audio: {e}")

    def stop_playback(self, event=None):
        if self._playing:
            try:
                import sounddevice as sd
                sd.stop()
            except: pass
            self._playing = False

    def on_drag_motion(self, event):
        super().on_drag_motion(event)


