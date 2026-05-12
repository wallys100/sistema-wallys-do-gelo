from typing import Optional
from pydantic import BaseModel, field_validator

# Mapa central de produtos válidos — edite aqui para adicionar novos tipos
PRODUTOS_VALIDOS = {
    "Gelo em Cubo": {
        "secao": "cubos",
        "sku": "GELO-CUBOS-001",
    },
    "Gelo Saborizado": {
        "secao": "saborizado",
        "sku": "GELO-SAB-001",
    },
}

class Transacao(BaseModel):
    tipo: str                          # "entrada" = compra/custo | "saida" = venda/receita
    produto: str
    valor: float
    status: str                        # "pago" | "pendente"
    observacoes: Optional[str] = None
    quantidade: Optional[int] = None
    data_venda: Optional[str] = None
    fornecedor: Optional[str] = None   # NOVO: ex. "Sempre Gelo", "Tinthoca"
    secao: Optional[str] = None        # NOVO: auto-preenchido pelo backend ("cubos" | "saborizado")
    sku: Optional[str] = None          # NOVO: auto-preenchido pelo backend

    @field_validator("produto")
    def produto_deve_ser_valido(cls, v):
        if v not in PRODUTOS_VALIDOS:
            raise ValueError(
                f"Tipo de gelo não reconhecido: '{v}'. "
                f"Valores aceitos: {list(PRODUTOS_VALIDOS.keys())}"
            )
        return v

    @field_validator("tipo")
    def tipo_deve_ser_valido(cls, v):
        if v not in ("entrada", "saida"):
            raise ValueError("'tipo' deve ser 'entrada' (compra) ou 'saida' (venda)")
        return v

    @field_validator("status")
    def status_deve_ser_valido(cls, v):
        if v not in ("pago", "pendente"):
            raise ValueError("'status' deve ser 'pago' ou 'pendente'")
        return v