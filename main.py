from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import supabase
from models import Transacao
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "wallys-gelo-secret-2024")
ALGORITHM = "HS256"
security = HTTPBearer()

def criar_token(usuario: str):
    expira = datetime.utcnow() + timedelta(hours=12)
    return jwt.encode(
        {"sub": usuario, "exp": expira},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def verificar_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/")
def home():
    return {"msg": "API Wallys do Gelo ONLINE"}

# =========================
# TRANSAÇÕES
# =========================

@app.post("/transacoes")
def criar_transacao(
    transacao: Transacao,
    usuario=Depends(verificar_token)
):
    data = supabase.table("transacoes").insert(
        transacao.dict(exclude_none=True)
    ).execute()

    return data

@app.get("/transacoes")
def listar_transacoes(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute()
    return data

@app.put("/transacoes/{id}")
def editar_transacao(
    id: str,
    transacao: Transacao,
    usuario=Depends(verificar_token)
):
    data = supabase.table("transacoes").update(
        transacao.dict(exclude_none=True)
    ).eq("id", id).execute()

    return data

@app.delete("/transacoes/{id}")
def deletar_transacao(
    id: str,
    usuario=Depends(verificar_token)
):
    data = supabase.table("transacoes").delete().eq(
        "id",
        id
    ).execute()

    return data

# =========================
# RESUMO
# =========================

@app.get("/resumo")
def resumo(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute().data

    receita = sum(
        t["valor"]
        for t in data
        if t["tipo"] == "saida"
        and t["status"] == "pago"
    )

    custos = sum(
        t["valor"]
        for t in data
        if t["tipo"] == "entrada"
        and t["status"] == "pago"
    )

    pendente = sum(
        t["valor"]
        for t in data
        if t["status"] == "pendente"
    )

    return {
        "receita_total": receita,
        "custos_total": custos,
        "lucro_liquido": receita - custos,
        "pendente": pendente
    }

# =========================
# RELATÓRIO CSV
# =========================

@app.get("/relatorio/csv")
def exportar_csv(usuario=Depends(verificar_token)):
    data = supabase.table("transacoes").select("*").execute().data

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Tipo",
        "Produto",
        "Valor",
        "Status",
        "Observações",
        "Data Venda"
    ])

    for t in data:
        writer.writerow([
            t.get("id", ""),
            t.get("tipo", ""),
            t.get("produto", ""),
            t.get("valor", ""),
            t.get("status", ""),
            t.get("observacoes", ""),
            t.get("data_venda", "")
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=relatorio-wallys.csv"
        }
    )

# =========================
# LOGIN
# =========================

class Login(BaseModel):
    usuario: str
    senha: str

@app.post("/login")
def login(dados: Login):

    result = supabase.table("usuarios").select("*").eq(
        "usuario",
        dados.usuario
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=401,
            detail="Usuário não encontrado"
        )

    user = result.data[0]

    if not bcrypt.checkpw(
        dados.senha.encode(),
        user["senha"].encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Senha incorreta"
        )

    token = criar_token(dados.usuario)

    return {
        "msg": "ok",
        "usuario": dados.usuario,
        "token": token
    }

# =========================
# CADASTRO
# =========================

class Cadastro(BaseModel):
    usuario: str
    senha: str

@app.post("/cadastro")
def cadastro(dados: Cadastro):

    existe = supabase.table("usuarios").select("*").eq(
        "usuario",
        dados.usuario
    ).execute()

    if existe.data:
        raise HTTPException(
            status_code=400,
            detail="Usuário já existe"
        )

    hash_senha = bcrypt.hashpw(
        dados.senha.encode("utf-8"),
        bcrypt.gensalt()
    )

    supabase.table("usuarios").insert({
        "usuario": dados.usuario,
        "senha": hash_senha.decode("utf-8")
    }).execute()

    return {
        "msg": "Usuário cadastrado com sucesso"
    }