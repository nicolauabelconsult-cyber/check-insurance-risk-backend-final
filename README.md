# Check Insurance Risk – Backend

API em FastAPI para cálculo de risco técnico de clientes e geração de relatório PDF.

## Endpoints principais
- `POST /api/login`
- `POST /api/risk-check`
- `GET /api/report/{consulta_id}`
- `POST /api/contact`

## Deploy
Este repositório está preparado para o Render.
O ficheiro `render.yaml` já contém a configuração:

```yaml
services:
  - type: web
    name: check-insurance-risk-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    plan: free
