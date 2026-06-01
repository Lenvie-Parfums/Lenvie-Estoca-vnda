import requests
import json
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Credenciais da empresa Omie de destino (Filial 002).
# Os valores reais ficam no .env (local) e nos Secrets do GitHub (producao).
OMIE_PRODUTO_URL = os.getenv("OMIE_PRODUTO_URL")
OMIE_ESTOQUE_URL = os.getenv("OMIE_ESTOQUE_URL")
APP_KEY = os.getenv("APP_KEY_OMIE")
APP_SECRET = os.getenv("APP_SECRET")

## Lista SKU Kits ##

SKUS_KITS = {
    "101002022","101002021",
    "102022380","102022150",	
	"90100001",	"14093020",	
    "14099020",	"10131874",
    "14093320",	"14090220",	
    "14090020",	"14097920",	
    "14098020",	"14012020",	
    "10408470", "10137474",	
    "10139274",	"10134074",	
}

def consultar_produto_omie(codigo, max_retries=3, retry_delay=10, request_delay=3):
    """
    Consulta o produto no Omie pelo código (SKU).
    Retorna o id_prod se encontrado, ou None se nunca existir no Omie.
    """
    payload = {
        "call": "ConsultarProduto",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{"codigo": codigo}]
    }

    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                OMIE_PRODUTO_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60
            )

            if response.status_code == 429:
                log.warning(f"[{codigo}] Rate limit atingido. Tentativa {tentativa}. Esperando {retry_delay}s...")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            if response.status_code != 200:
                log.warning(f"[{codigo}] Erro {response.status_code}: {response.text}")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            data = response.json()
            codigo_produto = data.get("codigo_produto")

            if not codigo_produto:
                log.warning(f"[{codigo}] Produto não encontrado no Omie.")
                return None

            # Delay entre SKUs
            time.sleep(request_delay)
            return codigo_produto

        except requests.exceptions.RequestException as e:
            log.warning(f"[{codigo}] Falha de conexão: {e}. Tentativa {tentativa}. Retentando em {retry_delay}s...")
            time.sleep(retry_delay)
            tentativa += 1

    log.warning(f"[{codigo}] Falha definitiva após {max_retries} tentativas.")
    return None


def atualizar_estoque_omie(codigo_produto, quan, sku, obs="Ajuste automático por API", max_retries=3, retry_delay=10):
    """
    Atualiza o estoque do produto no Omie.
    """
    hoje = time.strftime("%d/%m/%Y")

    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [
            {
                "id_prod": codigo_produto,
                "data": hoje,
                "quan": str(quan),
                "obs": obs,
                "origem": "AJU",
                "tipo": "SLD",
                "motivo": "INV",
                "valor": 0
            }
        ]
    }

    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                OMIE_ESTOQUE_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60
            )

            if response.status_code == 429:
                log.warning(f"[{sku}] Rate limit no ajuste. Tentativa {tentativa}. Esperando {retry_delay}s...")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            if response.status_code != 200:
                log.warning(f"[{sku}] Erro {response.status_code}: {response.text}")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            log.info(f"[{sku}] Estoque atualizado com sucesso! id_prod={codigo_produto}, quantidade={quan}")
            return True

        except requests.exceptions.RequestException as e:
            log.warning(f"[{sku}] Falha de conexão: {e}. Tentativa {tentativa}. Retentando em {retry_delay}s...")
            time.sleep(retry_delay)
            tentativa += 1

    log.error(f"[{sku}] Falha definitiva ao atualizar estoque após {max_retries} tentativas.")
    return False


def atualizar_estoque_kit(codigo_produto, quan, sku, obs="Ajuste automático por API", max_retries=1, retry_delay=10):
    """
    Atualiza o estoque do kit no Omie.
    """
    hoje = time.strftime("%d/%m/%Y")

    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [
            {
                "id_prod": codigo_produto,
                "data": hoje,
                "quan": str(quan),
                "obs": obs,
                "origem": "AJU",
                "tipo": "ENT",
                "motivo": "INV",
                "valor": 0
            }
        ]
    }

    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                OMIE_ESTOQUE_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60
            )

            if response.status_code == 429:
                log.warning(f"[{sku}] Rate limit no ajuste. Tentativa {tentativa}. Esperando {retry_delay}s...")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            if response.status_code != 200:
                log.warning(f"[{sku}] Erro {response.status_code}: {response.text}")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            log.info(f"[{sku}] Estoque atualizado com sucesso! id_prod={codigo_produto}, quantidade={quan}")
            return True

        except requests.exceptions.RequestException as e:
            log.warning(f"[{sku}] Falha de conexão: {e}. Tentativa {tentativa}. Retentando em {retry_delay}s...")
            time.sleep(retry_delay)
            tentativa += 1

    log.error(f"[{sku}] Falha definitiva ao atualizar estoque após {max_retries} tentativas.")
    return False