
import json, os, threading
_LOCK = threading.Lock()
_DB_PATH = os.environ.get("CIR_AI_DB", "/tmp/cir_ai_db.json")
class _DB:
    def __init__(self):
        self.data = {"sources": {}, "facts": {}}
        self._load()
    def _load(self):
        if os.path.exists(_DB_PATH):
            try:
                with open(_DB_PATH, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                pass
    def _save(self):
        try:
            with open(_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    def add_source(self, entity_id, doc):
        with _LOCK:
            self.data["sources"].setdefault(entity_id, []).append(doc)
            self._save()
    def get_sources(self, entity_id):
        return list(self.data["sources"].get(entity_id, []))
    def save_facts(self, entity_id, facts):
        with _LOCK:
            self.data["facts"][entity_id] = facts
            self._save()
    def get_facts(self, entity_id):
        return self.data["facts"].get(entity_id)
DB = _DB()
