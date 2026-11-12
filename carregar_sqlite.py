#!/usr/bin/env python3
"""
Carrega o CSV reduzido de itens do PNCP em um banco SQLite e executa os
arquivos SQL de limpeza e de analise (pasta sql/).

Usa apenas a biblioteca padrao do Python.

Uso:
  python carregar_sqlite.py --entrada itens_2025-03_reduzido.csv --banco compras.db

O que este script faz (e por que nao esta em SQL):
  1. Carrega tudo como TEXTO na tabela itens_bruto. Os ids tem 22 digitos e
     nao podem virar numero.
  2. Cria a coluna unidade_norm (maiusculas, sem espacos repetidos). O UPPER
     do SQLite nao trata acentos, entao isso e feito aqui.
  3. Anonimiza fornecedores: troca CNPJ e nome por um codigo sequencial
     (F000001...). Nome e CNPJ de fornecedor NAO entram no banco.
Depois executa sql/01_limpeza.sql e sql/02_analises.sql, se existirem.
"""
import argparse, csv, os, re, sqlite3, sys

def principal():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--banco", required=True)
    ap.add_argument("--pasta-sql", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql"))
    args = ap.parse_args()

    csv.field_size_limit(10_000_000)
    con = sqlite3.connect(args.banco)
    fornecedores = {}
    with open(args.entrada, newline="", encoding="utf-8-sig") as f:
        leitor = csv.DictReader(f)
        colunas = [c for c in leitor.fieldnames if c not in ("codFornecedor", "nomeFornecedor")]
        colunas_banco = colunas + ["unidade_norm", "fornecedor_id"]
        con.execute("DROP TABLE IF EXISTS itens_bruto")
        con.execute("CREATE TABLE itens_bruto (" + ", ".join(f'"{c}" TEXT' for c in colunas_banco) + ")")
        sql = "INSERT INTO itens_bruto VALUES (" + ",".join("?" * len(colunas_banco)) + ")"
        lote, total = [], 0
        for linha in leitor:
            valores = [(linha[c] if linha[c] != "" else None) for c in colunas]
            un = linha.get("unidadeMedida") or ""
            un = re.sub(r"\s+", " ", un).strip().upper() or None
            cod = linha.get("codFornecedor") or ""
            if cod:
                fid = fornecedores.setdefault(cod, f"F{len(fornecedores) + 1:06d}")
            else:
                fid = None
            lote.append(valores + [un, fid])
            if len(lote) >= 20000:
                con.executemany(sql, lote); total += len(lote); lote = []
        if lote:
            con.executemany(sql, lote); total += len(lote)
    con.commit()
    print(f"itens_bruto: {total} linhas carregadas, {len(fornecedores)} fornecedores anonimizados")

    for nome in ("01_limpeza.sql", "02_analises.sql"):
        caminho = os.path.join(args.pasta_sql, nome)
        if not os.path.exists(caminho):  # aceita tambem os .sql na mesma pasta do script
            caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), nome)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                con.executescript(f.read())
            print(f"executado: {nome}")
        else:
            print(f"aviso: {caminho} nao encontrado, pulei")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='itens'").fetchone()[0]
    if n:
        print("itens (tabela limpa):", con.execute("SELECT COUNT(*) FROM itens").fetchone()[0], "linhas")
    con.close()
    print(f"Banco pronto: {args.banco}")

if __name__ == "__main__":
    principal()
