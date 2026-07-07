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
OMIE_LOCAL_URL   = "https://app.omie.com.br/api/v1/estoque/local/"
OMIE_POSICAO_URL = "https://app.omie.com.br/api/v1/estoque/consulta/"
APP_KEY    = os.getenv("APP_KEY_OMIE")
APP_SECRET = os.getenv("APP_SECRET")

TZ_SP = ZoneInfo("America/Sao_Paulo")

def data_hoje_sp():
    return datetime.now(TZ_SP).strftime("%d/%m/%Y")

# Cache dos codigos de locais — carregado uma vez no inicio
_cache_locais = {}

def carregar_locais_estoque():
    """
    Carrega os locais de estoque do Omie e armazena em cache.
    Retorna dict: {codigo_local: nome_local}
    """
    global _cache_locais
    if _cache_locais:
        return _cache_locais

    payload = {
        "call": "ListarLocaisEstoque",
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": [{"nPagina": 1, "nRegPorPagina": 50}]
    }
    try:
        response = requests.post(
            OMIE_LOCAL_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            locais = data.get("locaisEstoque", [])
            for local in locais:
                cod = local.get("nCodLocalEstoque")
                nome = local.get("cCodigo", "")
                desc = local.get("cDescricao", "")
                _cache_locais[cod] = nome
                log.info(f"Local carregado: {cod} = {nome} ({desc})")
        else:
            log.warning(f"Erro ao listar locais: {response.text[:200]}")
    except Exception as e:
        log.warning(f"Falha ao carregar locais de estoque: {e}")

    return _cache_locais

def obter_codigo_local(nome_local):
    """
    Retorna o codigo numerico do local pelo nome (ex: 'PADRAO', 'QUARENTENA').
    """
    locais = carregar_locais_estoque()
    for cod, nome in locais.items():
        if nome.upper() == nome_local.upper():
            return cod
    return None

SKUS_KITS = {
    "101002022","101002021","102022380","102022150","90100001","14093020",
    "14099020","10131874","14093320","14090220","14090020","14097920",
    "14098020","14012020","10408470","10137474","10139274","10134074",
    "102026380","102059380",
    "KIT44","KIT45","KIT46","KIT47","KIT48","KIT49","KIT50",
    "KIT51","KIT52","KIT53","KIT54","KIT55","KIT56","KIT57",
    "KIT58","KIT59","KIT60","KIT61","KIT63","KIT64","KIT65",
    "KIT66","KIT67","KIT68","KIT69","KIT70","KIT05","11800001",
}


def _post_omie(url, payload, sku, max_retries=3, retry_delay=10):
    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                url, headers={"Content-Type": "application/json"},
                data=json.dumps(payload), timeout=60
            )
            texto = response.text
            if response.status_code == 200 and "faultstring" not in texto:
                return response
            if "Data do Movimento" in texto or "Client-101" in texto:
                return response
            if "REDUNDANT" in texto or "MISUSE_API" in texto or response.status_code in (425, 429):
                log.warning(f"[{sku}] API limitada. Esperando 60s...")
                time.sleep(60)
                tentativa += 1
                continue
            log.warning(f"[{sku}] Erro {response.status_code}: {texto[:200]}")
            time.sleep(retry_delay)
            tentativa += 1
        except requests.exceptions.RequestException as e:
            log.warning(f"[{sku}] Falha: {e}. Tentativa {tentativa}.")
            time.sleep(retry_delay)
            tentativa += 1
    return None


def consultar_produto_omie(codigo, max_retries=3, retry_delay=10, request_delay=1):
    """Retorna codigo_produto ou None."""
    payload = {
        "call": "ConsultarProduto",
        "app_key": APP_KEY, "app_secret": APP_SECRET,
        "param": [{"codigo": codigo}]
    }
    tentativa = 1
    while tentativa <= max_retries:
        try:
            response = requests.post(
                OMIE_PRODUTO_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload), timeout=60
            )
            if response.status_code == 429 or "REDUNDANT" in response.text or "MISUSE_API" in response.text:
                log.warning(f"[{codigo}] Rate limit. Aguardando 60s...")
                time.sleep(60); tentativa += 1; continue
            if response.status_code != 200:
                log.warning(f"[{codigo}] Erro {response.status_code}")
                time.sleep(retry_delay); tentativa += 1; continue
            data = response.json()
            codigo_produto = data.get("codigo_produto")
            if not codigo_produto:
                log.warning(f"[{codigo}] Nao encontrado no Omie.")
                return None
            time.sleep(request_delay)
            return codigo_produto
        except requests.exceptions.RequestException as e:
            log.warning(f"[{codigo}] Falha: {e}.")
            time.sleep(retry_delay); tentativa += 1
    log.error(f"[{codigo}] Falha definitiva na consulta.")
    return None


