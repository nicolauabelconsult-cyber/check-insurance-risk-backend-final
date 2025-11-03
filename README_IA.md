
# CIR — Add-on IA (Ingestão, Extração, Factos)
Patch mínimo para adicionar extração de PEP, sanções, sinistros e pagamentos às Fontes de Informação.

## Instalação
1. Copia `ai_pipeline.py`, `extractors.py`, `storage.py` para a raiz do backend (junto do main.py).
2. No `main.py`:
   ```python
   from ai_pipeline import router as ai_router
   app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
   ```
3. Em `requirements.txt`, acrescenta:
   ```
   httpx==0.27.2
   beautifulsoup4==4.12.3
   rapidfuzz==3.9.6
   ```

## Endpoints
- POST `/api/ai/ingest` → { entity_id, sources:[{url|html|text}] }
- POST `/api/ai/extract` → consolida factos e grava
- GET  `/api/ai/facts/{entity_id}` → devolve JSON consolidado

## Integração com PDF V6
Usa os campos do facts JSON para preencher o meta do `render_pdf`.
