"""Fluxo ADC PDF ANT MAN (task run_geacs_adc_pdf_ant_man): insere nos processos o PDF das planilhas colocadas
em dados/geacs_adc_pdf_ant_man/planilhas. É o ADC PDF ANT AUT sem o download. Ver
planilhas_adc_pdf_ant_man.py."""

from datetime import datetime

from constantes import DIR_ADC_PDF_ANT_MAN_PDF, DIR_ADC_PDF_ANT_MAN_PLANILHAS, DIR_LOG
from main_geacs_adc_pdf_ant_aut import executar
from planilhas_adc_pdf_ant_man import inserir_pdfs_da_pasta

AGORA = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
SCRIPT = 'geacs_adc_pdf_ant_man'
FLUXO = 'ADC PDF ANT MAN - PLANILHAS DA PASTA'

ARQ_LOG = DIR_LOG / f'{AGORA}_execucao_geacs_adc_pdf_ant_man.log'


def main():
    executar(SCRIPT, FLUXO, AGORA, ARQ_LOG, [DIR_ADC_PDF_ANT_MAN_PLANILHAS, DIR_ADC_PDF_ANT_MAN_PDF], inserir_pdfs_da_pasta)


if __name__ == '__main__':
    main()
