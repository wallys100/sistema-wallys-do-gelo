from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from database import supabase
from models import Transacao
from pydantic import BaseModel
import csv
import io

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
    result = supabase.table("usuarios").select("*").eq("usuario", dados.usuario).eq("senha", dados.senha).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")
    return {"msg": "ok", "usuario": dados.usuario}