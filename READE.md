# 🌱 Biomassa IA — Motor Preditivo de Crescimento de Microalgas

API de Machine Learning para previsão de crescimento de biomassa em tanques de cultivo, com integração ao Oracle Database.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação local](#instalação-local)
- [Configuração](#configuração)
- [Executando a API](#executando-a-api)
- [Endpoints](#endpoints)
- [Treinamento do Modelo](#treinamento-do-modelo)
- [Banco de Dados Oracle](#banco-de-dados-oracle)
- [Testes](#testes)
- [Deploy na OCI com Docker](#deploy-na-oci-com-docker)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Visão Geral

Este serviço expõe uma API REST que recebe dados de sensores IoT (pH, temperatura, turbidez, luminosidade, radiação PAR) e retorna a previsão de biomassa (g/L) para as próximas 48h, a data estimada de colheita e a confiança do modelo.

O modelo é um **Random Forest Regressor** (scikit-learn) treinado com histórico de medições e colheitas armazenados no Oracle.

**Stack:**
- Python 3.11+
- FastAPI + Uvicorn
- scikit-learn (Random Forest)
- Oracle Database (via `python-oracledb`)
- Docker + Docker Compose

---

## Arquitetura

```
Sensores IoT / API Java
        │
        ▼ POST /api/v1/predict
┌───────────────────┐
│   FastAPI (8000)  │
│  ┌─────────────┐  │
│  │ predictor   │◄─┼── model.pkl + scaler.pkl (carregados na memória)
│  └─────────────┘  │
└───────────────────┘
        │
        ▼ INSERT
┌─────────────────────┐
│   Oracle Database   │
│  TB_METRICAS_TANQUE │
│  TB_PREVISOES_IA    │
│  TB_ALERTA_CRITICO  │
└─────────────────────┘
```

---

## Pré-requisitos

**Local:**
- Python 3.11+
- Docker e Docker Compose

**OCI:**
- VM Ubuntu 22.04 (Always Free é suficiente)
- Docker instalado na VM
- Porta 8000 liberada no Security List

---

## Instalação local

```bash
git clone https://github.com/GS1-2TDSPG-2026/gs1-python-LSTM.git
cd gs1-python-LSTM

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuração

```bash
cp .env.example .env
nano .env
```

```env
ORACLE_USER=system
ORACLE_PASSWORD=sua_senha_aqui
ORACLE_DSN=localhost:1521/XEPDB1
```

> **Nunca** commite o arquivo `.env`. Ele já está no `.gitignore`.

---

## Executando a API

### Desenvolvimento (sem Docker)

```bash
uvicorn app.main:app --reload --port 8000
```

### Produção (com Docker)

```bash
docker compose up -d
```

Acesse a documentação interativa em: **http://localhost:8000/docs**

---

## Endpoints

### `POST /api/v1/predict`

**Request body:**
```json
{
  "tanqueId": 1,
  "ph": 7.2,
  "temperatura": 26.5,
  "turbidez": 38.0,
  "luminosidade": 820,
  "radiacaoPar": 5.7
}
```

**Response `200 OK`:**
```json
{
  "tanqueId": 1,
  "biomassaEstimada": 14.87,
  "dataPrevistaColheita": "2026-06-15",
  "confianca": 91.3,
  "status": "CRESCIMENTO_IDEAL"
}
```

**Status possíveis:**

| Status | Biomassa (g/L) |
|---|---|
| `CRESCIMENTO_IDEAL` | ≥ 15.0 |
| `CRESCIMENTO_MODERADO` | ≥ 10.0 |
| `CRESCIMENTO_LENTO` | ≥ 5.0 |
| `ALERTA_BAIXA_BIOMASSA` | < 5.0 |

### `GET /api/v1/health`

```json
{
  "status": "ok",
  "servico": "biomassa-ia",
  "versao": "1.0.0"
}
```

---

## Treinamento do Modelo

### Primeira vez (dados sintéticos)

```bash
python -m training.train
```

Gera `artifacts/model.pkl` e `artifacts/scaler.pkl` com 500 amostras sintéticas.

> Com Docker, o treinamento inicial roda automaticamente durante o `docker build`.

### Com dados reais do Oracle

Edite o bloco `__main__` em `training/train.py`:

```python
if __name__ == "__main__":
    df = carregar_dados_oracle()
    treinar(df)
```

---

## Banco de Dados Oracle

Execute no SQL Developer ou SQL*Plus:

```sql
CREATE TABLE TB_PREVISOES_IA (
    id_previsao        NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tanque          NUMBER         NOT NULL,
    id_dado_orbital    NUMBER,
    dt_previsao        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    biomassa_g_l       NUMBER(10, 2),
    dt_pico_previsto   DATE,
    confianca_pct      NUMBER(5, 2),
    modelo_utilizado   VARCHAR2(50)
);

CREATE TABLE TB_ALERTA_CRITICO (
    id_alerta     NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tanque     NUMBER        NOT NULL,
    id_metrica    NUMBER,
    tipo_alerta   VARCHAR2(50),
    severidade    VARCHAR2(20),
    mensagem      VARCHAR2(255),
    status        VARCHAR2(20) DEFAULT 'ABERTO',
    dt_alerta     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Verificar conexão

```bash
python -c "from app.db.oracle import get_conexao; c = get_conexao(); print('✅ Conectado:', c.version)"
```

---

## Testes

```bash
pytest tests/ -v
```

| Teste | O que verifica |
|---|---|
| `test_status_crescimento_ideal` | Classificação ≥ 15 g/L |
| `test_status_crescimento_moderado` | Classificação ≥ 10 g/L |
| `test_status_crescimento_lento` | Classificação ≥ 5 g/L |
| `test_status_alerta` | Classificação < 5 g/L |
| `test_previsao_retorna_saida_valida` | Estrutura completa da resposta |
| `test_condicoes_ruins_geram_baixa_biomassa` | Sanity check do modelo |
| `test_schemas_valida_ph_invalido` | Validação Pydantic (pH > 14 rejeitado) |

---

## Deploy na OCI com Docker

### 1. Provisionar a VM

No Console da OCI, crie uma instância:
- Shape: `VM.Standard.E2.1.Micro` (Always Free) ou superior
- Imagem: **Ubuntu 22.04**
- Abra a porta `8000` no Security List da subnet

### 2. Instalar Docker na VM

```bash
ssh ubuntu@<IP_DA_SUA_VM>

sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Permite rodar docker sem sudo
sudo usermod -aG docker ubuntu
newgrp docker
```

### 3. Clonar e configurar o projeto

```bash
git clone https://github.com/GS1-2TDSPG-2026/gs1-python-LSTM.git
cd gs1-python-LSTM

cp .env.example .env
nano .env
```

### 4. Subir a aplicação

```bash
docker compose up -d --build
```

O `--build` garante que o modelo seja treinado na primeira vez. Nas próximas atualizações, o volume `./artifacts` preserva o `model.pkl` já treinado.

### 5. Verificar

```bash
# Status do container
docker compose ps

# Logs em tempo real
docker compose logs -f

# Testar o endpoint
curl http://localhost:8000/api/v1/health
```

### 6. Abrir porta no firewall da VM

```bash
sudo ufw allow 8000/tcp
```

Lembre-se também de liberar a porta `8000` no **Security List** da subnet no Console da OCI.

### Atualizar após mudanças no código

```bash
git pull
docker compose up -d --build
```

O container reinicia automaticamente se a VM for reiniciada (`restart: unless-stopped`).

---

## Estrutura do Projeto

```
gs1-python-LSTM/
├── app/
│   ├── api/
│   │   └── routes.py
│   ├── data/
│   │   └── preprocessor.py
│   ├── db/
│   │   └── oracle.py
│   ├── models/
│   │   ├── predictor.py
│   │   └── schemas.py
│   └── main.py
├── artifacts/
│   ├── model.pkl
│   └── scaler.pkl
├── tests/
│   └── test_predictor.py
├── training/
│   └── train.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Licença

MIT — veja o arquivo [LICENSE](LICENSE) para detalhes.