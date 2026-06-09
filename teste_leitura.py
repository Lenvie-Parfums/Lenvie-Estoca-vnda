"""
TESTE SOMENTE LEITURA — nao grava nada no Omie.

Consulta a Estoca para uma lista pequena de SKUs e imprime o que voltou.
Serve para validar credenciais (API_KEY_ESTOCA, WAREHOUSE), conexao e
formato da resposta, sem nenhum risco de alterar estoque.

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

# 3 SKUs de teste: 2 produtos normais (PA) + 1 kit.
SKUS_TESTE = [
    "102059380",  # PA
    "102026380",  # PA
    "10408470",   # KIT
]


def testar_leitura_estoca():
    base_url = os.getenv("BASE_URL_ESTOCA")
    api_key = os.getenv("API_KEY_ESTOCA")
    warehouse = os.getenv("WAREHOUSE")
    endpoint = os.getenv("ESTOCA_ENDPOINT", "/inventories")

    # Confere se os secrets chegaram (sem imprimir os valores!)
    log.info("Verificando variaveis de ambiente:")
    log.info(f"  BASE_URL_ESTOCA definida? {'SIM' if base_url else 'NAO'}")
    log.info(f"  API_KEY_ESTOCA definida?  {'SIM' if api_key else 'NAO'}")
    log.info(f"  WAREHOUSE definida?       {'SIM' if warehouse else 'NAO'}")

    if not all([base_url, api_key, warehouse]):
        log.error("Faltam variaveis de ambiente. Confira os Secrets no GitHub.")
        raise SystemExit(1)

    url = base_url.rstrip("/") + endpoint
    headers = {"X-Api-Key": api_key, "X-Api-Version": "v1"}
    params = {"warehouse": warehouse, "skus": ",".join(SKUS_TESTE)}

    log.info(f"Consultando {len(SKUS_TESTE)} SKUs de teste na Estoca...")
    log.info(f"URL: {url}")

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

    log.info("=" * 55)
    log.info(f"RESULTADO — {len(data)} produto(s) retornado(s):")
    for p in data:
        sku = p.get("product_sku", "?")
        avail = p.get("available", "?")
        log.info(f"  SKU {sku}  ->  available: {avail}")
    log.info("=" * 55)

    # Avisa se algum SKU pedido nao voltou
    voltaram = {p.get("product_sku") for p in data}
    faltando = [s for s in SKUS_TESTE if s not in voltaram]
    if faltando:
        log.warning(f"SKUs pedidos que NAO voltaram: {faltando}")

    log.info("TESTE DE LEITURA CONCLUIDO. Nada foi gravado no Omie.")


if __name__ == "__main__":
    testar_leitura_estoca()
