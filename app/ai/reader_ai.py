import os, re
from datetime import datetime

def _detect_category(text: str):
    if re.search(r"\bpep\b|\bpoliticamente exposto", text, re.IGNORECASE):
        return "PEP"
    if re.search(r"ofac|sanction|sanções|conselho de segurança|united nations", text, re.IGNORECASE):
        return "Sanções"
    if re.search(r"fraude|fraudulento|suspeito|lavagem", text, re.IGNORECASE):
        return "Fraude / AML"
    if re.search(r"\besg\b|sustentabilidade|environmental|governance", text, re.IGNORECASE):
        return "ESG"
    if re.search(r"rating|moody|fitch|s&p", text, re.IGNORECASE):
        return "Crédito / Rating"
    return "Outros"

def _detect_jurisdiction(text: str):
    if re.search(r"\bUni[aã]o Europeia\b|\bEU\b|\bEuropean Union\b", text, re.IGNORECASE):
        return "União Europeia"
    if re.search(r"\bOFAC\b|\bUS Treasury\b|\bUnited States\b", text, re.IGNORECASE):
        return "Estados Unidos / OFAC"
    if re.search(r"\bUK HMT\b|\bHis Majesty", text, re.IGNORECASE):
        return "Reino Unido"
    if re.search(r"\bNa[cç][aã]es Unidas\b|\bUnited Nations\b|\bONU\b", text, re.IGNORECASE):
        return "Nações Unidas"
    return "Desconhecida"

def _detect_freshness(text: str):
    m = re.findall(r"(20[0-4][0-9][-/\.](0[1-9]|1[0-2])[-/\.]([0-2][0-9]|3[01]))", text)
    if not m:
        return "Sem data explícita. Verificar validade manual."
    anos = [int(x[0][0:4]) for x in m]
    ano_max = max(anos)
    ano_now = datetime.now().year
    if ano_max < ano_now - 2:
        return f"Fonte potencialmente desatualizada (última referência {ano_max})."
    if ano_max < ano_now:
        return f"Fonte possivelmente válida mas não recente (última referência {ano_max})."
    return "Fonte parece recente."

def _recommended_usage(category: str, sanctions_flag: bool):
    if category == "Sanções":
        return "Uso obrigatório em due diligence e onboarding de clientes de alto impacto antes da emissão da apólice."
    if category == "PEP":
        return "Aplicar reforço de due diligence e aprovação de nível Compliance antes de aceitar."
    if category == "Fraude / AML":
        return "Consultar sempre em sinistros suspeitos e renovações com histórico crítico."
    if sanctions_flag:
        return "Existe referência a sanções, escalar para Compliance antes de decisão comercial."
    if category == "ESG":
        return "Usar apenas para scoring reputacional e reporte interno; não usar isoladamente para recusa."
    return "Fonte de apoio. Não substitui verificação humana."

def analyze_file(filepath: str):
    filename = os.path.basename(filepath)
    ext = filename.split(".")[-1].lower()
    tipo = {
        "csv":"CSV/Tabela",
        "txt":"Texto",
        "xlsx":"Excel",
        "pdf":"PDF",
    }.get(ext, "Desconhecido")

    try:
        with open(filepath, "rb") as f:
            raw = f.read(8192)
        text_sample = raw.decode(errors="ignore")
    except Exception:
        text_sample = ""

    categoria = _detect_category(text_sample)
    jurisdicao = _detect_jurisdiction(text_sample)
    freshness = _detect_freshness(text_sample)

    sanctions_flag = bool(re.search(r"sanction|ofac|united nations|conselho de segurança|sanç", text_sample, re.IGNORECASE))
    linhas_est = text_sample.count("\n")
    recomendacao = _recommended_usage(categoria, sanctions_flag)

    resumo = (
        f"Ficheiro '{filename}' interpretado. Categoria provável: {categoria}. "
        f"Fonte associada a: {jurisdicao}. "
        f"Integridade temporal: {freshness} "
        f"Linhas detectadas ~{linhas_est}. "
        f"Recomendação: {recomendacao}"
    )

    return {
        "filename": filename,
        "tipo_detectado": tipo,
        "categoria": categoria,
        "jurisdicao": jurisdicao,
        "freshness": freshness,
        "linhas_estimadas": linhas_est,
        "recomendacao": recomendacao,
        "resumo": resumo
    }
