
from fastapi import APIRouter, HTTPException, Response, Query, Depends
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from auth import get_current_user, has_sensitive_access
from storage import get_analyses_db

router = APIRouter(prefix="/api", tags=["reports"])

@router.get("/report/{consulta_id}")
def get_report(consulta_id: str, token: str = Query(None), user=Depends(get_current_user)):
    analysis = get_analyses_db().get(consulta_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    # mascarar se o user não tem acesso sensível
    if not has_sensitive_access(user):
        analysis = dict(analysis)
        analysis["pep_alert"] = None
        analysis["sanctions_alert"] = None
        analysis["fraude_suspeita"] = None
        analysis["comentario_fraude"] = ""

    pdf_buffer = build_pdf(analysis)
    return Response(
        content=pdf_buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="relatorio_{consulta_id}.pdf"'
        },
    )

def comportamento_historico_label(a: dict) -> str:
    if a.get("fraude_suspeita"):
        return "Suspeita de fraude declarada"
    if int(a.get("sinistros_ult_12m",0)) >= 2:
        return "Sinistros frequentes (últimos 12m)"
    hist = (a.get("historico_pagamentos") or "").lower()
    if "atras" in hist or "inadimpl" in hist:
        return "Pagador com histórico de atraso"
    return "Boa conduta histórica"

def wrap_lines(text, width=60):
    if text is None:
        return []
    words = str(text).split()
    out = []
    cur = []
    cur_len = 0
    for w in words:
        lw = len(w)+1
        if cur_len + lw > width:
            out.append(" ".join(cur))
            cur=[w]
            cur_len=len(w)
        else:
            cur.append(w)
            cur_len += lw
    if cur:
        out.append(" ".join(cur))
    return out

