#!/usr/bin/env python3
"""
Baixa todas as paginas de um endpoint da API de Dados Abertos do Compras.gov.br
(modulo de contratacoes, Lei 14.133) e grava um CSV.

Usa apenas a biblioteca padrao do Python, nao precisa instalar nada.

Como usar:
  1. No Swagger, clique em "Try it out", preencha as datas e execute.
  2. Copie o valor de "Request URL" (a linha que comeca com https://dadosabertos...).
  3. Rode:
       python baixar_pncp.py --url "COLE_A_URL_AQUI" --saida itens_2025-03.csv

Se o download for interrompido (timeout, queda de internet), rode o MESMO comando
acrescentando --retomar. O script conta as linhas ja gravadas e continua dali:
       python baixar_pncp.py --url "COLE_A_URL_AQUI" --saida itens_2025-03.csv --retomar

Se uma pagina falhar varias vezes, o script a busca em pedacos menores.
Por seguranca, ele nao sobrescreve um arquivo existente sem --sobrescrever.
"""

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUBTAMANHOS = [100, 50, 25, 20, 10, 5, 2, 1]


def montar_url(url_base, pagina, tamanho):
    partes = urllib.parse.urlsplit(url_base)
    params = urllib.parse.parse_qsl(partes.query, keep_blank_values=True)
    params = [(k, v) for k, v in params if k not in ("pagina", "tamanhoPagina")]
    params.append(("pagina", str(pagina)))
    params.append(("tamanhoPagina", str(tamanho)))
    consulta = urllib.parse.urlencode(params)
    return urllib.parse.urlunsplit(
        (partes.scheme, partes.netloc, partes.path, consulta, partes.fragment)
    )


