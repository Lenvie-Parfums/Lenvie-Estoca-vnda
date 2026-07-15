import logging
import time
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

log.info("Iniciando script...")

try:
    from utils.ConsultaEstoca import rodarAPIEstoca
    log.info("ConsultaEstoca importado OK")
except Exception as e:
    log.error(f"Falha ao importar ConsultaEstoca: {e}")
    sys.exit(1)

try:
    from utils.AtualizaOmie import (
        consultar_produto_omie,
        atualizar_estoque_omie_com_bloqueado,
        atualizar_estoque_kit,
        carregar_locais_estoque,
        SKUS_KITS,
    )
    log.info("AtualizaOmie importado OK")
except ImportError as e:
    log.error(f"Falha ao importar AtualizaOmie: {e}")
    log.error("Verifique se o AtualizaOmie.py tem as funcoes: atualizar_estoque_omie_com_bloqueado, carregar_locais_estoque")
    sys.exit(1)


def atualizar_todos_estoques():
    log.info("Carregando locais de estoque do Omie...")
    locais = carregar_locais_estoque()
    log.info(f"Locais carregados: {locais}")

    skus_disponiveis = rodarAPIEstoca()
    total = len(skus_disponiveis)
    log.info(f"Total de produtos recebidos da Estoca: {total}")

    ok = falhas = nao_encontrados = 0

    for produto in skus_disponiveis:
        sku       = produto["sku"]
        available = produto["available"]
        bloqueado = produto.get("blocked", 0)

        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        if sku in SKUS_KITS:
            log.info(f"[KIT] {sku} -> ajustando para {available}")
            sucesso = atualizar_estoque_kit(codigo_produto, available, sku)
        else:
            log.info(f"{sku} -> PADRAO={available} | AVARIAS={bloqueado}")
            sucesso = atualizar_estoque_omie_com_bloqueado(
                codigo_produto, available, bloqueado, sku
            )

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


if __name__ == "__main__":
    atualizar_todos_estoques()
