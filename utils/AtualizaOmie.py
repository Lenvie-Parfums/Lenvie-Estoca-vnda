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
OMIE_POSICAO_URL = "https://app.omie.com.br/api/v1/estoque/consulta/"
APP_KEY = os.getenv("APP_KEY_OMIE")
APP_SECRET = os.getenv("APP_SECRET")

# Fuso de Sao Paulo. GitHub Actions roda em UTC.
TZ_SP = ZoneInfo("America/Sao_Paulo")

def data_hoje_sp():
    return datetime.now(TZ_SP).strftime("%d/%m/%Y")

# Lista de SKUs que sao Kits no Omie.
# Kits nao aceitam SLD (saldo) — apenas ENT (entrada) ou SAI (saida).
# A logica correta e: consultar saldo atual, calcular diferenca e ajustar.
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
    "102026380", "102059380",  # kits leve-2 identificados
    "KIT44", "KIT45", "KIT46", "KIT47", "KIT48", "KIT49", "KIT50",
    "KIT51", "KIT52", "KIT53", "KIT54", "KIT55", "KIT56", "KIT57",
    "KIT58", "KIT59", "KIT60", "KIT61", "KIT63", "KIT64", "KIT65",
    "KIT66", "KIT67", "KIT68", "KIT69", "KIT70", "KIT05",
    "11800001",
}


def _post_omie(url, payload, sku, max_retries=3, retry_delay=10):
    """Helper: faz POST no Omie com retry e tratamento de bloqueio."""
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

            # Erro de DADOS: nao adianta repetir
            if response.status_code == 200 and "faultstring" not in texto:
                return response  # sucesso

            if "Data do Movimento" in texto or "Client-101" in texto:
                # Pode ser erro de tipo de kit tambem — retorna pra caller decidir
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

    return None  # falha definitiva


def consultar_produto_omie(codigo, max_retries=3, retry_delay=10, request_delay=1):
    """Consulta o produto no Omie pelo SKU. Retorna codigo_produto ou None."""
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
                log.warning(f"[{codigo}] Rate limit. Tentativa {tentativa}. Aguardando {retry_delay}s...")
                time.sleep(retry_delay)
                tentativa += 1
                continue

            if "REDUNDANT" in response.text or "MISUSE_API" in response.text:
                log.warning(f"[{codigo}] API bloqueada. Tentativa {tentativa}. Aguardando 60s...")
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
                return None

            time.sleep(request_delay)
            return codigo_produto

        except requests.exceptions.RequestException as e:
            log.warning(f"[{codigo}] Falha de conexao: {e}. Tentativa {tentativa}.")
            time.sleep(retry_delay)
            tentativa += 1

    log.error(f"[{codigo}] Falha definitiva na consulta apos {max_retries} tentativas.")
    return None


def consultar_saldo_kit_omie(codigo_produto, sku):
    """
    Consulta o saldo atual de estoque de um kit no Omie.
    Retorna o saldo (float) ou 0 se nao encontrar.
    """
    payload = {
        "call": "ConsultarPosicaoEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{"codigo_produto": codigo_produto}]
    }
    try:
        response = requests.post(
            OMIE_POSICAO_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            saldo = data.get("saldo", 0)
            log.info(f"[{sku}] Saldo atual no Omie: {saldo}")
            return float(saldo)
    except Exception as e:
        log.warning(f"[{sku}] Falha ao consultar saldo: {e}")
    return 0.0


def atualizar_estoque_omie(codigo_produto, quan, sku,
                            obs="Ajuste automatico por API",
                            max_retries=3, retry_delay=10):
    """Atualiza estoque de Produto Acabado (PA) usando SLD (saldo direto)."""
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
        log.error(f"[{sku}] Falha definitiva ao atualizar estoque apos {max_retries} tentativas.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] Estoque atualizado! id_prod={codigo_produto}, quantidade={quan}")
        return True

    # Erro de dados
    if "Data do Movimento" in response.text or "Client-101" in response.text:
        log.error(f"[{sku}] Erro de dados (nao adianta repetir): {response.text[:200]}")
        return False

    log.error(f"[{sku}] Falha: {response.text[:200]}")
    return False


def atualizar_estoque_kit(codigo_produto, quan_estoca, sku,
                           obs="Ajuste automatico por API",
                           max_retries=3, retry_delay=10):
    """
    Atualiza estoque de Kit no Omie usando ENT ou SAI (kits nao aceitam SLD).

    Logica:
      1. Consulta o saldo atual do kit no Omie.
      2. Calcula diferenca = quan_estoca - saldo_atual.
      3. Se diferenca > 0 -> ENT (entrada) da diferenca.
      4. Se diferenca < 0 -> SAI (saida) do absoluto da diferenca.
      5. Se diferenca == 0 -> ja esta correto, nada a fazer.
    """
    saldo_atual = consultar_saldo_kit_omie(codigo_produto, sku)
    diferenca = float(quan_estoca) - saldo_atual

    if diferenca == 0:
        log.info(f"[{sku}] Kit ja esta com saldo correto ({saldo_atual}). Nada a fazer.")
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
        log.error(f"[{sku}] Falha definitiva ao ajustar kit apos {max_retries} tentativas.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] Kit atualizado! saldo_final={quan_estoca}, tipo={tipo}, ajuste={quantidade_ajuste:.0f}")
        return True

    log.error(f"[{sku}] Falha ao ajustar kit: {response.text[:200]}")
    return False
