from pydantic import BaseModel
from typing import Optional

class Transacao(BaseModel):
    tipo: str
    valor: float
    status: str
    observacoes: Optional[str] = None
    produto: Optional[str] = None