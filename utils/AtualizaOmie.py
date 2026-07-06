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

OMIE_PRODUTO_URL = os.getenv("OMIE_PRODUTO_URL")
OMIE_ESTOQUE_URL = os.getenv("OMIE_ESTOQUE_URL")
OMIE_CONSULTA_ESTOQUE_URL = "https://app.omie.com.br/api/v1/estoque/resumo/"
APP_KEY = os.getenv("APP_KEY_OMIE")
APP_SECRET = os.getenv("APP_SECRET")

TZ_SP = ZoneInfo("America/Sao_Paulo")

def data_hoje_sp():
    return datetime.now(TZ_SP).strftime("%d/%m/%Y")

SKUS_KITS = {
    "101002022", "101002021",
    "102022380", "102022150",
    "90100001",  "14093020",
    "14099020",  "10131874",
    "14093320",  "14090220",
    "14090020",  "14097920",
    "14098020",  "14012020",
    "10408470",  "10137474",
    "10139274",  "10134074",
    "102026380", "102059380",
    "KIT44", "KIT45", "KIT46", "KIT47", "KIT48", "KIT49", "KIT50",
    "KIT51", "KIT52", "KIT53", "KIT54", "KIT55", "KIT56", "KIT57",
    "KIT58", "KIT59", "KIT60", "KIT61", "KIT63", "KIT64", "KIT65",
    "KIT66", "KIT67", "KIT68", "KIT69", "KIT70", "KIT05",
    "11800001",
}

def _post_omie(url, payload, sku, max_retries=3, retry_delay=10):
    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=60
            )
            texto = response.text

            if response.status_code == 200 and "faultstring" not in texto:
                return response

            if "Data do Movimento" in texto or "Client-101" in texto:
                return response

            if "REDUNDANT" in texto or "MISUSE_API" in texto or response.status_code in (425, 429):
                log.warning(f"[{sku}] API limitada. Tentativa {tentativa}. Esperando 60s...")
                time.sleep(60)
                tentativa += 1
                continue

            log.warning(f"[{sku}] Erro {response.status_code}: {texto[:200]}")
            time.sleep(retry_delay)
            tentativa += 1

        except requests.exceptions.RequestException as e:
            log.warning(f"[{sku}] Falha de conexao: {e}. Tentativa {tentativa}.")
            time.sleep(retry_delay)
            tentativa += 1

    return None

def consultar_posicao_estoque(codigo_produto, sku, max_retries=3, retry_delay=10):
    payload = {
        "call": "ListarPosEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{
            "id_prod": codigo_produto,
            "data_posicao": data_hoje_sp()
        }]
    }
    
    response = _post_omie(OMIE_CONSULTA_ESTOQUE_URL, payload, sku, max_retries, retry_delay)
    
    if response and response.status_code == 200:
        data = response.json()
        produtos = data.get("produtos", [])
        saldo_total = 0.0
        for prod in produtos:
            saldo = prod.get("saldo_fisico", 0)
            saldo_total += float(saldo)
        return saldo_total
        
    log.warning(f"[{sku}] Nao foi possivel obter a posicao real de estoque. Assumindo 0.")
    return 0.0

def consultar_produto_omie(codigo, max_retries=3, retry_delay=10, request_delay=1):
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
                log.warning(f"[{codigo}] Rate limit. Aguardando {retry_delay}s...")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            if "REDUNDANT" in response.text or "MISUSE_API" in response.text:
                log.warning(f"[{codigo}] API bloqueada. Aguardando 60s...")
                time.sleep(60)
                tentativa += 1
                continue

            if response.status_code != 200:
                log.warning(f"[{codigo}] Erro {response.status_code}: {response.text[:100]}")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            data = response.json()
            codigo_produto = data.get("codigo_produto")
            if not codigo_produto:
                log.warning(f"[{codigo}] Produto nao encontrado no Omie.")
                return None, 0

            estoque_atual = consultar_posicao_estoque(codigo_produto, codigo, max_retries, retry_delay)

            time.sleep(request_delay)
            return codigo_produto, estoque_atual

        except requests.exceptions.RequestException as e:
            log.warning(f"[{codigo}] Falha de conexao: {e}. Tentativa {tentativa}.")
            time.sleep(retry_delay)
            tentativa += 1

    log.error(f"[{codigo}] Falha definitiva na consulta apos {max_retries} tentativas.")
    return None, 0

def atualizar_estoque_omie(codigo_produto, quan, sku,
                            obs="Ajuste automatico por API",
                            max_retries=3, retry_delay=10):
    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{
            "id_prod": codigo_produto,
            "data": data_hoje_sp(),
            "quan": str(quan),
            "obs": obs,
            "origem": "AJU",
            "tipo": "SLD",
            "motivo": "INV",
            "valor": 0
        }]
    }
    response = _post_omie(OMIE_ESTOQUE_URL, payload, sku, max_retries, retry_delay)
    if response is None:
        log.error(f"[{sku}] Falha definitiva ao atualizar estoque.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] Estoque atualizado! id_prod={codigo_produto}, quantidade={quan}")
        return True
    if "Data do Movimento" in response.text or "Client-101" in response.text:
        log.error(f"[{sku}] Erro de dados: {response.text[:200]}")
        return False
    log.error(f"[{sku}] Falha: {response.text[:200]}")
    return False

def atualizar_estoque_kit(codigo_produto, quan_estoca, sku, estoque_omie_atual=0,
                           obs="Ajuste automatico por API",
                           max_retries=3, retry_delay=10):
    saldo_atual = float(estoque_omie_atual)
    diferenca = float(quan_estoca) - saldo_atual

    if diferenca == 0:
        log.info(f"[{sku}] Kit ja esta correto ({saldo_atual}). Nada a fazer.")
        return True

    tipo = "ENT" if diferenca > 0 else "SAI"
    quantidade_ajuste = abs(diferenca)

    log.info(f"[{sku}] Kit: saldo_omie={saldo_atual} | estoca={quan_estoca} | "
             f"diferenca={diferenca:+.0f} | tipo={tipo} | ajuste={quantidade_ajuste:.0f}")

    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{
            "id_prod": codigo_produto,
            "data": data_hoje_sp(),
            "quan": str(int(quantidade_ajuste)),
            "obs": obs,
            "origem": "AJU",
            "tipo": tipo,
            "motivo": "INV",
            "valor": 0.01
        }]
    }
    response = _post_omie(OMIE_ESTOQUE_URL, payload, sku, max_retries, retry_delay)
    if response is None:
        log.error(f"[{sku}] Falha definitiva ao ajustar kit.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] Kit atualizado! saldo_final={quan_estoca}, tipo={tipo}, ajuste={quantidade_ajuste:.0f}")
        return True
    log.error(f"[{sku}] Falha ao ajustar kit: {response.text[:200]}")
    return False
