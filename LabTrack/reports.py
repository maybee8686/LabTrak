"""Формирование отчётов в Word (.docx) и PDF."""
import os
import tempfile
from xml.sax.saxutils import escape

from analysis import fmt, linear_fit, summary_lines


def collect(db, lab_id):
    lab = db.get_lab(lab_id)
    steps = db.list_steps(lab_id)
    ms = db.list_measurements(lab_id)
    return {"lab": lab, "steps": steps, "ms": ms, "lines": summary_lines(lab, ms)}


def _label(name, unit, default):
    name = name or default
    return f"{name}, {unit}" if unit else name


def make_chart(data, path):
    """График точек и линии аппроксимации. Возвращает False, если точек < 2."""
    ms, lab = data["ms"], data["lab"]
    if len(ms) < 2:
        return False
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs, ys = [m["x"] for m in ms], [m["y"] for m in ms]
    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    ax.scatter(xs, ys, color="#1f5fa8", zorder=3, label="Измерения")
    fit = linear_fit(xs, ys)
    if fit:
        x0, x1 = min(xs), max(xs)
        ax.plot([x0, x1], [fit["k"] * x0 + fit["b"], fit["k"] * x1 + fit["b"]],
                color="#c0392b", label="Линейная аппроксимация")
    ax.set_xlabel(_label(lab["x_name"], lab["x_unit"], "x"))
    ax.set_ylabel(_label(lab["y_name"], lab["y_unit"], "y"))
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def _status(data):
    done = sum(s["done"] for s in data["steps"])
    return f"Выполнено этапов: {done} из {len(data['steps'])}"


def export_docx(data, path):
    from docx import Document
    from docx.shared import Pt, Cm

    lab = data["lab"]
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)

    doc.add_heading(f"Отчёт по лабораторной работе: {lab['title']}", level=1)
    for caption, value in (("Предмет", lab["subject"]), ("Срок сдачи", lab["deadline"])):
        if value:
            doc.add_paragraph(f"{caption}: {value}")
    doc.add_paragraph(_status(data))

    if lab["description"]:
        doc.add_heading("Описание и цель работы", level=2)
        doc.add_paragraph(lab["description"])

    if data["steps"]:
        doc.add_heading("Этапы выполнения", level=2)
        table = doc.add_table(rows=1, cols=2, style="Table Grid")
        table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Этап", "Статус"
        for s in data["steps"]:
            row = table.add_row().cells
            row[0].text = s["title"]
            row[1].text = "выполнен" if s["done"] else "не выполнен"

    doc.add_heading("Результаты измерений", level=2)
    if data["ms"]:
        table = doc.add_table(rows=1, cols=3, style="Table Grid")
        head = table.rows[0].cells
        head[0].text = "№"
        head[1].text = _label(lab["x_name"], lab["x_unit"], "x")
        head[2].text = _label(lab["y_name"], lab["y_unit"], "y")
        for i, m in enumerate(data["ms"], 1):
            row = table.add_row().cells
            row[0].text, row[1].text, row[2].text = str(i), fmt(m["x"], 6), fmt(m["y"], 6)
    else:
        doc.add_paragraph("Измерения не внесены.")

    doc.add_heading("Анализ данных", level=2)
    for line in data["lines"]:
        doc.add_paragraph(line, style="List Bullet")

    with tempfile.TemporaryDirectory() as tmp:
        img = os.path.join(tmp, "chart.png")
        if make_chart(data, img):
            doc.add_heading("График", level=2)
            doc.add_picture(img, width=Cm(15))

    if lab["conclusion"]:
        doc.add_heading("Вывод", level=2)
        doc.add_paragraph(lab["conclusion"])
    doc.save(path)


def _register_fonts():
    """Шрифты с кириллицей: Arial в Windows, иначе DejaVu (идёт с matplotlib)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import matplotlib

    mpl = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    pairs = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        (os.path.join(mpl, "DejaVuSans.ttf"), os.path.join(mpl, "DejaVuSans-Bold.ttf")),
    ]
    for regular, bold in pairs:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("LT", regular))
            pdfmetrics.registerFont(TTFont("LT-Bold", bold))
            return
    raise RuntimeError("Не найден шрифт с поддержкой кириллицы для PDF")


def export_pdf(data, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    _register_fonts()
    lab = data["lab"]
    body = ParagraphStyle("body", fontName="LT", fontSize=11, leading=15)
    h1 = ParagraphStyle("h1", parent=body, fontName="LT-Bold", fontSize=16, leading=20, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=body, fontName="LT-Bold", fontSize=13, leading=17,
                        spaceBefore=12, spaceAfter=6)

    def para(text, style=body):
        return Paragraph(escape(text).replace("\n", "<br/>"), style)

    def grid(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "LT"),
            ("FONTNAME", (0, 0), (-1, 0), "LT-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
        ]))
        return t

    story = [para(f"Отчёт по лабораторной работе: {lab['title']}", h1)]
    for caption, value in (("Предмет", lab["subject"]), ("Срок сдачи", lab["deadline"])):
        if value:
            story.append(para(f"{caption}: {value}"))
    story.append(para(_status(data)))

    if lab["description"]:
        story += [para("Описание и цель работы", h2), para(lab["description"])]

    if data["steps"]:
        rows = [["Этап", "Статус"]] + [
            [para(s["title"]), "выполнен" if s["done"] else "не выполнен"]
            for s in data["steps"]]
        story += [para("Этапы выполнения", h2), grid(rows, [12 * cm, 4 * cm])]

    story.append(para("Результаты измерений", h2))
    if data["ms"]:
        rows = [["№", _label(lab["x_name"], lab["x_unit"], "x"),
                 _label(lab["y_name"], lab["y_unit"], "y")]]
        rows += [[str(i), fmt(m["x"], 6), fmt(m["y"], 6)] for i, m in enumerate(data["ms"], 1)]
        rows[0][1:] = [para(rows[0][1]), para(rows[0][2])]
        story.append(grid(rows, [1.5 * cm, 7 * cm, 7 * cm]))
    else:
        story.append(para("Измерения не внесены."))

    story.append(para("Анализ данных", h2))
    story += [para("• " + line) for line in data["lines"]]

    with tempfile.TemporaryDirectory() as tmp:
        img = os.path.join(tmp, "chart.png")
        if make_chart(data, img):
            story.append(KeepTogether([para("График", h2),
                                       Image(img, width=15 * cm, height=10 * cm)]))
        if lab["conclusion"]:
            story += [para("Вывод", h2), para(lab["conclusion"])]
        SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=2 * cm, bottomMargin=2 * cm,
                          title=f"Отчёт: {lab['title']}").build(story)
