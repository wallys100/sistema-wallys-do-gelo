from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from database import supabase
from models import Transacao
from pydantic import BaseModel
from fastapi import HTTPException
import csv
import io
import bcrypt

app = FastAPI(title="Sistema Wallys do Gelo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"msg": "API Wallys do Gelo ONLINE"}

@app.post("/transacoes")
def criar_transacao(transacao: Transacao):
    data = supabase.table("transacoes").insert(transacao.dict()).execute()
    return data

@app.get("/transacoes")
def listar_transacoes():
    data = supabase.table("transacoes").select("*").execute()
    return data

@app.get("/resumo")
def resumo():
    data = supabase.table("transacoes").select("*").execute().data
    receita = sum(t["valor"] for t in data if t["tipo"] == "saida" and t["status"] == "pago")
    custos  = sum(t["valor"] for t in data if t["tipo"] == "entrada")
    pendente = sum(t["valor"] for t in data if t["status"] == "pendente")
    return {"receita_total": receita, "custos_total": custos, "lucro_liquido": receita - custos, "pendente": pendente}

@app.get("/relatorio/csv")
def exportar_csv():
    data = supabase.table("transacoes").select("*").execute().data
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tipo", "Produto", "Valor", "Status", "Observações", "Data"])
    for t in data:
        writer.writerow([t.get("id",""), t.get("tipo",""), t.get("produto",""), t.get("valor",""), t.get("status",""), t.get("observacoes",""), t.get("created_at","")])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=relatorio-wallys.csv"})

class Login(BaseModel):
    usuario: str
    senha: str

@app.post("/login")
def login(dados: Login):
    result = supabase.table("usuarios").select("*").eq("usuario", dados.usuario).execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    user = result.data[0]

    senha_hash = user["senha"]

    if not bcrypt.checkpw(dados.senha.encode(), senha_hash.encode()):
        raise HTTPException(status_code=401, detail="Senha incorreta")

    return {"msg": "ok", "usuario": dados.usuario}

# DELETAR TRANSAÇÃO
@app.delete("/transacoes/{id}")
def deletar_transacao(id: str):
    data = supabase.table("transacoes").delete().eq("id", id).execute()
    return data

# EDITAR TRANSAÇÃO
@app.put("/transacoes/{id}")
def editar_transacao(id: str, transacao: Transacao):
    data = supabase.table("transacoes").update(transacao.dict()).eq("id", id).execute()
    return data

class Cadastro(BaseModel):
    usuario: str
    senha: str

@app.post("/cadastro")
def cadastro(dados: Cadastro):
    # verificar se já existe
    existe = supabase.table("usuarios").select("*").eq("usuario", dados.usuario).execute()

    if existe.data:
        raise HTTPException(status_code=400, detail="Usuário já existe")

    # gerar hash da senha
    senha_bytes = dados.senha.encode('utf-8')
    hash_senha = bcrypt.hashpw(senha_bytes, bcrypt.gensalt())

    # salvar no banco
    supabase.table("usuarios").insert({
        "usuario": dados.usuario,
        "senha": hash_senha.decode('utf-8')
    }).execute()

    return {"msg": "Usuário cadastrado com sucesso"}