def build_pdf(a: dict) -> BytesIO:
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)

    W,H = A4
    ml,mr = 20*mm,20*mm
    header_h = 22*mm

    # header
    p.setFillColorRGB(0.07,0.1,0.18)
    p.rect(0,H-header_h,W,header_h,fill=1,stroke=0)
    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold",12)
    p.drawString(ml,H-10*mm,"CHECK INSURANCE RISK")
    p.setFont("Helvetica",8.5)
    p.setFillColorRGB(0.55,0.8,1)
    p.drawString(ml,H-14.5*mm,"Motor de Compliance e Suporte Técnico de Subscrição")
    p.setStrokeColorRGB(0.55,0.8,1)
    p.setLineWidth(0.6)
    p.line(ml,H-header_h,W-mr,H-header_h)

    y = H-header_h-8*mm
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold",10)
    p.drawString(ml,y,"Dados da Consulta"); y-=6*mm
    p.setFont("Helvetica",9)
    meta=[
        f"Consulta ID: {a.get('consulta_id')}",
        f"Data/Hora (UTC): {a.get('timestamp')}",
        f"Identificador analisado: {a.get('identifier','-')} ({a.get('identifier_type','-')})",
        f"Estado do Caso: {a.get('estado','-')}",
        f"Ramo / Finalidade / Canal: {a.get('ramo','-')} / {a.get('finalidade','-')} / {a.get('canal','-')}",
        f"Regras Aplicadas: {', '.join(a.get('regras_aplicadas',[])) or '-'}",
    ]
    for line in meta:
        p.drawString(ml,y,line); y-=5.2*mm
    y-=4*mm
    p.setStrokeColor(colors.grey); p.setLineWidth(0.3)
    p.line(ml,y,W-mr,y); y-=8*mm

    # Risco box
    decisao_txt = (a["decisao"] or "").lower()
    if ("escalar" in decisao_txt) or ("elevado" in decisao_txt) or ("recus" in decisao_txt):
        box_color=(0.95,0.27,0.27); text_color=colors.white; risco_label="Risco Elevado"
    elif "condi" in decisao_txt:
        box_color=(0.98,0.87,0.3); text_color=colors.black; risco_label="Risco Moderado"
    else:
        box_color=(0.36,0.83,0.50); text_color=colors.black; risco_label="Risco Controlado"

    box_h=32*mm; box_w=W-ml-mr; box_y=y-box_h
    p.setFillColorRGB(*box_color)
    p.roundRect(ml,box_y,box_w,box_h,4*mm,fill=1,stroke=0)
    p.setFillColor(text_color)
    p.setFont("Helvetica-Bold",11)
    p.drawString(ml+6*mm,box_y+box_h-7*mm,risco_label)
    p.setFont("Helvetica",9)
    p.drawString(ml+6*mm,box_y+box_h-12*mm,f"Score Final: {a['score_final']}/100")
    p.drawString(ml+6*mm,box_y+box_h-16.5*mm,f"Decisão Recomendada: {a['decisao']}")
    flags=[]
    if a.get("pep_alert"): flags.append("PEP")
    if a.get("sanctions_alert"): flags.append("Sanções")
    if a.get("fraude_suspeita"): flags.append("Fraude")
    fl_txt="Sem alertas PEP / Sanções / Fraude" if not flags else "Alertas: "+ " / ".join(flags)
    p.drawString(ml+6*mm,box_y+box_h-21*mm,fl_txt)
    comp_hist = comportamento_historico_label(a)
    p.drawString(ml+6*mm,box_y+box_h-25.5*mm,"Comportamento Hist.: "+comp_hist)
    conds=a.get("condicoes_sugeridas","")
    if conds:
        p.drawString(ml+6*mm,box_y+box_h-30*mm,"Condições Sugeridas: "+conds[:70])

    y=box_y-10*mm

    # Detalhes técnicos
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold",10)
    p.drawString(ml,y,"Detalhes Técnicos"); y-=6*mm
    p.setFont("Helvetica",9)

    detalhes=[
        ("Score Final", f"{a['score_final']}/100"),
        ("Decisão Recomendada", a["decisao"]),
        ("Justificação Técnica", a.get("justificacao","-")),
        ("Alerta Sanções", "SIM" if a.get("sanctions_alert") else "NÃO"),
        ("Alerta PEP", "SIM" if a.get("pep_alert") else "NÃO"),
        ("Fraude Suspeita", "SIM" if a.get("fraude_suspeita") else "NÃO"),
        ("Histórico de Pagamentos", a.get("historico_pagamentos","-")),
        ("Sinistros Totais", str(a.get("sinistros_total","-"))),
        ("Sinistros Últimos 12 Meses", str(a.get("sinistros_ult_12m","-"))),
        ("Nota de Fraude / Abuso", a.get("comentario_fraude","-")),
        ("Estado do Caso", a.get("estado","-")),
        ("Decisão Humana / Timestamp", f"{a.get('decisao_humana','-')} / {a.get('data_decisao','-')}"),
        ("Motor / Versão", a.get("motor_versao","-")),
        ("Integridade (SHA256)", a.get("integridade_hash","-")[:40]+"..."),
    ]

    col_key_w=60*mm
    col_val_w=W-ml-mr-col_key_w
    row_h=8*mm

    def maybe_new_page(current_y):
        if current_y-row_h < 25*mm:
            draw_footer()
            p.showPage()
            setup_new_page()
            return p._current_y
        return current_y

    def draw_footer():
        footer_h=10*mm; footer_y=10*mm
        p.setFillColorRGB(0.15,0.18,0.25)
        p.rect(0,0,W,footer_h+footer_y,fill=1,stroke=0)
        p.setFillColorRGB(0.55,0.8,1)
        p.setFont("Helvetica-Bold",8)
        p.drawRightString(W-mr,footer_y+3*mm,"CONFIDENCIAL • USO INTERNO")

    def setup_new_page():
        p.setFont("Helvetica-Bold",10)
        p.setFillColor(colors.black)
        p.drawString(ml,H-25*mm,"Detalhes Técnicos (cont.)")
        p._current_y = H-33*mm
        p.setFont("Helvetica",9)
        p.setFillColor(colors.white)

    p._current_y = y
    for label_text, value_text in detalhes:
        p._current_y = maybe_new_page(p._current_y)
        # label box
        p.setFillColorRGB(0.11,0.14,0.2)
        p.rect(ml,p._current_y-row_h+1.5*mm,col_key_w,row_h,fill=1,stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold",8.5)
        p.drawString(ml+3*mm,p._current_y-3*mm,label_text)

        # value box
        p.setFillColorRGB(0.17,0.2,0.28)
        p.rect(ml+col_key_w,p._current_y-row_h+1.5*mm,col_val_w,row_h,fill=1,stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica",8.5)

        lines = wrap_lines(str(value_text),60)
        line_y = p._current_y-3*mm
        for line in lines:
            p.drawString(ml+col_key_w+3*mm,line_y,line)
            line_y-=4*mm

        extra = max(0,(len(lines)-1))*4*mm
        p._current_y -= row_h+extra
        p._current_y -= 2*mm

    y = p._current_y-8*mm
    p.setStrokeColor(colors.grey); p.setLineWidth(0.3)
    p.line(ml,y,W-mr,y); y-=8*mm
    p.setFillColor(colors.black); p.setFont("Helvetica-Bold",10)
    p.drawString(ml,y,"Notas e Conformidade"); y-=6*mm
    p.setFont("Helvetica",8.5); p.setFillColor(colors.black)

    obs=[
        "Esta análise resulta da consolidação de fontes internas e externas autorizadas.",
        "O score técnico e a decisão recomendada servem como apoio à subscrição, compliance e antifraude.",
        "Não substituem avaliação humana em casos de risco elevado, suspeita de fraude, PEP ou sanções.",
        "",
        f"Gerado por: {a.get('requested_by','-')}",
        f"Motor: Check Insurance Risk v{a.get('motor_versao','-')}",
    ]

    for line in obs:
        if y < 30*mm:
            draw_footer()
            p.showPage()
            y = H-25*mm
            p.setFont("Helvetica",8.5)
            p.setFillColor(colors.black)
        p.drawString(ml,y,line)
        y-=5*mm

    draw_footer()
    p.showPage()
    p.save()
    buf.seek(0)
    return buf
