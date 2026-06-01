import logging
from utils.ConsultaEstoca import rodarAPIEstoca
from utils.AtualizaOmie import (
    consultar_produto_omie,
    atualizar_estoque_omie,
    atualizar_estoque_kit,
    SKUS_KITS,
)

# Logging aparece no terminal local e nos logs do GitHub Actions.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)


def atualizar_todos_estoques():
    # 1. Le o estoque disponivel na Estoca (fonte real do armazem).
    skus_disponiveis = rodarAPIEstoca()
    total = len(skus_disponiveis)
    log.info(f"Total de produtos recebidos da Estoca: {total}")

    ok = falhas = nao_encontrados = 0

    for produto in skus_disponiveis:
        sku = produto["sku"]
        available = produto["available"]

        # 2. Busca o id interno do produto no Omie (Filial 002).
        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        # 3. Ajusta o estoque no Omie, separando KIT de Produto Acabado (PA).
        if sku in SKUS_KITS:
            log.info(f"SKU {sku} e KIT -> ajuste de kit")
            sucesso = atualizar_estoque_kit(codigo_produto, available, sku)
        else:
            log.info(f"SKU {sku} e PA -> ajuste de saldo")
            sucesso = atualizar_estoque_omie(codigo_produto, available, sku)

        if sucesso:
            ok += 1
        else:
            falhas += 1

    # 4. Resumo final da execucao.
    log.info("=" * 55)
    log.info(
        f"RESUMO | recebidos: {total} | atualizados: {ok} | "
        f"falhas: {falhas} | nao encontrados no Omie: {nao_encontrados}"
    )
    log.info("=" * 55)

    return {
        "total": total,
        "ok": ok,
        "falhas": falhas,
        "nao_encontrados": nao_encontrados,
    }


if __name__ == "__main__":
    atualizar_todos_estoques()
