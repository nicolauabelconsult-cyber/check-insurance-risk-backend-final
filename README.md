# Check Insurance Risk Backend

## Login inicial
POST /api/login
{
  "email": "admin@checkrisk.com",
  "password": "admin123"
}

Resposta:
{
  "access_token": "admin@checkrisk.com",
  "user_name": "Administrador",
  "role": "admin"
}

Guardar no browser/localStorage:
- cir_token = access_token
- cir_user = user_name
- cir_role = role

## Fluxo Dashboard
1. POST /api/risk-check  (Authorization: Bearer <cir_token>)
2. Resposta traz consulta_id, score_final, decisao, justificacao, pep/sanctions flags, benchmark, timestamp
3. GET /api/report/{consulta_id}?token=<cir_token> devolve PDF

## Administração (role=admin)
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

Pastas locais:
- uploads/  (ficheiros carregados)
- reports/  (PDFs gerados)

Healthcheck:
GET /api/health -> {"status":"ok"}