def buscar(url, tentativas, espera_inicial, timeout):
    """GET com novas tentativas para erros temporarios. Erro 400 sobe direto."""
    espera = espera_inicial
    ultimo_erro = None
    for n in range(1, tentativas + 1):
        req = urllib.request.Request(
            url,
            headers={"accept": "*/*", "User-Agent": "portfolio-analise-compras/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 400:
                raise
            ultimo_erro = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            ultimo_erro = e
        print(f"  tentativa {n}/{tentativas} falhou ({ultimo_erro}), aguardando {espera}s")
        time.sleep(espera)
        espera = min(espera * 2, 60)
    raise RuntimeError(f"Falha apos {tentativas} tentativas: {ultimo_erro}")


def buscar_pagina(url_base, pagina, tamanho, total_registros, args):
    """Busca uma pagina. Se falhar, busca o mesmo trecho em pedacos menores."""
    try:
        return buscar(montar_url(url_base, pagina, tamanho), args.tentativas, args.espera, args.timeout)["resultado"]
    except RuntimeError as erro:
        print(f"  pagina {pagina} falhou ({erro}). Tentando em pedacos menores.")
    for sub in SUBTAMANHOS:
        if sub >= tamanho or tamanho % sub != 0:
            continue
        fator = tamanho // sub
        maximo = math.ceil(total_registros / sub)
        lote = []
        try:
            for k in range(fator):
                p = (pagina - 1) * fator + k + 1
                if p > maximo:
                    break
                d = buscar(montar_url(url_base, p, sub), args.tentativas, args.espera, args.timeout)
                lote.extend(d.get("resultado", []))
            print(f"  pagina {pagina} recuperada em pedacos de {sub}")
            return lote
        except (RuntimeError, urllib.error.HTTPError):
            print(f"  pedacos de {sub} tambem falharam, tentando menor")
    raise RuntimeError(f"Nao consegui baixar a pagina {pagina} nem em pedacos menores.")


def primeira_pagina(url_base, tamanho_pedido, args):
    """Descobre um tamanho de pagina aceito pela API."""
    tamanhos = [tamanho_pedido]
    while tamanhos[-1] > 1:
        tamanhos.append(max(1, tamanhos[-1] // 2))
    for t in tamanhos:
        try:
            dados = buscar(montar_url(url_base, 1, t), args.tentativas, args.espera, args.timeout)
            return t, dados
        except urllib.error.HTTPError as e:
            print(f"Tamanho de pagina {t} recusado (HTTP {e.code}), tentando menor.")
    sys.exit("Nenhum tamanho de pagina foi aceito. Confira a URL copiada do Swagger.")


def contar_linhas(caminho):
    csv.field_size_limit(10_000_000)
    with open(caminho, newline="", encoding="utf-8-sig") as f:
        leitor = csv.reader(f)
        cabecalho = next(leitor, None)
        n = sum(1 for _ in leitor)
    return cabecalho, n


def principal():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="Request URL copiada do Swagger")
    ap.add_argument("--saida", required=True, help="Arquivo CSV de saida")
    ap.add_argument("--tamanho", type=int, default=500, help="Tamanho de pagina desejado (padrao 500)")
    ap.add_argument("--pausa", type=float, default=0.5, help="Pausa entre paginas em segundos (padrao 0.5)")
    ap.add_argument("--timeout", type=float, default=120, help="Timeout de cada chamada em segundos (padrao 120)")
    ap.add_argument("--tentativas", type=int, default=4, help="Tentativas por chamada (padrao 4)")
    ap.add_argument("--espera", type=float, default=2, help="Espera inicial entre tentativas em segundos (padrao 2)")
    ap.add_argument("--retomar", action="store_true", help="Continua de um CSV parcial ja existente")
    ap.add_argument("--sobrescrever", action="store_true", help="Permite apagar um CSV existente e recomecar")
    args = ap.parse_args()

    existe = os.path.exists(args.saida)
    if existe and not args.retomar and not args.sobrescrever:
        sys.exit(
            f"O arquivo {args.saida} ja existe. Use --retomar para continuar de onde parou "
            "ou --sobrescrever para apagar e recomecar."
        )
    if args.retomar and not existe:
        sys.exit(f"--retomar pedido, mas {args.saida} nao existe.")

    tamanho, dados = primeira_pagina(args.url, args.tamanho, args)
    total_registros = dados.get("totalRegistros", 0)
    total_paginas = dados.get("totalPaginas", 0)
    print(f"Tamanho de pagina aceito: {tamanho}")
    print(f"Total de registros: {total_registros} em {total_paginas} paginas")
    if not dados.get("resultado"):
        sys.exit("A primeira pagina veio vazia. Confira as datas da consulta.")

    if args.retomar:
        cabecalho, ja_gravadas = contar_linhas(args.saida)
        if ja_gravadas % tamanho != 0:
            sys.exit(
                f"O arquivo tem {ja_gravadas} linhas, que nao e multiplo de {tamanho}. "
                "Ele pode ter sido cortado no meio de uma pagina. Use --sobrescrever e recomece."
            )
        pagina_inicial = ja_gravadas // tamanho + 1
        modo = "a"
        colunas = cabecalho
        print(f"Retomando: {ja_gravadas} linhas ja gravadas, continuando na pagina {pagina_inicial}")
    else:
        ja_gravadas = 0
        pagina_inicial = 1
        modo = "w"
        colunas = list(dados["resultado"][0].keys())

    linhas_gravadas = ja_gravadas
    with open(args.saida, modo, newline="", encoding="utf-8-sig" if modo == "w" else "utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        if modo == "w":
            escritor.writeheader()

        for pagina in range(pagina_inicial, total_paginas + 1):
            if pagina == 1:
                lote = dados["resultado"]
            else:
                time.sleep(args.pausa)
                lote = buscar_pagina(args.url, pagina, tamanho, total_registros, args)
            for linha in lote:
                escritor.writerow(linha)
            f.flush()
            linhas_gravadas += len(lote)
            if pagina % 10 == 0 or pagina == total_paginas:
                print(f"  pagina {pagina}/{total_paginas}, {linhas_gravadas} linhas")

    print(f"Pronto: {linhas_gravadas} linhas em {args.saida}")
    if linhas_gravadas != total_registros:
        print(
            f"ATENCAO: a API informou {total_registros} registros, mas o arquivo tem {linhas_gravadas}. "
            "Os dados podem ter mudado durante o download. Vou checar duplicados e lacunas na limpeza."
        )


if __name__ == "__main__":
    principal()
