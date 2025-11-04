# CIR — Add-on IA (INSTALAÇÃO)
1) Copia para a raiz do backend (junto ao main.py):
   - ai_pipeline.py
   - extractors.py
   - storage.py

2) No main.py adiciona:
   from ai_pipeline import router as ai_router
   app.include_router(ai_router, prefix="/api/ai", tags=["ai"])

3) Em requirements.txt acrescenta:
   httpx==0.27.2
   beautifulsoup4==4.12.3
   rapidfuzz==3.9.6

4) Render:
   Build: pip install -r requirements.txt
   Start: python -m uvicorn main:app --host 0.0.0.0 --port $PORT
