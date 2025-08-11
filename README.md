## Agentes Contábeis — NF‑e Parser (XML/PDF), Classificação e UI

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![uv](https://img.shields.io/badge/uv-Dependency%20Manager-4c1)](https://github.com/astral-sh/uv)
[![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)

Plataforma em Python para ler NF‑e por XML ou PDF (DANFE), extrair um `NFePayload` validado com Pydantic, executar um fluxo com LangGraph, expor endpoints FastAPI e disponibilizar uma UI moderna em Streamlit. Agora inclui extração via LLM para PDFs, suporte a múltiplos provedores (OpenAI, Gemini, Groq), CLIs, exemplos e automação via `run.bat` (XML e PDF).

---

### Sumário
- [Destaques](#destaques)
- [Arquitetura (visão rápida)](#arquitetura-visão-rápida)
- [Quick Start](#quick-start)
- [Instalação (uv)](#instalação-uv)
- [Como executar](#como-executar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Schema de dados](#schema-de-dados)
- [Automação Windows](#automação-windows)
- [Logs e troubleshooting](#logs-e-troubleshooting)
- [Publicar no GitHub](#publicar-no-github)

---

### Destaques
- **Parser NF‑e (XML) robusto**: `xmltodict` + sanitização pré‑validação.
- **Parser NF‑e (PDF/DANFE)**: PyMuPDF para extração de texto (+ OCR opcional via Tesseract) e extração com LLM (LangChain). Suporta provedores OpenAI, Gemini e Groq; saída saneada e validada em `NFePayload`.
- **Modelos Pydantic**: validação clara de `NFePayload` e `NFeItem`.
- **Fluxo LangGraph**: estado tipado e execução determinística.
- **API + UI**: integração FastAPI e Streamlit com experiência aprimorada.
- **DX**: `uv` para ambientes rápidos e `pytest` para testes.

---

### Arquitetura (visão rápida)
```mermaid
flowchart TD
  A["XML da NF-e"] --> B["XmlParserAgent"]
  P["PDF (DANFE)"] --> L["PdfParserAgent (LLM)"]
  B --> C{"Validação Pydantic"}
  L --> C
  C -->|ok| D["NFePayload"]
  C -->|falha| E["Erro/Log"]
  D --> F["Workflow LangGraph"]
  F --> G["Resultado"]
  G --> H{"Needs Review?"}
  H -->|sim| I["Input Humano opcional"]
  H -->|não| J["Saída Final"]
```

---

## Quick Start
1) Crie a venv e instale dependências (usando `uv`):
```powershell
uv venv .venv; ./.venv/Scripts/Activate.ps1; uv pip sync requirements.txt
```
2) Rode os testes:
```powershell
uv run -m pytest -q
```
3) Suba API e UI (em dois terminais):
```powershell
uv run uvicorn src.api.main:app --reload
uv run streamlit run src/app/streamlit_app.py
```

---

## Instalação (uv)
Requisitos: Python 3.10+, Git, PowerShell (para `run.bat`).

Instale o `uv` se necessário:
```powershell
pip install uv
```

Crie ambiente e sincronize:
```powershell
uv venv .venv
./.venv/Scripts/Activate.ps1
uv pip sync requirements.txt
```

Atualize dependências após editar `requirements.txt`:
```powershell
uv pip sync requirements.txt
```

---

## Como executar

| Tarefa | Comando |
|---|---|
| Testes | `uv run -m pytest -q` |
| Parser simples (CLI) | `uv run -m src.app.parse_cli --xml data/exemplos/nota_minima.xml` |
| Workflow LangGraph (XML) | `uv run -m src.app.run_graph --xml data/exemplos/nota_minima.xml --log-level info` |
| Workflow LangGraph (PDF) | `uv run -m src.app.run_graph --pdf data/exemplos/pdf/3524036...8397-nfe.pdf --log-level info` |
| Informar regime (opcional) | `--regime simples` (não use `*`) |
| Revisão humana (opcional) | `--human-review-json caminho\revisao.json` |
| API FastAPI | `uv run uvicorn src.api.main:app --reload` |
| UI Streamlit | `uv run streamlit run src/app/streamlit_app.py` |

No painel lateral da UI, configure a URL do backend (ex.: `http://127.0.0.1:8000`) e clique em “Testar”.

---

### Endpoints principais (API)

Classificar por caminho:
- `POST /classificar/path` → XML via caminho `xml_path`
- `POST /classificar/pdf_path` → PDF via caminho `pdf_path`

Classificar por upload:
- `POST /classificar/xml` → upload de `xml_file`
- `POST /classificar/pdf` → upload de `pdf_file`

Revisão humana por caminho/upload (mesma estrutura de JSON `human_review_input`):
- `POST /classificar/review/path` (XML) | `POST /classificar/review/pdf_path` (PDF)
- `POST /classificar/review/xml` (upload XML) | `POST /classificar/review/pdf` (upload PDF)

---

## Estrutura do projeto
```text
.
├─ src/
│  ├─ agents/
│  │  ├─ xml_parser_agent.py
│  │  ├─ pdf_parser_agent.py
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
│  └─ exemplos/
├─ data_sources/
│  └─ contas_por_cfop.csv
├─ requirements.txt
├─ run.bat
└─ .gitignore
```

---

## LLM e .env

O parser de PDF usa LLM via LangChain. Configure via `.env` (carregado automaticamente):

- `PDF_LLM_PROVIDER` = `openai` | `gemini` | `groq` (default: `openai`)
- Chaves por provedor: `OPENAI_API_KEY` | `GOOGLE_API_KEY` | `GROQ_API_KEY`
- `PDF_LLM_MODEL` (defaults):
  - openai: `gpt-4o-mini`
  - gemini: `gemini-1.5-pro`
  - groq: `llama-3.1-70b-versatile`
- `PDF_LLM_TEMPERATURE` (default: `0.0`)

Observações para PDF:
- OCR automático (quando o PDF não tem camada de texto). Requer Tesseract instalado no SO.
- A saída da LLM é saneada antes de validar (`cfop` 4 dígitos, `UF` upper, `NCM` inválido → `null`, números normalizados).

---

## Schema de dados
`NFePayload` (mínimo):

| Campo | Tipo | Descrição |
|---|---|---|
| `cfop` | `str` (4 dígitos) | CFOP da operação |
| `emitente_uf` | `UF` | UF do emitente (`SP`, `RJ`, `MG`, `ES`, `OUTRO`) |
| `destinatario_uf` | `UF` | UF do destinatário |
| `valor_total` | `float` | Valor total da NF‑e (≥ 0) |
| `itens` | `List[NFeItem]` | Itens com `descricao`, `ncm`, `valor` |

Notas:
- `ncm` inválido é sanitizado para `None` antes da validação.
- Acesso seguro a dicionários com `safe_get`.

---

## Automação Windows
Execute:
```powershell
./run.bat
```
O script:
- Busca XMLs e PDFs em `data/exemplos/` (recursivo)
- Executa o workflow para cada arquivo (usa `--xml` ou `--pdf` conforme a extensão)
- Salva logs/JSONs em `logs/`
- Gera `logs/summary.csv` (`ok`, `needs_review`, `reason`)
- Inicia loop de revisão humana quando necessário (sem CFOP; pergunta regime/contas)

---

## Logs e troubleshooting
- Ajuste o nível com `--log-level` nos CLIs (ex.: `debug`, `info`).
- Se faltar dependência no `pytest` (ex.: `pluggy`), rode `uv pip sync requirements.txt`.
- No `run.bat`, pipes `|` e parênteses estão escapados (PowerShell).
- Se mudar a porta do backend, atualize a URL na UI.
- PDF/LLM: verifique as chaves (`OPENAI_API_KEY`/`GOOGLE_API_KEY`/`GROQ_API_KEY`) e o `PDF_LLM_PROVIDER`. Para OCR, instale Tesseract e garanta que está no PATH.

---

## Publicar no GitHub
Com GitHub CLI:
```powershell
git init -b main
git add -A
git commit -m "chore: initial commit"
gh repo create Agentes_Contabeis --private --source . --remote origin --push
```

Manual (repo vazio no site):
```powershell
git init -b main
git add -A
git commit -m "chore: initial commit"
git remote add origin https://github.com/SEU_USUARIO/Agentes_Contabeis.git
git push -u origin main
```

---

## Licença
Defina a licença (ex.: MIT) ou mantenha como proprietária.

---

## Suporte
Abra uma issue com detalhes (inclua logs e o XML se possível) ou ajuste o nível de log para coletar mais contexto durante a execução.


