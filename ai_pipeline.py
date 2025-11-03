
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import datetime as dt

from extractors import fetch_source, extract_facts_from_sources
from storage import DB

router = APIRouter()

class Source(BaseModel):
    url: Optional[str] = Field(default=None)
    html: Optional[str] = Field(default=None)
    text: Optional[str] = Field(default=None)
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)

class IngestRequest(BaseModel):
    entity_id: str
    sources: List[Source]

class ExtractRequest(BaseModel):
    entity_id: str

@router.post("/ingest")
async def ingest(req: IngestRequest):
    stored = []
    for s in req.sources:
        doc = {"url": s.url, "html": s.html, "text": s.text, "meta": s.meta or {}}
        if (not doc.get("html")) and (not doc.get("text")) and s.url:
            html = await fetch_source(s.url)
            doc["html"] = html
        DB.add_source(req.entity_id, doc)
        stored.append({"ok": True, "url": s.url})
    return {"entity_id": req.entity_id, "stored": stored, "count": len(stored)}

@router.post("/extract")
async def extract(req: ExtractRequest):
    sources = DB.get_sources(req.entity_id)
    if not sources:
        raise HTTPException(status_code=404, detail="Sem fontes para esta entidade.")
    facts = extract_facts_from_sources(sources)
    DB.save_facts(req.entity_id, facts)
    return {"entity_id": req.entity_id, "facts": facts, "updated_at": dt.datetime.utcnow().isoformat()+"Z"}

@router.get("/facts/{entity_id}")
async def get_facts(entity_id: str):
    facts = DB.get_facts(entity_id)
    if not facts:
        raise HTTPException(status_code=404, detail="Sem factos extraídos para esta entidade.")
    return {"entity_id": entity_id, "facts": facts}
