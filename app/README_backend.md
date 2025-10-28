CHECK INSURANCE RISK • Backend v4.0

- Autenticação via /api/login (JWT).
- /api/risk-check gera:
    * score_final
    * decisao
    * flags PEP / sanções
    * benchmark_internacional
    * consulta_id no formato CIR-YYYY-000001
    * timestamp
    * auditoria interna
- /api/report/{consulta_id}?token=JWT devolve PDF profissional (ReportLab),
  incluindo:
    Dados da Consulta, Detalhes Técnicos,
    Histórico de Comportamento e Sinistros,
    Notas de Conformidade,
    Assinatura Técnica (CONFIDENCIAL • USO INTERNO).
- /api/admin/... (apenas admin):
    * users/list + users/create
    * audit/list
    * risk-data/add-record, list, delete-record
    * info-sources/upload, create, list, delete
    * info-sources/analisar-fonte → IA Local Heurística v1

IA Local Heurística v1:
    - Classifica ficheiros carregados (PEP, Sanções, Fraude/AML, ESG, Rating).
    - Detecta jurisdição (OFAC, UE, ONU, UK HMT...).
    - Verifica frescura temporal dos dados.
    - Dá recomendação operacional de uso.
