"""Fluxo PDF (task run_pdf): insere nos processos o PDF das planilhas colocadas
em dados/fluxo_pdf/planilhas. É o ALT 1 sem o download. Ver
planilhas_fluxo_pdf.py."""

from datetime import datetime

from constantes import DIR_FLUXO_PDF_PDF, DIR_FLUXO_PDF_PLANILHAS, DIR_LOG
from main_alt_1 import executar
from planilhas_fluxo_pdf import inserir_pdfs_da_pasta

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'fluxo_pdf'
FLUXO = 'FLUXO PDF - PLANILHAS DA PASTA'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_fluxo_pdf.log'


def main():
    executar(SCRIPT, FLUXO, AGORA, ARQ_LOG, [DIR_FLUXO_PDF_PLANILHAS, DIR_FLUXO_PDF_PDF], inserir_pdfs_da_pasta)


if __name__ == '__main__':
    main()
