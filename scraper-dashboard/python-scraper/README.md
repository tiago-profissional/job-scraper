# Multi-Source Tech Job Scraper

Um pipeline assíncrono e resiliente em Python para recolha, normalização, validação e deduplicação de vagas de tecnologia a partir de múltiplas fontes de dados públicas (APIs REST).

## 🚀 Funcionalidades

- **Coleta Multi-fonte**: Suporte extensível via adaptadores para Adzuna, Remotive, Arbeitnow, Greenhouse e Ashby.
- **Normalização Automática**: Padronização de títulos, modalidades de trabalho (`remote`, `hybrid`, `onsite`), senioridade, tecnologias e datas em UTC.
- **Validação Rígida**: Filtro automático de registos sem título, empresa, descrição válida ou com URLs fora dos domínios autorizados.
- **Deduplicação Inteligente**: Fusão em memória com algoritmo de chave primária composta (Fonte + ID externo, URL canónica sem parâmetros de rastreio `utm_*` e Hash SHA-256 do conteúdo).
- **Armazenamento Seguro (Atomic JSON)**: Persistência transacional que impede a corrupção de ficheiros em caso de falhas durante a escrita.
- **Resiliência e Paginação**: Suporte nativo a *exponential backoff*, *retries* automáticos para erros HTTP 429/5xx e limite configurável de páginas.

## 📁 Estrutura do Projeto

```text
python-scraper/
├── data/
│   ├── raw/          # Payloads originais das APIs
│   └── processed/    # Vagas validadas e normalizadas em JSON
├── scraper/
│   ├── deduplication/# Algoritmos de deduplicação e fusão (merge)
│   ├── fetching/     # Clientes HTTP resilientes (httpx)
│   ├── models/       # Modelos de dados Pydantic (RawJob e NormalizedJob)
│   ├── normalization/# Limpeza de HTML, parsing de datas e enums
│   ├── sources/      # Adaptadores específicos de cada fonte (JobSourceAdapter)
│   ├── storage/      # Persistência segura em UTF-8 com escrita atômica
│   └── validation/   # Regras de integridade de vagas
├── tests/            # Suíte de testes unitários com pytest
├── main.py           # Pipeline principal de execução
├── pytest.ini
└── requirements.txt