from constantes import DIR_UTILIZACOES_OUTRAS_PDF
from transformar_xls_em_pdf import transformar_xls_em_pdf
import pandas as pd
from pathlib import Path

path = Path(r"C:\Users\m755247\Desktop\MANTIS_8769_2225612_2225613_21_09_2026___3_.xlsx")

df = pd.read_excel(path)

transformar_xls_em_pdf(
    tit_matricula='1368154-1',
    tit_nome='Geny Pereira Rodrigues'.upper(),
    tipo='Dependente(s)',
    df=df,
    path_destino=DIR_UTILIZACOES_OUTRAS_PDF
)