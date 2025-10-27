ANALYSES_DB = {}  # consulta_id -> analysis_obj
AUDIT_LOG = []  # lista de auditoria
INFO_SOURCES = []  # fontes cadastradas

def add_info_source(title, description, url, directory, filename, uploaded_at):
    INFO_SOURCES.append({
        "title": title,
        "description": description,
        "url": url,
        "directory": directory,
        "filename": filename,
        "uploaded_at": uploaded_at,
    })