def consultar_saldo_por_local(codigo_produto, sku):
    """
    Consulta saldo de estoque por local via ListarPosEstoque.
    Retorna dict: {codigo_local: quantidade}
    """
    payload = {
        "call": "ListarPosEstoque",
        "app_key": APP_KEY, "app_secret": APP_SECRET,
        "param": [{"nCodProd": codigo_produto, "pagina": 1, "registros_por_pagina": 50}]
    }
    resultado = {}
    try:
        response = requests.post(
            OMIE_POSICAO_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload), timeout=60
        )
        if response.status_code == 200 and "faultstring" not in response.text:
            data = response.json()
            posicoes = data.get("posicaoEstoque", [])
            for p in posicoes:
                cod_local = p.get("nCodLocalEstoque")
                qtde = float(p.get("nQtde", 0))
                resultado[cod_local] = qtde
                log.info(f"[{sku}] Local {cod_local}: {qtde} un")
        else:
            log.warning(f"[{sku}] ListarPosEstoque falhou: {response.text[:150]}")
    except Exception as e:
        log.warning(f"[{sku}] Erro ao consultar saldo: {e}")
    return resultado


def _ajustar_local(codigo_produto, sku, quan_alvo, codigo_local, nome_local,
                   saldo_atual, tipo_ajuste_kit=None, max_retries=3, retry_delay=10):
    """
    Ajusta o estoque de um produto num local específico.
    - PA: usa SLD (saldo direto) — sem codigo_local_estoque (vai pro local padrão)
    - Kit no local QUARENTENA: usa ENT/SAI calculando diferença
    - Kit no local PADRAO: usa ENT/SAI calculando diferença
    """
    diferenca = float(quan_alvo) - float(saldo_atual)

    if diferenca == 0:
        log.info(f"[{sku}] {nome_local} ja correto ({saldo_atual}). Nada a fazer.")
        return True

    # PA: SLD no local PADRAO (sem especificar local = usa o padrão)
    if tipo_ajuste_kit is None:
        tipo = "SLD"
        ajuste = quan_alvo
        valor = 0
    else:
        # Kit: ENT ou SAI com diferença
        tipo = "ENT" if diferenca > 0 else "SAI"
        ajuste = abs(diferenca)
        valor = 0.01

    log.info(f"[{sku}] {nome_local}: saldo={saldo_atual} | alvo={quan_alvo} | "
             f"tipo={tipo} | ajuste={ajuste:.0f}")

    param = {
        "id_prod": codigo_produto,
        "data": data_hoje_sp(),
        "quan": str(int(ajuste)) if tipo_ajuste_kit else str(quan_alvo),
        "obs": "Ajuste automatico por API",
        "origem": "AJU",
        "tipo": tipo,
        "motivo": "INV",
        "valor": valor
    }
    # Especifica o local de estoque (QUARENTENA)
    if codigo_local is not None:
        param["codigo_local_estoque"] = codigo_local

    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY, "app_secret": APP_SECRET,
        "param": [param]
    }
    response = _post_omie(OMIE_ESTOQUE_URL, payload, sku, max_retries, retry_delay)
    if response is None:
        log.error(f"[{sku}] Falha definitiva ao ajustar {nome_local}.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] {nome_local} atualizado! alvo={quan_alvo}")
        return True
    log.error(f"[{sku}] Falha {nome_local}: {response.text[:200]}")
    return False


