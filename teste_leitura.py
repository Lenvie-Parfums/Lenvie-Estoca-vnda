"""
TESTE SOMENTE LEITURA — nao grava nada no Omie.

Consulta a Estoca para uma amostra de SKUs (todos os kits conhecidos + alguns PA)
e imprime, para cada um: a quantidade 'available' e como o codigo o classifica
(KIT ou PA). Serve para validar os numeros contra o painel da Estoca e checar
se a lista de kits do codigo esta correta.

Pode ser apagado depois que o projeto estiver validado.
"""
import os
import logging
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# Lista de kits conforme o codigo atual (SKUS_KITS do AtualizaOmie).
SKUS_KITS = {
    "101002022", "101002021", "102022380", "102022150", "90100001", "14093020",
    "14099020", "10131874", "14093320", "14090220", "14090020", "14097920",
    "14098020", "14012020", "10408470", "10137474", "10139274", "10134074",
}

# Amostra de teste: todos os kits presentes na lista principal + alguns PA,
# incluindo os dois SKUs que voce indicou serem kits mas estao como PA.
SKUS_TESTE = [
    # --- kits conforme o codigo ---
    "10408470", "90100001", "14012020", "14097920", "14090020", "14093020",
    "14090220", "14093320", "14098020", "14099020", "102022150", "102022380",
    # --- classificados como PA, mas voce indicou serem kits ---
    "102026380", "102059380",
    # --- PA para comparacao ---
    "102062150", "102040445", "102079380",
]


def testar_leitura_estoca():
    base_url = os.getenv("BASE_URL_ESTOCA")
    api_key = os.getenv("API_KEY_ESTOCA")
    warehouse = os.getenv("WAREHOUSE")
    endpoint = os.getenv("ESTOCA_ENDPOINT", "/inventories")

    log.info("Verificando variaveis de ambiente:")
    log.info(f"  BASE_URL_ESTOCA definida? {'SIM' if base_url else 'NAO'}")
    log.info(f"  API_KEY_ESTOCA definida?  {'SIM' if api_key else 'NAO'}")
    log.info(f"  WAREHOUSE definida?       {'SIM' if warehouse else 'NAO'}")

    if not all([base_url, api_key, warehouse]):
        log.error("Faltam variaveis de ambiente. Confira os Secrets no GitHub.")
        raise SystemExit(1)

    url = base_url.rstrip("/") + endpoint
    headers = {"X-Api-Key": api_key, "X-Api-Version": "v1"}

    # A Estoca aceita ate 50 SKUs por chamada; a amostra cabe em uma so.
    params = {"warehouse": warehouse, "skus": ",".join(SKUS_TESTE)}

    log.info(f"Consultando {len(SKUS_TESTE)} SKUs de teste na Estoca...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        log.error(f"Falha de conexao com a Estoca: {e}")
        raise SystemExit(1)

    log.info(f"Status HTTP: {response.status_code}")
    if response.status_code != 200:
        log.error(f"Resposta nao-200. Corpo: {response.text[:500]}")
        raise SystemExit(1)

    dados = response.json()
    data = dados.get("data", [])
    if isinstance(data, dict):
        data = [data]

    # Indexa por SKU para imprimir na ordem da amostra
    por_sku = {p.get("product_sku"): p for p in data}

    log.info("=" * 60)
    log.info(f"{'SKU':<14}{'AVAILABLE':<12}{'CLASSIF. CODIGO':<16}")
    log.info("-" * 60)
    for sku in SKUS_TESTE:
        p = por_sku.get(sku)
        classif = "KIT" if sku in SKUS_KITS else "PA"
        if p is None:
            log.info(f"{sku:<14}{'(nao voltou)':<12}{classif:<16}")
        else:
            avail = p.get("available", "?")
            log.info(f"{sku:<14}{str(avail):<12}{classif:<16}")
    log.info("=" * 60)

    faltando = [s for s in SKUS_TESTE if s not in por_sku]
    if faltando:
        log.warning(f"SKUs que NAO voltaram: {faltando}")

    log.info("TESTE DE LEITURA CONCLUIDO. Nada foi gravado no Omie.")


if __name__ == "__main__":
    testar_leitura_estoca()