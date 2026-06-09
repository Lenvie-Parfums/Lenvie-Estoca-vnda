"""
TESTE DE GRAVACAO CONTROLADO — grava no Omie, mas SO para uma amostra pequena de PA.

Roda o fluxo completo (le Estoca + grava no Omie) apenas para os SKUs em
SKUS_TESTE_PA. Serve para validar a gravacao real antes de liberar a lista
inteira. Kits sao ignorados (Fase 1).

Apos rodar, confira no painel do Omie se o saldo desses 4 SKUs bate com o
'available' que aparece no log.
"""
import logging
from utils.ConsultaEstoca import rodarAPIEstoca
from utils.AtualizaOmie import (
    consultar_produto_omie,
    atualizar_estoque_omie,
    SKUS_KITS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# Amostra de PA para o teste de gravacao (4 itens).
SKUS_TESTE_PA = ["102062150", "102040445", "102079380", "10704027"]


def testar_gravacao():
    log.info("*" * 60)
    log.info("TESTE DE GRAVACAO CONTROLADO - grava no Omie SO estes SKUs:")
    log.info(f"  {SKUS_TESTE_PA}")
    log.info("*" * 60)

    # Le tudo da Estoca, mas processa apenas os SKUs de teste.
    todos = rodarAPIEstoca()
    por_sku = {p["sku"]: p["available"] for p in todos}

    ok = falhas = nao_encontrados = 0

    for sku in SKUS_TESTE_PA:
        if sku in SKUS_KITS:
            log.info(f"[KIT] {sku} -> ignorado (nao deveria estar no teste de PA)")
            continue

        if sku not in por_sku:
            log.warning(f"SKU {sku} nao voltou da Estoca. Pulando...")
            continue

        available = por_sku[sku]

        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        log.info(f"[PA] {sku} -> gravando saldo {available} no Omie")
        sucesso = atualizar_estoque_omie(codigo_produto, available, sku)
        if sucesso:
            ok += 1
        else:
            falhas += 1

    log.info("=" * 60)
    log.info(f"TESTE CONCLUIDO | gravados: {ok} | falhas: {falhas} | nao encontrados: {nao_encontrados}")
    log.info("Confira no Omie se o saldo desses SKUs bate com o 'available' acima.")
    log.info("=" * 60)


if __name__ == "__main__":
    testar_gravacao()