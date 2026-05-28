"""
main.py
-------
Ponto de entrada da aplicação. É o primeiro arquivo que roda quando você inicia a API.

Para rodar: uvicorn app.main:app --reload --port 8000
Depois acesse: http://localhost:8000/docs  ← documentação automática gerada pelo FastAPI
"""

from fastapi import FastAPI
from app.api.routes import router
from app.models.predictor import carregar_modelo

# Cria a aplicação FastAPI com metadados que aparecem na documentação
app = FastAPI(
    title="Biomassa IA — Motor Preditivo",
    docs_url=None
    redoc_url="/docs"
    description="Serviço de previsão de crescimento de biomassa usando Machine Learning.",
    version="1.0.0",
    contact={"name": "Equipe de IA"},
)

# Registra as rotas definidas em routes.py
app.include_router(router)


@app.on_event("startup")
async def ao_iniciar():
    """
    Roda automaticamente quando a API sobe.
    Carrega o modelo na memória ANTES de receber qualquer requisição.
    Assim a primeira chamada não fica lenta esperando o modelo carregar.
    """
    print("Iniciando serviço de IA...")
    carregar_modelo()
    print("API pronta para receber requisições.")


@app.get("/", include_in_schema=False)
def raiz():
    return {"mensagem": "Biomassa IA está no ar. Acesse /docs para a documentação."}
