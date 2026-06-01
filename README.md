# Sincronizacao de Estoque — Estoca → Omie

Integracao que le o estoque disponivel no WMS da **Estoca** e grava o ajuste
no ERP **Omie** (Filial 002). Roda automaticamente via GitHub Actions.

## Fluxo

```
ESTOCA (WMS)  →  OMIE (ERP, Filial 002)  →  VNDA (loja)
   le estoque       grava ajuste              atualiza sozinho
   [este script] →  [este script]            [integracao nativa Omie↔Vnda]
```

O estoque real vem da **Estoca** (armazem), este script grava o ajuste no
**Omie** (Filial 002), e o **Omie propaga automaticamente para a Vnda** pela
integracao nativa de e-commerce do Omie. Ou seja: este projeto cobre a etapa
Estoca → Omie; a etapa Omie → Vnda acontece em cascata, sem codigo proprio.

Importante: como a Vnda atualiza em cascata, qualquer ajuste de estoque feito
por este script reflete na loja. Validar os primeiros disparos com cuidado.

## Estrutura

```
.
├── main.py                      # orquestrador
├── requirements.txt             # dependencias
├── .env.example                 # modelo de variaveis (copiar para .env)
├── .gitignore
├── .github/workflows/
│   └── sync-estoque.yml         # agendamento (3x/dia)
└── utils/
    ├── ConsultaEstoca.py        # le estoque da Estoca
    └── AtualizaOmie.py          # grava ajuste no Omie
```

## Variaveis de ambiente

| Variavel | Sistema | Descricao | Status |
|----------|---------|-----------|--------|
| BASE_URL_ESTOCA | Estoca | `https://api.estoca.com.br` | OK |
| ESTOCA_ENDPOINT | Estoca | `/inventories` | OK |
| API_KEY_ESTOCA | Estoca | chave do header `X-Api-Key` | **PENDENTE** |
| WAREHOUSE | Estoca | ID do armazem | **PENDENTE** |
| OMIE_PRODUTO_URL | Omie | URL ConsultarProduto | OK |
| OMIE_ESTOQUE_URL | Omie | URL IncluirAjusteEstoque | OK |
| APP_KEY_OMIE | Omie | app_key da Filial 002 | OK |
| APP_SECRET | Omie | app_secret da Filial 002 | OK |

## Rodar localmente

```bash
pip install -r requirements.txt
cp .env.example .env      # depois preencha o .env com os valores reais
python main.py
```

## Deploy (GitHub Actions)

1. Suba este repositorio na organizacao (repo **privado**).
2. Em **Settings → Secrets and variables → Actions**, cadastre cada variavel
   da tabela acima como *Repository secret* (mesmos nomes).
3. Em **Actions**, abra o workflow e clique em **Run workflow** para testar.
4. Confira os logs. Se rodou limpo, o agendamento assume sozinho.

O agendamento roda as 06h, 12h e 18h (horario de SP). Para mudar, edite as
linhas `cron` em `.github/workflows/sync-estoque.yml`.

## Pendencias

- [ ] Obter `API_KEY_ESTOCA` e `WAREHOUSE` (chamado aberto na Estoca).
- [ ] Validar se a lista de SKUs em `utils/ConsultaEstoca.py` esta atualizada.
- [ ] Testar fluxo completo apos receber as credenciais.
- [ ] Confirmar que o ajuste no Omie reflete corretamente na Vnda (cascata nativa).
- [ ] Avaliar alerta de falha (email/mensagem) ao fim da execucao.

## Seguranca

- Nunca commitar o `.env` real (ja protegido pelo `.gitignore`).
- Credenciais vivem apenas nos Secrets do GitHub em producao.
- Recomenda-se rotacionar credenciais que ja circularam fora do cofre.
