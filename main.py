import logging
import time
from utilitários.ConsultaEstoca import rodarAPIEstoca
from utilitários.AtualizaOmie import (
    consultar_produto_omie,
    atualizar_estoque_omie,
    atualizar_estoque_kit,
    SKUS_KITS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)


def atualizar_todos_estoques():
    skus_disponiveis = rodarAPIEstoca()
    total = len(skus_disponiveis)
    log.info(f"Total de produtos recebidos da Estoca: {total}")

    ok = falhas = nao_encontrados = 0

    for produto in skus_disponiveis:
        sku = produto["sku"]
        available = produto["available"]

        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        # Kit: usa ENT/SAI com consulta previa do saldo atual
        # PA:  usa SLD (saldo direto)
        if sku in SKUS_KITS:
            log.info(f"[KIT] {sku} -> ajustando saldo para {available}")
            sucesso = atualizar_estoque_kit(codigo_produto, available, sku)
        else:
            log.info(f"{sku} -> gravando saldo {available} no Omie")
            sucesso = atualizar_estoque_omie(codigo_produto, available, sku)

        if sucesso:
            ok += 1
        else:
            falhas += 1

        time.sleep(1)

    log.info("=" * 60)
    log.info("RESUMO DA EXECUCAO")
    log.info(f"  Recebidos da Estoca:     {total}")
    log.info(f"  Atualizados no Omie:     {ok}")
    log.info(f"  Falhas:                  {falhas}")
    log.info(f"  Nao encontrados no Omie: {nao_encontrados}")
    log.info("=" * 60)

    return {"total": total, "ok": ok, "falhas": falhas, "nao_encontrados": nao_encontrados}


if __name__ == "__main__":
    atualizar_todos_estoques()
