from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import supabase
from models import Transacao, PRODUTOS_VALIDOS
from pydantic import BaseModel
import csv
import io
import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os

app = FastAPI(title="Sistema Wallys do Gelo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wallys100.github.io"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY não configurada. Configure a variável de ambiente.")

ALGORITHM = "HS256"
security = HTTPBearer()


def criar_token(usuario: str):
    expira = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode({"sub": usuario, "exp": expira}, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.get("/")
def home():
    return {"msg": "API Wallys do Gelo ONLINE"}


# ─────────────────────────────────────────────
#  TRANSAÇÕES
# ─────────────────────────────────────────────

@app.post("/transacoes")
def criar_transacao(transacao: Transacao, usuario=Depends(verificar_token)):
    dados = transacao.dict()

    # [SEGURANÇA] Bloqueia produto não mapeado (nunca deve chegar aqui
    # pois o validator do modelo já rejeita, mas garante a camada extra)
    produto = dados.get("produto", "")
    if produto not in PRODUTOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo de gelo não definido. Produto '{produto}' não reconhecido."
        )

    # [TAG AUTOMÁTICA] Preenche secao e sku pelo nome do produto
    dados["secao"] = PRODUTOS_VALIDOS[produto]["secao"]
    dados["sku"]   = PRODUTOS_VALIDOS[produto]["sku"]

    data = supabase.table("transacoes").insert(dados).execute()
    return data


@app.get("/transacoes")
def listar_transacoes(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").order("created_at", desc=True).execute()
    return data


@app.put("/transacoes/{id}")
def editar_transacao(id: str, transacao: Transacao, usuario=Depends(verificar_token)):
    dados = transacao.dict()

    # Re-aplica tags ao editar também
    produto = dados.get("produto", "")
    if produto in PRODUTOS_VALIDOS:
        dados["secao"] = PRODUTOS_VALIDOS[produto]["secao"]
        dados["sku"]   = PRODUTOS_VALIDOS[produto]["sku"]

    data = supabase.table("transacoes").update(dados).eq("id", id).execute()
    return data


@app.delete("/transacoes/{id}")
def deletar_transacao(id: str, usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").delete().eq("id", id).execute()
    return data


# ─────────────────────────────────────────────
#  RESUMO FINANCEIRO (dashboard)
# ─────────────────────────────────────────────

@app.get("/resumo")
def resumo(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute().data

    # Totais gerais
    receita = sum(t["valor"] for t in data if t["tipo"] == "saida"   and t["status"] == "pago")
    custos  = sum(t["valor"] for t in data if t["tipo"] == "entrada" and t["status"] == "pago")
    pendente = sum(t["valor"] for t in data if t["status"] == "pendente")

    # Breakdown por seção (cubos / saborizado)
    secoes = {}
    for t in data:
        secao = t.get("secao") or "sem_secao"
        if secao not in secoes:
            secoes[secao] = {"receita": 0.0, "custos": 0.0}
        if t["tipo"] == "saida"   and t["status"] == "pago":
            secoes[secao]["receita"] += t["valor"]
        if t["tipo"] == "entrada" and t["status"] == "pago":
            secoes[secao]["custos"] += t["valor"]

    # Breakdown por fornecedor (chave única para relatórios)
    fornecedores = {}
    for t in data:
        if t["tipo"] != "entrada" or t["status"] != "pago":
            continue
        forn = t.get("fornecedor") or "sem_fornecedor"
        secao = t.get("secao") or "sem_secao"
        chave = f"{secao}::{forn}"
        fornecedores[chave] = fornecedores.get(chave, 0.0) + t["valor"]

    return {
        "receita_total": receita,
        "custos_total": custos,
        "lucro_liquido": receita - custos,
        "pendente": pendente,
        "por_secao": secoes,
        "custos_por_fornecedor": fornecedores,
    }


# ─────────────────────────────────────────────
#  ESTOQUE SEPARADO POR PRODUTO
# ─────────────────────────────────────────────

@app.get("/estoque")
def estoque(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute().data

    contadores = {secao: 0 for secao in set(v["secao"] for v in PRODUTOS_VALIDOS.values())}

    for t in data:
        secao = t.get("secao")
        qtd   = t.get("quantidade") or 0
        if secao not in contadores:
            continue
        if t["tipo"] == "entrada":
            contadores[secao] += qtd   # compra → entrada no estoque
        elif t["tipo"] == "saida":
            contadores[secao] -= qtd   # venda  → saída do estoque

    return {
        "estoque_cubos":      contadores.get("cubos", 0),
        "estoque_saborizado": contadores.get("saborizado", 0),
    }


# ─────────────────────────────────────────────
#  RELATÓRIO CSV
# ─────────────────────────────────────────────

@app.get("/relatorio/csv")
def exportar_csv(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute().data

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tipo", "Seção", "SKU", "Produto", "Fornecedor",
                    "Valor", "Quantidade", "Status", "Observações", "Data"])
    for t in data:
        writer.writerow([
            t.get("id", ""),
            t.get("tipo", ""),
            t.get("secao", ""),
            t.get("sku", ""),
            t.get("produto", ""),
            t.get("fornecedor", ""),
            t.get("valor", ""),
            t.get("quantidade", ""),
            t.get("status", ""),
            t.get("observacoes", ""),
            t.get("created_at", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=relatorio-wallys.csv"},
    )


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────

class Login(BaseModel):
    usuario: str
    senha: str


@app.post("/login")
def login(dados: Login):
    result = supabase.table("usuarios").select("*").eq("usuario", dados.usuario).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    user = result.data[0]
    if not bcrypt.checkpw(dados.senha.encode(), user["senha"].encode()):
        raise HTTPException(status_code=401, detail="Senha incorreta")
    token = criar_token(dados.usuario)
    return {"msg": "ok", "usuario": dados.usuario, "token": token}


class Cadastro(BaseModel):
    usuario: str
    senha: str


@app.post("/cadastro")
def cadastro(dados: Cadastro):
    existe = supabase.table("usuarios").select("*").eq("usuario", dados.usuario).execute()
    if existe.data:
        raise HTTPException(status_code=400, detail="Usuário já existe")
    hash_senha = bcrypt.hashpw(dados.senha.encode("utf-8"), bcrypt.gensalt())
    supabase.table("usuarios").insert({
        "usuario": dados.usuario,
        "senha": hash_senha.decode("utf-8"),
    }).execute()
    return {"msg": "Usuário cadastrado com sucesso"}