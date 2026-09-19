"""Tk windows; all methods are called on the main thread."""
import time
import tkinter as tk
from tkinter import messagebox


def clamp_geometry(x, y, width, height, screen_width, screen_height):
    width = min(width, screen_width)
    height = min(height, screen_height)
    return (max(0, min(x, screen_width - width)), max(0, min(y, screen_height - height)), width, height)


def ink_for(color):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return '#202d32' if r * .299 + g * .587 + b * .114 > 145 else '#ffffff'


class NoteWindow:
    def __init__(self, desktop, note):
        self.desktop = desktop
        self.id = note['id']
        self.saved_geometry = None
        self.pending = None
        self.last_note = None
        self.window = tk.Toplevel(desktop.root)
        self.window.withdraw()
        self.window.title(note['title'] or 'Sticky note')
        self.window.minsize(220, 160)
        self.window.attributes('-topmost', True)
        self.window.configure(highlightthickness=3)
        self.window.protocol('WM_DELETE_WINDOW', lambda: self.action('visibility', visible=False))
        self.header = tk.Frame(self.window, cursor='fleur')
        self.header.pack(fill='x', padx=10, pady=(8, 0))
        self.title = tk.Label(self.header, anchor='w', font=('Sans', 11, 'bold'), cursor='fleur')
        self.title.pack(side='left', fill='x', expand=True)
        self.hide_button = tk.Button(self.header, text='Hide', command=lambda: self.action('visibility', visible=False),
                                     relief='flat', borderwidth=0, padx=5)
        self.hide_button.pack(side='right', before=self.title)
        self.body = tk.Text(self.window, wrap='word', font=('DejaVu Sans', 12), relief='flat',
                            borderwidth=0, padx=14, pady=14, cursor='arrow', state='disabled',
                            highlightthickness=0, spacing3=5)
        self.body.pack(fill='both', expand=True)
        self.footer = tk.Frame(self.window)
        self.footer.pack(side='bottom', fill='x', padx=10, pady=(0, 8), before=self.body)
        self.edit_button = tk.Button(self.footer, text='Edit', relief='flat', borderwidth=0,
                                     command=lambda: desktop.open_editor(self.id))
        self.edit_button.pack(side='left')
        self.status = tk.Label(self.footer, font=('Sans', 9), anchor='w')
        self.status.pack(side='left', padx=5)
        self.grip = tk.Label(self.footer, text='◢', cursor='bottom_right_corner')
        self.grip.pack(side='right')
        self.alert_bar = tk.Frame(self.window)
        self.dismiss_button = tk.Button(self.alert_bar, text='Dismiss', relief='flat',
                                        command=lambda: self.action('dismiss'))
        self.dismiss_button.pack(side='left', padx=6, pady=5)
        self.snooze_button = tk.Button(self.alert_bar, text='Snooze 5 min', relief='flat',
                                       command=lambda: self.action('snooze'))
        self.snooze_button.pack(side='left', padx=6, pady=5)
        for widget in (self.header, self.title):
            widget.bind('<ButtonPress-1>', self.start_drag)
            widget.bind('<B1-Motion>', self.drag)
        self.grip.bind('<ButtonPress-1>', self.start_resize)
        self.grip.bind('<B1-Motion>', self.resize)
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        x, y, width, height = clamp_geometry(note['x'], note['y'], note['width'], note['height'], sw, sh)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
        self.window.bind('<Configure>', self.configured)
        self.update(note)

    def action(self, command, **payload):
        self.desktop.action(command, {'id': self.id, **payload})

    def start_drag(self, event):
        self.drag_origin = (event.x_root, event.y_root, self.window.winfo_x(), self.window.winfo_y())

    def drag(self, event):
        sx, sy, x, y = self.drag_origin
        x, y = max(0, x + event.x_root - sx), max(0, y + event.y_root - sy)
        self.window.geometry(f'+{x}+{y}')

    def start_resize(self, event):
        self.resize_origin = (event.x_root, event.y_root, self.window.winfo_width(), self.window.winfo_height())

    def resize(self, event):
        sx, sy, width, height = self.resize_origin
        self.window.geometry(f'{max(220, width + event.x_root - sx)}x{max(160, height + event.y_root - sy)}')

    def configured(self, event):
        if event.widget is self.window and self.window.state() != 'withdrawn':
            if self.pending:
                self.window.after_cancel(self.pending)
            self.pending = self.window.after(300, self.save_geometry)

    def save_geometry(self):
        if self.pending:
            self.window.after_cancel(self.pending)
            self.pending = None
        if self.window.winfo_width() < 220 or self.window.winfo_height() < 160:
            return
        geometry = dict(x=self.window.winfo_x(), y=self.window.winfo_y(),
                        width=self.window.winfo_width(), height=self.window.winfo_height())
        if geometry != self.saved_geometry:
            self.desktop.store.execute('geometry', {'id': self.id, **geometry}, time.time())
            self.saved_geometry = geometry

    def update(self, note):
        if note == self.last_note:
            return
        self.last_note = note.copy()
        color, ink = note['color'], ink_for(note['color'])
        border = '#ce6522' if note['alert'] else color
        self.window.configure(background=color, highlightbackground=border, highlightcolor=border)
        self.window.title(note['title'] or 'Sticky note')
        for widget in (self.header, self.footer, self.alert_bar):
            widget.configure(background=color)
        for widget in (self.title, self.status, self.grip):
            widget.configure(background=color, foreground=ink)
        for widget in (self.hide_button, self.edit_button, self.dismiss_button, self.snooze_button):
            widget.configure(background=color, foreground=ink, activebackground=color, activeforeground=ink)
        self.title.configure(text=note['title'] or 'Sticky note')
        self.body.configure(background=color, foreground=ink)
        if self.body.get('1.0', 'end-1c') != note['body']:
            self.body.configure(state='normal')
            self.body.delete('1.0', 'end')
            self.body.insert('1.0', note['body'])
            self.body.configure(state='disabled')
        self.status.configure(text='Reminder!' if note['alert'] else
                              time.strftime('%b %d, %H:%M', time.localtime(note['deadline'])) if note['deadline'] else '')
        if note['alert']:
            self.alert_bar.pack(side='bottom', fill='x', before=self.body)
        else:
            self.alert_bar.pack_forget()
        if note['visible']:
            if self.window.state() == 'withdrawn':
                self.window.deiconify()
        else:
            self.window.withdraw()

    def destroy(self):
        if self.pending:
            self.window.after_cancel(self.pending)
        self.window.destroy()


class Desktop:
    def __init__(self, root, store, open_editor):
        self.root, self.store, self.open_editor = root, store, open_editor
        self.windows = {}

    def action(self, command, payload):
        try:
            self.store.execute(command, payload, time.time())
            self.refresh()
        except (OSError, ValueError) as error:
            messagebox.showerror('Could not save note', str(error), parent=self.root)

    def refresh(self, alert_ids=()):
        notes = self.store.snapshot()
        present = {note['id'] for note in notes}
        for identifier in list(self.windows):
            if identifier not in present:
                self.windows.pop(identifier).destroy()
        for note in notes:
            if note['id'] not in self.windows:
                self.windows[note['id']] = NoteWindow(self, note)
            else:
                self.windows[note['id']].update(note)
        for identifier in alert_ids:
            self.windows[identifier].window.lift()
        if alert_ids:
            self.root.bell()

    def close(self):
        for window in self.windows.values():
            window.save_geometry()
        for window in self.windows.values():
            window.destroy()
        self.windows.clear()
