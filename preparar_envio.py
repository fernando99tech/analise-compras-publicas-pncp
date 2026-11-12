#!/usr/bin/env python3
"""
Reduz o CSV bruto de itens do PNCP para enviar ao Claude e para uso no projeto.

O que faz:
  1. Mantem so as colunas necessarias para a analise.
  2. Mascara nomes de fornecedores que terminam com 11 digitos (padrao de CPF
     embutido no nome de MEI), trocando por "PESSOA FISICA MEI (mascarado)".
  3. Grava um CSV menor e tambem um .zip dele (CSV compacta muito bem).

Usa apenas a biblioteca padrao do Python.

Uso:
  python preparar_envio.py --entrada itens_2025-03.csv --saida itens_2025-03_reduzido.csv
"""

import argparse
import csv
import re
import sys
import zipfile

COLUNAS = [
    "idCompra", "idCompraItem", "idContratacaoPNCP",
    "unidadeOrgaoCodigoUnidade", "orgaoEntidadeCnpj", "numeroItemPncp",
    "descricaoResumida", "materialOuServico",
    "codigoClasse", "codigoGrupo", "codItemCatalogo", "codigoPdm", "nomePdm",
    "unidadeMedida", "orcamentoSigiloso", "itemCategoriaNome",
    "criterioJulgamentoNome", "situacaoCompraItemNome", "tipoBeneficioNome",
    "quantidade", "valorUnitarioEstimado", "valorTotal",
    "temResultado", "codFornecedor", "nomeFornecedor",
    "quantidadeResultado", "valorUnitarioResultado", "valorTotalResultado",
    "dataInclusaoPncp", "dataAtualizacaoPncp", "dataResultado",
]

PADRAO_CPF_NO_NOME = re.compile(r"\d{11}\s*$")
MASCARA = "PESSOA FISICA MEI (mascarado)"


def principal():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--saida", required=True)
    args = ap.parse_args()

    csv.field_size_limit(10_000_000)
    total = mascarados = 0
    with open(args.entrada, newline="", encoding="utf-8-sig") as fin, \
         open(args.saida, "w", newline="", encoding="utf-8-sig") as fout:
        leitor = csv.DictReader(fin)
        faltando = [c for c in COLUNAS if c not in (leitor.fieldnames or [])]
        if faltando:
            print("Aviso: colunas ausentes no arquivo de entrada:", ", ".join(faltando))
        colunas = [c for c in COLUNAS if c in (leitor.fieldnames or [])]
        escritor = csv.DictWriter(fout, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        for linha in leitor:
            nome = linha.get("nomeFornecedor") or ""
            if PADRAO_CPF_NO_NOME.search(nome):
                linha["nomeFornecedor"] = MASCARA
                mascarados += 1
            escritor.writerow(linha)
            total += 1

    zip_path = args.saida.rsplit(".", 1)[0] + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(args.saida)

    print(f"Linhas processadas: {total}")
    print(f"Nomes mascarados (terminavam com 11 digitos): {mascarados}")
    print(f"Gerados: {args.saida} e {zip_path}")
    if total == 0:
        sys.exit("Arquivo de entrada sem linhas de dados.")


if __name__ == "__main__":
    principal()
