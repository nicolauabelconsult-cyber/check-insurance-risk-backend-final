# Check Insurance Risk — Backend (FastAPI)

Este backend foi desenhado para **funcionar imediatamente** com o teu frontend (`index.html`, `acesso.html`, `admin.html`).

## Credenciais iniciais
- **Admin**: `admin@checkrisk.com` / `admin123`
- **Analyst**: `analyst@checkrisk.com` / `analyst123`

## Endpoints usados pelo Frontend
- `POST /api/login` — autenticação JWT.
- `POST /api/risk-check` — análise de risco.
- `GET  /api/report/{consulta_id}?token=...` — PDF inline.
- Administração (perfil `admin`):
  - `POST /api/admin/user-add`
  - `POST /api/admin/risk-data/add-record` | `GET /api/admin/risk-data/list` | `POST /api/admin/risk-data/delete-record`
  - `POST /api/admin/info-sources/upload` | `POST /api/admin/info-sources/create` | `GET /api/admin/info-sources/list` | `POST /api/admin/info-sources/delete`

## Executar localmente
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
A app arranca em `http://127.0.0.1:8000` (ajusta `API_BASE` no frontend para apontar aqui).

## Deploy na Render
1. Cria um novo **Web Service** e liga este repositório/ZIP.
2. `Build Command`: `pip install -r requirements.txt`
3. `Start Command`: `bash start.sh`
4. Define `FRONTEND_ORIGIN` para o domínio do teu Netlify (ou `*` durante testes).

## Notas
- Base de dados SQLite (ficheiro `data.db`). Para Render, usa `sqlite:///data.db` (já no `render.yaml`).
- Uploads guardados em `uploads/`.
- Os PDF são gerados on-the-fly com ReportLab.
