import tkinter as tk
from tkinter import ttk
from typing import Optional

class AmendmentController:
    def __init__(self, session, path: str = "autosave.json"):
        self.session = session
        self.source_path=path
    def next(self):
        self.session.next()

    def prev(self):
        self.session.previous()

    def toggle_friendly(self):
        self.session.toggle_friendly()

    def save(self, path="autosave.json"):
        self.session.save(path)


class AmendmentSlide(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=20)

        self.title_var = tk.StringVar()
        self.context_var = tk.StringVar()
        self.action_var = tk.StringVar()
        self.reason_var = tk.StringVar()
        self.footer_var = tk.StringVar()
        self.badge_var = tk.StringVar()
        self.save_status = tk.StringVar()
        
        
        self._build()
    
    def _build(self):
        # Configure column 0 to expand and add horizontal padding (margins)
        self.columnconfigure(0, weight=1)
        
        # Configure row 3 (or 4) to take up all remaining vertical space
        # This pushes row 5 (the footer) to the absolute bottom
        self.rowconfigure(3, weight=1)
        

        # Adding a master padding to the grid call or the frame itself 
        # handles the "left and right margins"
        layout_padding = {'padx': 80, 'sticky': "ew"}

        self.title = ttk.Label(
            self,
            textvariable=self.title_var,
            font=("Segoe UI", 34, "bold"),
            anchor="center",
            foreground="#0A4D7F"
        )
        self.title.grid(row=0, column=0, pady=(50, 20), **layout_padding)

        self.badge = ttk.Label(
            self,
            textvariable=self.badge_var,
            font=("Segoe UI", 16, "bold")
        )
        # Sticky 'e' keeps it to the right within the margined column
        self.badge.grid(row=1, column=0, sticky="e", padx=40)

        self.context = ttk.Label(
            self,
            textvariable=self.context_var,
            wraplength=1200,
            font=("Segoe UI", 18, "italic")
        )
        self.context.grid(row=2, column=0, pady=20, **layout_padding)

        self.action = ttk.Label(
            self,
            textvariable=self.action_var,
            wraplength=1200,
            font=("Segoe UI", 24)
        )
        # This row has weight=1, so it will expand vertically
        self.action.grid(row=3, column=0, pady=20, **layout_padding)

        self.reason = ttk.Label(
            self,
            textvariable=self.reason_var,
            wraplength=1200,
            font=("Segoe UI", 18)
        )
        self.reason.grid(row=4, column=0, pady=10, **layout_padding)

        self.footer = ttk.Label(
            self,
            textvariable=self.footer_var,
            font=("Segoe UI", 14),
            anchor="e"
        )
        # Sticky 'se' (South-East) ensures it stays at the bottom right
        self.footer.grid(row=5, column=0, sticky="se", padx=40, pady=(30, 20))
        
        
    def render(self, session):
        amendment = session.current()

        clause_path = amendment.clause
        if amendment.sub_clause:
            clause_path += f".{amendment.sub_clause}"
        if amendment.sub_sub_clause:
            clause_path += f".{amendment.sub_sub_clause}"

        self.title_var.set(
            f"{amendment.submitter_delegate} — {amendment.amendment_type.value} {clause_path}"
        )

        badge = amendment.amendment_type.value
        if amendment.friendly:
            badge += " | FRIENDLY"
        self.badge_var.set(badge)

        self.context_var.set(amendment.context)

        if amendment.amendment_type == amendment.amendment_type.ADD:
            self.action_var.set(f"Add:\n{amendment.text}")
        elif amendment.amendment_type == amendment.amendment_type.AMEND:
            self.action_var.set(f"Replace with:\n{amendment.text}")
        else:
            self.action_var.set("Strike the above clause.")

        self.reason_var.set(
            f"Reason:\n{amendment.reason}" if amendment.reason else ""
        )

        self.footer_var.set(
            f"{session.committee} | {session.current_index + 1} / {len(session.amendments)} {self.save_status.get()}"
        )

class AmendmentApp(tk.Tk):
    def __init__(self, session):
        super().__init__()

        self.session = session
        self.controller = AmendmentController(session)
        self.source_path = session.source_path

        self.attributes("-fullscreen", False)
        self.configure(background="black")

        self.slide = AmendmentSlide(self)
        self.slide.pack(expand=True, fill="both")

        self._bind_keys()
        self._refresh()
        
    def _bind_keys(self):
        self.bind("<Right>", self._next)
        self.bind("<Down>", self._next)
        self.bind("<Left>", self._prev)
        self.bind("<Up>", self._prev)

        self.bind("f", self._toggle_friendly)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", self.save_to_source)
        self.bind("<Control-S>", self.save_to_source)
        
    def _next(self, event=None):
        self.controller.next()
        self._refresh()

    def _prev(self, event=None):
        self.controller.prev()
        self._refresh()

    def _toggle_friendly(self, event=None):
        self.controller.toggle_friendly()
        self.slide.save_status.set(" [*]")
        self.controller.save()
        self._refresh()
        

    def _refresh(self):
        self.slide.render(self.session)
    def save_to_source(self, event=None):
        if not self.source_path:
            raise RuntimeError("No source file to overwrite.")
        self.controller.save(self.session.source_path)
        self.slide.save_status.set("")
        self._refresh()
