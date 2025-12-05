import tkinter as tk
from src.constants import THEME

class OverlayManager:
    def __init__(self, root, config_manager, on_update_callback=None):
        self.root = root
        self.config_manager = config_manager
        self.on_update_callback = on_update_callback
        
        self.overlay_windows = []
        self.active = False
        self.dragging = False
        self.drag_start = None
        self.dragging_overlay = None

    def toggle(self):
        if self.active:
            self.hide()
        else:
            self.show()

    def hide(self):
        for overlay in self.overlay_windows:
            if overlay:
                # Destroy label window if it exists
                if hasattr(overlay, 'label_win') and overlay.label_win:
                    try:
                        overlay.label_win.destroy()
                    except:
                        pass
                # Destroy overlay
                try:
                    overlay.destroy()
                except:
                    pass
        self.overlay_windows = []
        self.active = False

    def show(self):
        self.hide() # Cleanup first
        self.active = True
        
        # Color coding
        colors = {
            "nickname": THEME['accent_cyan'],
            "single_high": '#10b981',
            "total_score": '#f59e0b'
        }
        
        rows = self.config_manager.get("rows", [])
        
        for row_idx, row_data in enumerate(rows):
            for col_name in ["nickname", "single_high", "total_score"]:
                if col_name not in row_data:
                    continue
                    
                bbox = row_data[col_name]
                x, y, w, h = bbox
                
                # Create text label window
                label_height = 20
                label_win = tk.Toplevel(self.root)
                label_win.geometry(f"{w}x{label_height}+{x}+{y-label_height-2}")
                label_win.overrideredirect(True)
                label_win.attributes('-alpha', 0.8)
                label_win.attributes('-topmost', True)
                
                color = colors.get(col_name, '#ffffff')
                col_short = {"nickname": "Nick", "single_high": "Single", "total_score": "Total"}
                label_text = f"R{row_idx+1} {col_short.get(col_name, col_name)}"
                
                label_frame = tk.Frame(label_win, bg=color)
                label_frame.pack(fill=tk.BOTH, expand=True)
                
                tk.Label(label_frame, text=label_text,
                        bg=color, fg=THEME['bg_dark'],
                        font=("Segoe UI", 8, "bold")).pack()
                
                # Create overlay window
                overlay = tk.Toplevel(self.root)
                overlay.geometry(f"{w}x{h}+{x}+{y}")
                overlay.overrideredirect(True)
                overlay.attributes('-alpha', 0.15)
                overlay.attributes('-topmost', True)
                
                # Colored background
                frame = tk.Frame(overlay, bg=color, width=w, height=h, cursor="fleur")
                frame.pack(fill=tk.BOTH, expand=True)
                
                # Store references
                overlay.row_idx = row_idx
                overlay.col_name = col_name
                overlay.label_win = label_win
                
                # Bind drag events
                frame.bind('<Button-1>', lambda e, o=overlay: self.start_drag(e, o))
                frame.bind('<B1-Motion>', lambda e, o=overlay: self.do_drag(e, o))
                frame.bind('<ButtonRelease-1>', lambda e, o=overlay: self.end_drag(e, o))
                
                self.overlay_windows.append(overlay)

    def start_drag(self, event, overlay):
        self.dragging = True
        self.drag_start = (event.x_root, event.y_root)
        self.dragging_overlay = overlay
        overlay.drag_moved = False

    def do_drag(self, event, overlay):
        if not self.dragging or self.dragging_overlay != overlay:
            return
        
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        
        if abs(dx) > 3 or abs(dy) > 3:
            overlay.drag_moved = True
        
        # Get current rows config ref
        rows = self.config_manager.get("rows")
        bbox = rows[overlay.row_idx][overlay.col_name]
        
        new_x = bbox[0] + dx
        new_y = bbox[1] + dy
        
        # Update config directly (referenced list)
        rows[overlay.row_idx][overlay.col_name] = [new_x, new_y, bbox[2], bbox[3]]
        
        # Move windows
        overlay.geometry(f"+{new_x}+{new_y}")
        if hasattr(overlay, 'label_win') and overlay.label_win:
            overlay.label_win.geometry(f"+{new_x}+{new_y-22}")
        
        # Callback to update UI entries if needed
        if self.on_update_callback:
            self.on_update_callback(overlay.row_idx, overlay.col_name)
            
        self.drag_start = (event.x_root, event.y_root)

    def end_drag(self, event, overlay):
        if self.dragging and self.dragging_overlay == overlay:
            # If clicked but not moved, maybe select it in UI
            if not getattr(overlay, 'drag_moved', False):
                if self.on_update_callback:
                    self.on_update_callback(overlay.row_idx, overlay.col_name, select=True)
        
        self.dragging = False
        # Save config after drag end? Or wait for explicit save?
        # Original code didn't save on drag end, only on "Save Config" button.
