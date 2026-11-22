"""Графический интерфейс LabTrack (Tkinter)."""
import datetime
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from analysis import parse_number, parse_pairs, summary_lines
from reports import collect, export_docx, export_pdf

DATE_FORMAT = "%d.%m.%Y"


def parse_date(text):
    try:
        return datetime.datetime.strptime(text.strip(), DATE_FORMAT).date()
    except ValueError:
        return None


class App(tk.Tk):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.lab_id = None
        self.title("LabTrack — лабораторные работы")
        self.geometry("1120x700")
        self.minsize(940, 580)
        self._build_ui()
        self.refresh_labs()

    # ------------------------------------------------------------ каркас
    def _build_ui(self):
        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Лабораторные работы", font=("", 11, "bold")).pack(anchor="w")
        self.labs_tree = ttk.Treeview(left, columns=("title", "progress"),
                                      show="headings", selectmode="browse", height=24)
        self.labs_tree.heading("title", text="Название")
        self.labs_tree.heading("progress", text="Этапы")
        self.labs_tree.column("title", width=200)
        self.labs_tree.column("progress", width=60, anchor="center")
        self.labs_tree.tag_configure("overdue", foreground="#c0392b")
        self.labs_tree.pack(fill="y", expand=True, pady=6)
        self.labs_tree.bind("<<TreeviewSelect>>", self.on_select_lab)
        btns = ttk.Frame(left)
        btns.pack(fill="x")
        ttk.Button(btns, text="Новая", command=self.new_lab).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="Удалить", command=self.delete_lab).pack(side="left", expand=True, fill="x")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        self._build_info_tab()
        self._build_steps_tab()
        self._build_data_tab()
        self._build_analysis_tab()
        self._build_report_tab()
        self._set_enabled(False)

    def _build_info_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Описание")
        self.vars = {}
        fields = [("title", "Название"), ("subject", "Предмет"),
                  ("deadline", "Срок сдачи (ДД.ММ.ГГГГ)"),
                  ("x_name", "Величина X (название)"), ("x_unit", "Единица X"),
                  ("y_name", "Величина Y (название)"), ("y_unit", "Единица Y")]
        for row, (key, label) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=3)
            self.vars[key] = tk.StringVar()
            ttk.Entry(tab, textvariable=self.vars[key], width=50).grid(
                row=row, column=1, sticky="we", padx=8)
        ttk.Label(tab, text="Описание и цель работы").grid(row=len(fields), column=0, sticky="nw", pady=3)
        self.desc_text = tk.Text(tab, height=10, width=50, wrap="word")
        self.desc_text.grid(row=len(fields), column=1, sticky="nsew", padx=8, pady=3)
        ttk.Button(tab, text="Сохранить", command=self.save_info).grid(
            row=len(fields) + 1, column=1, sticky="e", padx=8, pady=8)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(len(fields), weight=1)

    def _build_steps_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Этапы")
        self.progress = ttk.Progressbar(tab, maximum=100)
        self.progress.pack(fill="x")
        self.progress_label = ttk.Label(tab, text="")
        self.progress_label.pack(anchor="w", pady=(2, 8))
        self.steps_tree = ttk.Treeview(tab, columns=("done", "title"), show="headings",
                                       selectmode="browse")
        self.steps_tree.heading("done", text="✓")
        self.steps_tree.heading("title", text="Этап")
        self.steps_tree.column("done", width=40, anchor="center", stretch=False)
        self.steps_tree.tag_configure("done", foreground="#7f8c8d")
        self.steps_tree.pack(fill="both", expand=True)
        self.steps_tree.bind("<Double-1>", lambda e: self.toggle_step())
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=8)
        self.step_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.step_var)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.add_step())
        ttk.Button(row, text="Добавить этап", command=self.add_step).pack(side="left", padx=4)
        ttk.Button(row, text="Отметить / снять", command=self.toggle_step).pack(side="left")
        ttk.Button(row, text="Удалить", command=self.delete_step).pack(side="left", padx=4)

    def _build_data_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Измерения")
        self.axes_label = ttk.Label(tab, text="")
        self.axes_label.pack(anchor="w", pady=(0, 6))
        self.data_tree = ttk.Treeview(tab, columns=("n", "x", "y"), show="headings",
                                      selectmode="extended")
        for col, text, width in (("n", "№", 50), ("x", "X", 150), ("y", "Y", 150)):
            self.data_tree.heading(col, text=text)
            self.data_tree.column(col, width=width, anchor="center")
        self.data_tree.pack(fill="both", expand=True)
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=8)
        self.x_var, self.y_var = tk.StringVar(), tk.StringVar()
        ttk.Label(row, text="X:").pack(side="left")
        ttk.Entry(row, textvariable=self.x_var, width=12).pack(side="left", padx=4)
        ttk.Label(row, text="Y:").pack(side="left")
        y_entry = ttk.Entry(row, textvariable=self.y_var, width=12)
        y_entry.pack(side="left", padx=4)
        y_entry.bind("<Return>", lambda e: self.add_measurement())
        ttk.Button(row, text="Добавить", command=self.add_measurement).pack(side="left")
        ttk.Button(row, text="Вставить из буфера (Excel)", command=self.paste_measurements).pack(side="left", padx=8)
        ttk.Button(row, text="Удалить выбранные", command=self.delete_measurements).pack(side="right")

    def _build_analysis_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Анализ")
        ttk.Button(tab, text="Рассчитать", command=self.run_analysis).pack(anchor="w")
        self.analysis_text = tk.Text(tab, height=20, wrap="word", state="disabled")
        self.analysis_text.pack(fill="both", expand=True, pady=8)

    def _build_report_tab(self):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text="Отчёт")
        ttk.Label(tab, text="Вывод по работе (попадёт в отчёт)").pack(anchor="w")
        self.concl_text = tk.Text(tab, height=14, wrap="word")
        self.concl_text.pack(fill="both", expand=True, pady=6)
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(row, text="Сохранить вывод", command=self.save_conclusion).pack(side="left")
        ttk.Button(row, text="Экспорт в PDF", command=lambda: self.export("pdf")).pack(side="right")
        ttk.Button(row, text="Экспорт в Word", command=lambda: self.export("docx")).pack(side="right", padx=6)

    def _set_enabled(self, enabled):
        for i in range(self.tabs.index("end")):
            self.tabs.tab(i, state="normal" if enabled else "disabled")

    # ------------------------------------------------------------ список работ
    def refresh_labs(self, select=None):
        """Обновляет список на месте: выделение не сбрасывается, лишних событий нет."""
        labs = self.db.list_labs()
        wanted = {str(lab["id"]) for lab in labs}
        for iid in self.labs_tree.get_children():
            if iid not in wanted:
                self.labs_tree.delete(iid)
        today = datetime.date.today()
        for index, lab in enumerate(labs):
            deadline = parse_date(lab["deadline"]) if lab["deadline"] else None
            finished = lab["total"] > 0 and lab["done"] == lab["total"]
            overdue = deadline is not None and deadline < today and not finished
            iid = str(lab["id"])
            values = (lab["title"], f"{lab['done']}/{lab['total']}")
            tags = ("overdue",) if overdue else ()
            if self.labs_tree.exists(iid):
                self.labs_tree.item(iid, values=values, tags=tags)
                self.labs_tree.move(iid, "", index)
            else:
                self.labs_tree.insert("", index, iid=iid, values=values, tags=tags)
        if select is not None and self.labs_tree.exists(str(select)):
            if self.labs_tree.selection() != (str(select),):
                self.labs_tree.selection_set(str(select))

    def on_select_lab(self, _event=None):
        sel = self.labs_tree.selection()
        if not sel:
            return
        lab_id = int(sel[0])
        if lab_id == self.lab_id:
            return  # эта работа уже открыта, правки в форме не трогаем
        self.lab_id = lab_id
        self.load_lab()

    def new_lab(self):
        lab_id = self.db.add_lab("Новая лабораторная работа")
        self.refresh_labs(select=lab_id)
        self.tabs.select(0)

    def delete_lab(self):
        if self.lab_id is None:
            return
        if not messagebox.askyesno("Удаление", "Удалить работу вместе с этапами и измерениями?"):
            return
        self.db.delete_lab(self.lab_id)
        self.lab_id = None
        self._set_enabled(False)
        self.refresh_labs()

    def load_lab(self):
        lab = self.db.get_lab(self.lab_id)
        if not lab:
            return
        self._set_enabled(True)
        for key, var in self.vars.items():
            var.set(lab[key])
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", lab["description"])
        self.concl_text.delete("1.0", "end")
        self.concl_text.insert("1.0", lab["conclusion"])
        self.refresh_steps()
        self.refresh_measurements()
        self._show_analysis(["Нажмите «Рассчитать»."])

    # ------------------------------------------------------------ описание
    def save_info(self, quiet=False):
        if self.lab_id is None:
            return False
        values = {k: v.get().strip() for k, v in self.vars.items()}
        if not values["title"]:
            messagebox.showwarning("LabTrack", "Укажите название работы.")
            return False
        if values["deadline"] and parse_date(values["deadline"]) is None:
            messagebox.showwarning("LabTrack", "Срок сдачи: формат ДД.ММ.ГГГГ, например 15.12.2026.")
            return False
        values["description"] = self.desc_text.get("1.0", "end").strip()
        self.db.update_lab(self.lab_id, **values)
        self.refresh_labs(select=self.lab_id)
        self.refresh_axes_label()
        if not quiet:
            messagebox.showinfo("LabTrack", "Сохранено.")
        return True

    # ------------------------------------------------------------ этапы
    def refresh_steps(self):
        self.steps_tree.delete(*self.steps_tree.get_children())
        steps = self.db.list_steps(self.lab_id)
        for s in steps:
            self.steps_tree.insert("", "end", iid=str(s["id"]),
                                   values=("✓" if s["done"] else "", s["title"]),
                                   tags=("done",) if s["done"] else ())
        done, total = self.db.progress(self.lab_id)
        self.progress["value"] = 100 * done / total if total else 0
        self.progress_label.config(text=f"Выполнено {done} из {total}")
        self.refresh_labs(select=self.lab_id)

    def add_step(self):
        title = self.step_var.get().strip()
        if title and self.lab_id is not None:
            self.db.add_step(self.lab_id, title)
            self.step_var.set("")
            self.refresh_steps()

    def toggle_step(self):
        sel = self.steps_tree.selection()
        if sel:
            self.db.toggle_step(int(sel[0]))
            self.refresh_steps()

    def delete_step(self):
        sel = self.steps_tree.selection()
        if sel:
            self.db.delete_step(int(sel[0]))
            self.refresh_steps()

    # ------------------------------------------------------------ измерения
    def refresh_axes_label(self):
        lab = self.db.get_lab(self.lab_id)

        def name(n, u, d):
            return f"{n or d}" + (f" ({u})" if u else "")
        self.axes_label.config(
            text=f"X — {name(lab['x_name'], lab['x_unit'], 'не задано')};   "
                 f"Y — {name(lab['y_name'], lab['y_unit'], 'не задано')}")

    def refresh_measurements(self):
        self.refresh_axes_label()
        self.data_tree.delete(*self.data_tree.get_children())
        for i, m in enumerate(self.db.list_measurements(self.lab_id), 1):
            self.data_tree.insert("", "end", iid=str(m["id"]), values=(i, m["x"], m["y"]))

    def add_measurement(self):
        try:
            x, y = parse_number(self.x_var.get()), parse_number(self.y_var.get())
        except ValueError:
            messagebox.showwarning("LabTrack", "Введите числа в поля X и Y.")
            return
        self.db.add_measurements(self.lab_id, [(x, y)])
        self.x_var.set("")
        self.y_var.set("")
        self.refresh_measurements()

    def paste_measurements(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("LabTrack", "Буфер обмена пуст.")
            return
        pairs, bad = parse_pairs(text)
        if not pairs:
            messagebox.showwarning("LabTrack", "В буфере нет пар чисел (два столбца: X и Y).")
            return
        self.db.add_measurements(self.lab_id, pairs)
        self.refresh_measurements()
        if bad:
            messagebox.showinfo("LabTrack", f"Добавлено пар: {len(pairs)}. Пропущено строк: {bad}.")

    def delete_measurements(self):
        for iid in self.data_tree.selection():
            self.db.delete_measurement(int(iid))
        self.refresh_measurements()

    # ------------------------------------------------------------ анализ и отчёт
    def _show_analysis(self, lines):
        self.analysis_text.config(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", "\n".join(lines))
        self.analysis_text.config(state="disabled")

    def run_analysis(self):
        lab = self.db.get_lab(self.lab_id)
        self._show_analysis(summary_lines(lab, self.db.list_measurements(self.lab_id)))

    def save_conclusion(self):
        self.db.update_lab(self.lab_id, conclusion=self.concl_text.get("1.0", "end").strip())

    def export(self, kind):
        if self.lab_id is None or not self.save_info(quiet=True):
            return
        self.save_conclusion()
        lab = self.db.get_lab(self.lab_id)
        ext = ".docx" if kind == "docx" else ".pdf"
        safe_title = re.sub(r'[\\/:*?"<>|]+', "_", lab["title"]).strip() or "работа"
        path = filedialog.asksaveasfilename(
            defaultextension=ext, initialfile=f"Отчёт - {safe_title}{ext}",
            filetypes=[("Word" if kind == "docx" else "PDF", f"*{ext}")])
        if not path:
            return
        try:
            data = collect(self.db, self.lab_id)
            (export_docx if kind == "docx" else export_pdf)(data, path)
        except PermissionError:
            messagebox.showerror("LabTrack", "Не удалось записать файл. Возможно, он открыт в другой программе.")
            return
        except Exception as exc:  # показываем причину, а не молча падаем
            messagebox.showerror("LabTrack", f"Ошибка при создании отчёта:\n{exc}")
            return
        if messagebox.askyesno("LabTrack", "Отчёт сохранён. Открыть его?") and hasattr(os, "startfile"):
            os.startfile(path)
