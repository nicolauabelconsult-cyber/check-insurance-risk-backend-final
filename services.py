import uuid
import json
from datetime import datetime
from fpdf import FPDF
from pathlib import Path

# memória de runtime
CONSULTAS = []
CONTACTS = []

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

def _load_clientes():
    with open(DATA_DIR / "clientes.json","r",encoding="utf-8") as f:
        return json.load(f)

def _load_rules():
    with open(DATA_DIR / "rules.json","r",encoding="utf-8") as f:
        return json.load(f)

def authenticate(email: str, password: str):
    # Demo: aceitar sempre e gerar token simples
    token = "demo-token-" + email
    return token

def _calc_score_and_decision(cliente, rules):
    fin  = cliente["financeiro"].get("risco_financeiro_score", 0)
    sin  = cliente["sinistros"].get("risco_sinistralidade_score", 0)

    rep_pep   = 100 if cliente["reputacao"].get("pep_flag") else 0
    rep_sanc  = 100 if cliente["reputacao"].get("sancionado_flag") else 0
    rep_score = max(rep_pep, rep_sanc)

    score_final = round(
        fin  * rules["peso_financeiro"] +
        sin  * rules["peso_sinistralidade"] +
        rep_score * rules["peso_reputacao"]
    )

    if score_final <= rules["limiar_aceitar"]:
        decisao = "Aceitar c/ Condições"
        justificacao = rules["texto_aceitar"]
    elif score_final <= rules["limiar_escalar"]:
        decisao = "Escalar Análise Manual"
        justificacao = rules["texto_escalar"]
    else:
        decisao = "Recusar Proposta"
        justificacao = rules["texto_recusar"]

    return score_final, decisao, justificacao

def analisar_risco(identificador: str):
    clientes = _load_clientes()
    rules    = _load_rules()
    ts       = datetime.utcnow()

    if identificador not in clientes:
        cliente = {
            "financeiro": {
                "risco_financeiro_score": 50,
                "nota_financeira": "Sem histórico financeiro carregado"
            },
            "sinistros": {
                "risco_sinistralidade_score": 30,
                "nota_sinistros": "Sem registo interno de sinistros recentes"
            },
            "reputacao": {
                "pep_flag": False,
                "sancionado_flag": False,
                "nota_reputacao": "Sem alerta conhecido (DEMO)"
            },
            "observacao_interna": "Cliente não encontrado nos dados internos carregados.",
            "ultima_actualizacao": ts.date().isoformat()
        }
    else:
        cliente = clientes[identificador]

    score_final, decisao, justificacao = _calc_score_and_decision(cliente, rules)

    sanctions_alert = bool(
        cliente["reputacao"].get("pep_flag") or cliente["reputacao"].get("sancionado_flag")
    )
    sanctions_note = cliente["reputacao"].get("nota_reputacao","")

    consulta_id = str(uuid.uuid4())

    resposta = {
        "consulta_id": consulta_id,
        "score_final": score_final,
        "decisao": decisao,
        "justificacao": justificacao,
        "sanctions_alert": sanctions_alert,
        "sanctions_note": sanctions_note,
        "resumo_financeiro": cliente["financeiro"].get("nota_financeira",""),
        "resumo_sinistros": cliente["sinistros"].get("nota_sinistros",""),
        "resumo_reputacao": cliente["reputacao"].get("nota_reputacao",""),
        "timestamp": ts
    }

    CONSULTAS.append(resposta)
    return resposta

def gerar_pdf_relatorio(consulta_id: str) -> bytes:
    data = next((c for c in CONSULTAS if c["consulta_id"] == consulta_id), None)
    if data is None:
        return None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Relatório Técnico de Risco", ln=True)

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Consulta ID: {data['consulta_id']}", ln=True)
    pdf.cell(0, 8, f"Timestamp (UTC): {data['timestamp'].isoformat()}", ln=True)
    pdf.ln(4)

    pdf.cell(0, 8, f"Score Final: {data['score_final']} / 100", ln=True)
    pdf.cell(0, 8, f"Decisão Recomendada: {data['decisao']}", ln=True)
    pdf.multi_cell(0, 8, f"Justificação Técnica: {data['justificacao']}")
    pdf.ln(4)

    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, f"Resumo Financeiro: {data['resumo_financeiro']}")
    pdf.ln(2)
    pdf.multi_cell(0, 6, f"Resumo Sinistralidade: {data['resumo_sinistros']}")
    pdf.ln(2)
    pdf.multi_cell(0, 6, f"Resumo Reputação/Compliance: {data['resumo_reputacao']}")
    pdf.ln(4)

    pdf.multi_cell(0, 6, f"Alerta Sanções/PEP: {'SIM' if data['sanctions_alert'] else 'NÃO'}")
    pdf.multi_cell(0, 6, f"Nota Compliance: {data['sanctions_note']}")
    pdf.ln(10)

    pdf.set_font("Arial", size=8)
    pdf.multi_cell(
        0, 5,
        "Nota: Este relatório contém apenas indicadores de risco estritamente necessários "
        "para a decisão de subscrição e registo auditável. "
        "Não inclui dados pessoais detalhados nem histórico integral de sinistros."
    )

    pdf_bytes = pdf.output(dest="S").encode("latin1")
    return pdf_bytes

def registar_contacto(nome, email, mensagem, assunto):
    item = {
        "id": str(uuid.uuid4()),
        "nome": nome,
        "email": email,
        "mensagem": mensagem,
        "assunto": assunto,
        "timestamp": datetime.utcnow().isoformat()
    }
    CONTACTS.append(item)
    print("NOVO_CONTACTO", item)
    return item
