import os, json
from datetime import datetime

SEQ_FILE = "consulta_seq.json"

def generate_consulta_id():
    year = datetime.now().year
    seq = {str(year): 0}
    if os.path.exists(SEQ_FILE):
        try:
            with open(SEQ_FILE, "r") as f:
                seq = json.load(f)
        except Exception:
            seq = {str(year): 0}
    current = seq.get(str(year), 0) + 1
    seq[str(year)] = current
    with open(SEQ_FILE, "w") as f:
        json.dump(seq, f)
    return f"CIR-{year}-{current:06d}"
