import logging
import time
from utils.ConsultaEstoca import rodarAPIEstoca
from utils.AtualizaOmie import (
    consultar_produto_omie,
    atualizar_estoque_omie,
    SKUS_KITS,
)

# Logging aparece no terminal local e nos logs do GitHub Actions.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# ==========================================================
# FASE 1: sincroniza apenas Produtos Acabados (PA).
# Kits NAO sao gravados no Omie por enquanto — apenas listados
# no log para acompanhamento. A regra de estoque dos kits (que
# usam 2 ou 3 unidades de itens PA) sera tratada na Fase 2.
# ==========================================================


def atualizar_todos_estoques():
    # 1. Le o estoque disponivel na Estoca (fonte real do armazem).
    skus_disponiveis = rodarAPIEstoca()
    total = len(skus_disponiveis)
    log.info(f"Total de produtos recebidos da Estoca: {total}")

    ok = falhas = nao_encontrados = 0
    kits_pulados = []  # guarda (sku, available) dos kits ignorados nesta fase

    for produto in skus_disponiveis:
        sku = produto["sku"]
        available = produto["available"]

        # --- KIT: nao grava nesta fase, apenas registra ---
        if sku in SKUS_KITS:
            log.info(f"[KIT] {sku} -> available {available} | NAO gravado (Fase 1)")
            kits_pulados.append((sku, available))
            continue

        # --- PA: fluxo normal de sincronizacao ---
        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        log.info(f"[PA] {sku} -> available {available} | gravando saldo no Omie")
        sucesso = atualizar_estoque_omie(codigo_produto, available, sku)
        if sucesso:
            ok += 1
        else:
            falhas += 1

        # Respiro entre gravacoes para nao acionar a protecao anti-spam do Omie.
        time.sleep(2)

    # 2. Resumo final da execucao.
    log.info("=" * 60)
    log.info("RESUMO DA EXECUCAO (Fase 1 - apenas PA)")
    log.info(f"  Recebidos da Estoca:        {total}")
    log.info(f"  PA atualizados no Omie:     {ok}")
    log.info(f"  PA com falha:               {falhas}")
    log.info(f"  PA nao encontrados no Omie: {nao_encontrados}")
    log.info(f"  Kits ignorados (Fase 1):    {len(kits_pulados)}")
    log.info("=" * 60)

    if kits_pulados:
        log.info("Kits NAO gravados nesta fase (sku -> available):")
        for sku, avail in kits_pulados:
            log.info(f"    {sku} -> {avail}")
        log.info("=" * 60)

    return {
        "total": total,
        "ok": ok,
        "falhas": falhas,
        "nao_encontrados": nao_encontrados,
        "kits_pulados": kits_pulados,
    }


if __name__ == "__main__":
    atualizar_todos_estoques()