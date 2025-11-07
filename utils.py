import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def render_pdf(path: str, data: dict):
    ensure_dir(os.path.dirname(path))
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Relatório de Cliente de Risco")
    y -= 30
    c.setFont("Helvetica", 10)
    for k, v in data.items():
        c.drawString(40, y, f"{k}: {v}")
        y -= 16
        if y < 60:
            c.showPage()
            y = h - 40
    c.showPage()
    c.save()
