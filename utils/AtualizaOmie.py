import requests
import json
import os
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Fuso de Sao Paulo. O servidor do GitHub Actions roda em UTC, entao a data
# precisa ser calculada no fuso do Brasil — senao o Omie recusa o ajuste com
# "Data do Movimento nao pode ser maior que a data atual".
TZ_SP = ZoneInfo("America/Sao_Paulo")


def data_hoje_sp():
    """Retorna a data de hoje no fuso de Sao Paulo, formato dd/mm/aaaa."""
    return datetime.now(TZ_SP).strftime("%d/%m/%Y")

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
    "102026380","102059380",
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

    log.error(f"[{codigo}] Falha definitiva após {max_retries} tentativas.")
    return None


def atualizar_estoque_omie(codigo_produto, quan, sku, obs="Ajuste automático por API", max_retries=3, retry_delay=10):
    """
    Atualiza o estoque do produto no Omie.
    """
    hoje = data_hoje_sp()

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

            if response.status_code == 200:
                resp_txt = response.text
                # O Omie as vezes responde 200 mas com faultstring de erro.
                if "faultstring" not in resp_txt:
                    log.info(f"[{sku}] Estoque atualizado com sucesso! id_prod={codigo_produto}, quantidade={quan}")
                    return True

            texto = response.text

            # Erro de DADOS (ex: data invalida): repetir nao resolve. Para na hora.
            if "Data do Movimento" in texto or "Client-101" in texto:
                log.error(f"[{sku}] Erro de dados (nao adianta repetir): {texto}")
                return False

            # API bloqueada / consumo redundante: respeita o tempo pedido pelo Omie.
            if "REDUNDANT" in texto or "MISUSE_API" in texto or response.status_code in (425, 429):
                espera = 60
                log.warning(f"[{sku}] API limitada/bloqueada. Tentativa {tentativa}. Esperando {espera}s...")
                time.sleep(espera)
                tentativa += 1
                continue

            log.warning(f"[{sku}] Erro {response.status_code}: {texto}")
            time.sleep(retry_delay)
            tentativa += 1
            continue

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
    hoje = data_hoje_sp()

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