def atualizar_estoque_omie(codigo_produto, quan_disponivel, sku, max_retries=3, retry_delay=10):
    """
    Atualiza PA:
    - Disponível Estoca → local PADRAO via SLD
    - Bloqueado Estoca  → local QUARENTENA via ENT/SAI
    """
    # SLD no local padrão (não precisa especificar o local)
    return _ajustar_local(
        codigo_produto, sku, quan_disponivel,
        codigo_local=None, nome_local="PADRAO",
        saldo_atual=0,  # SLD substitui, nao precisa calcular diferença
        tipo_ajuste_kit=None,
        max_retries=max_retries, retry_delay=retry_delay
    )


def atualizar_estoque_omie_com_bloqueado(codigo_produto, quan_disponivel,
                                          quan_bloqueado, sku,
                                          max_retries=3, retry_delay=10):
    """
    Atualiza PA com dois locais:
    - Disponível → PADRAO (SLD)
    - Bloqueado  → QUARENTENA (ENT/SAI)
    """
    # 1. Atualiza PADRAO via SLD
    ok_padrao = _ajustar_local(
        codigo_produto, sku, quan_disponivel,
        codigo_local=None, nome_local="PADRAO",
        saldo_atual=0, tipo_ajuste_kit=None,
        max_retries=max_retries, retry_delay=retry_delay
    )

    # 2. Atualiza QUARENTENA via ENT/SAI se tiver bloqueado
    ok_quar = True
    if quan_bloqueado > 0 or True:  # sempre verifica pra poder zerar também
        cod_quar = obter_codigo_local("QUARENTENA")
        if cod_quar:
            saldos = consultar_saldo_por_local(codigo_produto, sku)
            saldo_quar = saldos.get(cod_quar, 0)
            ok_quar = _ajustar_local(
                codigo_produto, sku, quan_bloqueado,
                codigo_local=cod_quar, nome_local="QUARENTENA",
                saldo_atual=saldo_quar, tipo_ajuste_kit="PA",
                max_retries=max_retries, retry_delay=retry_delay
            )
        else:
            log.warning(f"[{sku}] Codigo do local QUARENTENA nao encontrado.")

    return ok_padrao and ok_quar


def atualizar_estoque_kit(codigo_produto, quan_estoca, sku,
                           max_retries=3, retry_delay=10):
    """
    Atualiza Kit com ENT/SAI usando saldo real por local via ListarPosEstoque.
    Ajusta tanto PADRAO quanto QUARENTENA.
    """
    cod_padrao = obter_codigo_local("PADRAO")
    cod_quar   = obter_codigo_local("QUARENTENA")

    saldos = consultar_saldo_por_local(codigo_produto, sku)
    saldo_padrao = saldos.get(cod_padrao, 0) if cod_padrao else 0
    saldo_quar   = saldos.get(cod_quar, 0)   if cod_quar   else 0
    saldo_total  = saldo_padrao + saldo_quar

    diferenca = float(quan_estoca) - saldo_total

    if diferenca == 0:
        log.info(f"[{sku}] Kit ja correto (total={saldo_total}). Nada a fazer.")
        return True

    tipo   = "ENT" if diferenca > 0 else "SAI"
    ajuste = abs(diferenca)

    log.info(f"[{sku}] Kit: padrao={saldo_padrao} + quar={saldo_quar} = {saldo_total} | "
             f"estoca={quan_estoca} | dif={diferenca:+.0f} | tipo={tipo} | ajuste={ajuste:.0f}")

    # Ajuste no local PADRAO do kit
    param = {
        "id_prod": codigo_produto,
        "data": data_hoje_sp(),
        "quan": str(int(ajuste)),
        "obs": "Ajuste automatico por API",
        "origem": "AJU",
        "tipo": tipo,
        "motivo": "INV",
        "valor": 0.01
    }
    if cod_padrao:
        param["codigo_local_estoque"] = cod_padrao

    payload = {
        "call": "IncluirAjusteEstoque",
        "app_key": APP_KEY, "app_secret": APP_SECRET,
        "param": [param]
    }
    response = _post_omie(OMIE_ESTOQUE_URL, payload, sku, max_retries, retry_delay)
    if response is None:
        log.error(f"[{sku}] Falha definitiva ao ajustar kit.")
        return False
    if response.status_code == 200 and "faultstring" not in response.text:
        log.info(f"[{sku}] Kit atualizado! saldo_final={quan_estoca}, tipo={tipo}")
        return True
    log.error(f"[{sku}] Falha kit: {response.text[:200]}")
    return False
