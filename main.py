import logging
import time
from utils.ConsultaEstoca import rodarAPIEstoca
from utils.AtualizaOmie import consultar_produto_omie, atualizar_estoque_omie

# Logging aparece no terminal local e nos logs do GitHub Actions.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
log = logging.getLogger(__name__)

# ==========================================================
# Repassa o estoque da Estoca para o Omie, sem distincao.
# A Estoca e a fonte da verdade: o valor 'available' de cada
# SKU e gravado como SALDO (SLD) no Omie, exatamente como vem.
# O Omie entao propaga para o site (Vnda).
# ==========================================================


def atualizar_todos_estoques():
    # 1. Le o estoque disponivel na Estoca.
    skus_disponiveis = rodarAPIEstoca()
    total = len(skus_disponiveis)
    log.info(f"Total de produtos recebidos da Estoca: {total}")

    ok = falhas = nao_encontrados = 0

    for produto in skus_disponiveis:
        sku = produto["sku"]
        available = produto["available"]

        # 2. Busca o id interno do produto no Omie.
        codigo_produto = consultar_produto_omie(sku)
        if not codigo_produto:
            log.warning(f"SKU {sku} nao encontrado no Omie. Pulando...")
            nao_encontrados += 1
            continue

        # 3. Grava o saldo no Omie, repassando o available cru da Estoca.
        log.info(f"{sku} -> gravando saldo {available} no Omie")
        sucesso = atualizar_estoque_omie(codigo_produto, available, sku)
        if sucesso:
            ok += 1
        else:
            falhas += 1

        # Respiro entre gravacoes para nao acionar a protecao anti-spam do Omie.
        time.sleep(2)

    # 4. Resumo final.
    log.info("=" * 60)
    log.info("RESUMO DA EXECUCAO")
    log.info(f"  Recebidos da Estoca:     {total}")
    log.info(f"  Atualizados no Omie:     {ok}")
    log.info(f"  Falhas:                  {falhas}")
    log.info(f"  Nao encontrados no Omie: {nao_encontrados}")
    log.info("=" * 60)

    return {
        "total": total,
        "ok": ok,
        "falhas": falhas,
        "nao_encontrados": nao_encontrados,
    }


if __name__ == "__main__":
    atualizar_todos_estoques()