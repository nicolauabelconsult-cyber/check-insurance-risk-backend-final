# Check Insurance Risk Backend

Login inicial:
POST /api/login
{ "email": "admin@checkrisk.com", "password": "admin123" }

Depois usar o token devolvido como Bearer <token>.

Endpoints principais:
- /api/login
- /api/risk-check
- /api/report/{consulta_id}?token=...
- /api/health

Admin (role=admin):
- /api/admin/users/list
- /api/admin/users/create
- /api/admin/risk-data/add-record
- /api/admin/risk-data/list
- /api/admin/risk-data/delete-record
- /api/admin/info-sources/upload
- /api/admin/info-sources/create
- /api/admin/info-sources/list
- /api/admin/info-sources/delete
- /api/admin/audit/list

Pastas obrigatórias:
- uploads/  (ficheiros carregados)
- reports/  (PDFs gerados)

Comando de arranque no Render:
uvicorn app.main:app --host 0.0.0.0 --port $PORT
