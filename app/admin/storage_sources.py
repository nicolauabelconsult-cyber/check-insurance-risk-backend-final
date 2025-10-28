_sources = []

def add_source(meta: dict):
    _sources.append(meta)

def list_sources():
    return _sources

def delete_source(idx: int):
    if 0 <= idx < len(_sources):
        _sources.pop(idx)
        return True
    return False
