## Agentes Contábeis — NF‑e Parser, Classificação e UI

Plataforma em Python para ler arquivos NF‑e (XML), extrair campos mínimos em um payload validado com Pydantic, executar um fluxo orquestrado com LangGraph e expor uma UI moderna em Streamlit. Inclui CLIs, API FastAPI, exemplos de XML e automação via `run.bat` para Windows.

### Principais componentes
- **XmlParserAgent**: lê NF‑e XML e gera `NFePayload` com: `cfop`, `emitente_uf`, `destinatario_uf`, `valor_total`, `itens[{descricao, ncm, valor}]`.
- **LangGraph workflow**: orquestra o parser e estados (`src/workflow/*`).
- **API FastAPI**: endpoints para classificação e health check (`src/api/main.py`).
- **CLIs**: `parse_cli.py` (parser simples) e `run_graph.py` (workflow completo, com revisão humana opcional).
- **Streamlit UI**: frontend para upload/visualização (`src/app/streamlit_app.py`).
- **Automação Windows**: `run.bat` processa todos os XMLs de `data/exemplos/`, registra logs e gera sumário.

---

## Requisitos
- Python 3.10+
- Git
- Windows PowerShell (para `run.bat`)
- Recomendado: `uv` para ambiente/execução

Instale o `uv` se necessário:
```powershell
pip install uv
```

---

## Instalação (usando uv)
Execute na raiz do projeto:
```powershell
uv venv .venv
./.venv/Scripts/Activate.ps1
uv pip sync requirements.txt
```

Atualize dependências depois de editar `requirements.txt`:
```powershell
uv pip sync requirements.txt
```

---

## Estrutura do projeto (resumo)
```text
.
├─ src/
│  ├─ agents/
│  │  ├─ xml_parser_agent.py
│  │  └─ classificador_contabil_agent.py
│  ├─ api/
│  │  └─ main.py
│  ├─ app/
│  │  ├─ parse_cli.py
│  │  ├─ run_graph.py
│  │  └─ streamlit_app.py
│  └─ workflow/
│     ├─ graph.py
│     ├─ nodes.py
│     └─ state.py
├─ data/
│  └─ exemplos/  # XMLs de exemplo
├─ data_sources/
│  └─ contas_por_cfop.csv
├─ requirements.txt
├─ run.bat
└─ .gitignore
```

---

## Como executar

### 1) Testes
```powershell
uv run -m pytest -q
```

### 2) CLI (parser simples)
```powershell
uv run -m src.app.parse_cli --xml data/exemplos/nota_minima.xml
```

### 3) Workflow LangGraph (com opções)
```powershell
uv run -m src.app.run_graph --xml data/exemplos/nota_minima.xml --log-level info

# Opcional: informar regime tributário (não envie "*", pois significa indeterminado)
uv run -m src.app.run_graph --xml data/exemplos/nota_minima.xml --regime simples

# Opcional: fornecer um JSON de revisão humana
uv run -m src.app.run_graph --xml data/exemplos/nota_minima.xml --human-review-json path\para\revisao.json
```

### 4) API FastAPI
```powershell
uv run uvicorn src.api.main:app --reload
```
Endpoints:
- `GET /health` → `{ "status": "ok" }`
- `POST /classificar` → recebe XML e retorna resultado de classificação

### 5) Streamlit UI
```powershell
uv run streamlit run src/app/streamlit_app.py
```
No painel lateral, configure a URL do backend (ex.: `http://127.0.0.1:8000`) e teste a conexão.

### 6) Automação Windows (`run.bat`)
Duplo‑clique em `run.bat` ou execute:
```powershell
./run.bat
```
O script:
- Busca XMLs em `data/exemplos/` (recursivo)
- Executa o workflow para cada arquivo
- Registra JSONs de saída em `logs/`
- Gera `logs/summary.csv` com `ok`, `needs_review` e motivo
- Se necessário, inicia um loop de revisão humana (sem CFOP; pergunta regime e contas)

---

## Modelos de dados (Pydantic)
`NFePayload` (campos mínimos):
- `cfop`: string de 4 dígitos
- `emitente_uf`: UF do emitente (`SP`, `RJ`, `MG`, `ES` ou `OUTRO`)
- `destinatario_uf`: UF do destinatário
- `valor_total`: número ≥ 0
- `itens`: lista de `NFeItem` com:
  - `descricao`: texto do item
  - `ncm`: 8 dígitos ou `None` (valores inválidos são sanitizados para `None`)
  - `valor`: total do item

Sanitizações: `xml_parser_agent.py` contempla `_sanitize_prod_for_model` para NCMs inválidos e `safe_get` para acesso seguro em dicionários.

---

## Logs
Todos os módulos possuem `logging`. Níveis podem ser controlados nos CLIs via `--log-level`.
Exemplos:
```powershell
uv run -m src.app.run_graph --xml data/exemplos/nota_minima.xml --log-level debug
uv run -m src.app.parse_cli --xml data/exemplos/nota_minima.xml --log-level warning
```

---

## Exemplos de dados
Diretório `data/exemplos/` contém variados cenários:
- `nota_minima.xml`
- `nota_varios_itens.xml`
- `nota_interestadual.xml`
- `nota_sem_nfeProc.xml`
- `nota_valores_virgula.xml`

---

## Dicas de solução de problemas
- Use sempre `uv run` para garantir que as libs executem dentro da venv criada pelo `uv`.
- Se o `pytest` reclamar de dependências como `pluggy`, rode `uv pip sync requirements.txt` novamente.
- No `run.bat`, pipes `|` e parênteses em mensagens estão escapados; mantenha PowerShell como shell padrão.
- Ajuste a URL do backend na UI se você trocar a porta do Uvicorn.

---

## Publicar no GitHub (resumo)
Com GitHub CLI:
```powershell
git init -b main
git add -A
git commit -m "chore: initial commit"
gh repo create Agentes_Contabeis --private --source . --remote origin --push
```

Manual (criando repo vazio no site):
```powershell
git init -b main
git add -A
git commit -m "chore: initial commit"
git remote add origin https://github.com/SEU_USUARIO/Agentes_Contabeis.git
git push -u origin main
```

---

## Licença
Defina a licença de sua preferência (ex.: MIT) ou mantenha como proprietária.

---

## Contato
Em caso de dúvidas, abra uma issue no repositório ou ajuste os parâmetros de log para coletar mais detalhes de execução.


