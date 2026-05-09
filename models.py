from typing import Optional
from pydantic import BaseModel

class Transacao(BaseModel):
    tipo: str
    produto: str
    valor: float
    status: str
    observacoes: Optional[str] = None
    quantidade: Optional[int] = None
    data_venda: Optional[str] = None