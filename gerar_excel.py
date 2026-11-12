#!/usr/bin/env python3
"""
Gera o resumo em Excel (resumo_compras_2025-03.xlsx) a partir das views do banco.
Requer openpyxl:  pip install openpyxl

Uso:
  python gerar_excel.py --banco compras.db --saida resumo_compras_2025-03.xlsx

As abas de dados trazem o resultado das views SQL. Percentuais, acumulados,
classes ABC e todos os indicadores da aba Resumo sao FORMULAS do Excel.
"""
import argparse, sqlite3
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

FONTE = "Arial"
AZUL, LARANJA = "2A78D6", "EB6834"
F_BASE = Font(name=FONTE, size=10)
F_CAB = Font(name=FONTE, size=10, bold=True, color="FFFFFF")
P_CAB = PatternFill("solid", start_color="1F3A5F")
MOEDA, MOEDA2, INT, PCT, DEC = '"R$" #,##0', '"R$" #,##0.00', "#,##0", "0.0%", "#,##0.00"


def aba(wb, nome, cab, linhas, larguras, formatos=None):
    ws = wb.create_sheet(nome)
    ws.append(cab)
    for r in linhas:
        ws.append(list(r))
    for c in range(1, len(cab) + 1):
        cel = ws.cell(row=1, column=c)
        cel.font, cel.fill = F_CAB, P_CAB
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[L(c)].width = larguras[c - 1]
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{L(len(cab))}{max(ws.max_row, 2)}"
    return ws


def formatar(ws, formatos, ultima):
    for linha in ws.iter_rows(min_row=2, max_row=ultima):
        for cel in linha:
            cel.font = F_BASE
            f = formatos.get(cel.column_letter)
            if f:
                cel.number_format = f


def grafico(titulo, ws, col_val, col_cat, lin_ini, lin_fim, cor, horizontal=False, fmt=None, com_titulo_serie=False):
    g = BarChart()
    g.type = "bar" if horizontal else "col"
    g.title = titulo
    g.style = 10
    ini = lin_ini - 1 if com_titulo_serie else lin_ini
    for i, c in enumerate(col_val):
        g.add_data(Reference(ws, min_col=c, min_row=ini, max_row=lin_fim), titles_from_data=com_titulo_serie)
        g.series[i].graphicalProperties.solidFill = cor[i]
        g.series[i].graphicalProperties.line.solidFill = cor[i]
    g.set_categories(Reference(ws, min_col=col_cat, min_row=lin_ini, max_row=lin_fim))
    g.legend = None if len(col_val) == 1 else g.legend
    if g.legend is not None:
        g.legend.position = "b"
    g.x_axis.delete = False
    g.y_axis.delete = False
    g.y_axis.majorGridlines = None
    g.gapWidth = 60
    if horizontal:
        g.x_axis.scaling.orientation = "maxMin"
    if fmt:
        g.y_axis.number_format = fmt
        g.dataLabels = DataLabelList()
        g.dataLabels.showVal = True
        g.dataLabels.showSerName = g.dataLabels.showCatName = g.dataLabels.showLegendKey = False
        g.dataLabels.numFmt = fmt
    g.width, g.height = 17, 8.5
    return g


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    con = sqlite3.connect(a.banco)
    q = lambda s: con.execute(s).fetchall()
    wb = Workbook()
    res = wb.active
    res.title = "Resumo"

    # ---------------- abas de dados ----------------
    d = q("SELECT situacao, itens FROM vw_01_situacao_itens")
    ws = aba(wb, "Situacao", ["Situação do item", "Itens", "% dos itens"], d, [30, 12, 12])
    n_sit = len(d) + 1
    for r in range(2, n_sit + 1):
        ws[f"C{r}"] = f"=B{r}/SUM($B$2:$B${n_sit})"
    formatar(ws, {"B": INT, "C": PCT}, n_sit)

    d = q("SELECT segmento, itens, gasto FROM vw_02_gasto_por_segmento ORDER BY segmento")
    ws = aba(wb, "Segmento", ["Segmento", "Itens", "Gasto homologado (R$)", "% do gasto"], d, [28, 12, 24, 12])
    for r in (2, 3):
        ws[f"D{r}"] = f"=C{r}/SUM($C$2:$C$3)"
    formatar(ws, {"B": INT, "C": MOEDA, "D": PCT}, 3)

    d = q("SELECT id_item, orgao_cnpj, tipo, descricao, unidade, qtd_resultado, vl_unit_resultado, vl_total_resultado FROM vw_03_itens_mega")
    ws = aba(wb, "Itens_Mega", ["Id do item", "CNPJ do órgão", "Tipo", "Descrição", "Unidade", "Quantidade", "Preço unitário (R$)", "Valor total (R$)"],
             d, [26, 17, 10, 70, 18, 16, 20, 20])
    n_mega = len(d) + 1
    formatar(ws, {"F": INT, "G": MOEDA2, "H": MOEDA}, n_mega)

    d = q("SELECT grupo, itens, orgaos, gasto_total, gasto_sem_mega FROM vw_04_gasto_por_grupo_material ORDER BY gasto_sem_mega DESC LIMIT 50")
    ws_grp = aba(wb, "Grupos_Material", ["Grupo de material (PDM)", "Itens", "Órgãos", "Gasto total (R$)", "Gasto sem itens Mega (R$)", "Gasto sem itens Mega (R$ milhões)"],
                 d, [42, 10, 10, 20, 24, 22])
    for r in range(2, len(d) + 2):
        ws_grp[f"F{r}"] = f"=E{r}/1000000"
    formatar(ws_grp, {"B": INT, "C": INT, "D": MOEDA, "E": MOEDA, "F": "#,##0.0"}, len(d) + 1)

    d = q("SELECT classe, itens_catalogo, gasto FROM vw_06_abc_resumo ORDER BY classe")
    ws_abc = aba(wb, "ABC_Resumo", ["Classe", "Itens de catálogo", "% dos itens", "Gasto (R$)", "% do gasto"],
                 [(c, n, None, g, None) for c, n, g in d], [10, 18, 14, 22, 14])
    for r in (2, 3, 4):
        ws_abc[f"C{r}"] = f"=B{r}/SUM($B$2:$B$4)"
        ws_abc[f"E{r}"] = f"=D{r}/SUM($D$2:$D$4)"
    formatar(ws_abc, {"B": INT, "C": PCT, "D": MOEDA, "E": PCT}, 4)

    d = q("SELECT cod_catalogo, tipo, descricao_exemplo, compras, orgaos, gasto FROM vw_05_abc_itens WHERE classe IN ('A','B') ORDER BY gasto DESC, cod_catalogo")
    ws = aba(wb, "ABC_Itens", ["Código de catálogo", "Tipo", "Descrição (exemplo)", "Compras", "Órgãos", "Gasto (R$)", "% do gasto", "% acumulado", "Classe"],
             d, [16, 10, 70, 10, 10, 20, 12, 13, 9])
    n_abc = len(d) + 1
    for r in range(2, n_abc + 1):
        ws[f"G{r}"] = f"=F{r}/SUM(ABC_Resumo!$D$2:$D$4)"
        ws[f"H{r}"] = "=G2" if r == 2 else f"=H{r-1}+G{r}"
        ws[f"I{r}"] = f'=IF(H{r}-G{r}<0.8,"A",IF(H{r}-G{r}<0.95,"B","C"))'
    formatar(ws, {"D": INT, "E": INT, "F": MOEDA, "G": "0.000%", "H": "0.00%"}, n_abc)

    d = q("""SELECT cod_catalogo, unidade, grupo, descricao_exemplo, compras, orgaos, gasto, preco_min, preco_q1,
                    preco_mediana, preco_q3, preco_max, NULL, compras_fora_da_faixa, economia_potencial, NULL
             FROM vw_07_variacao_preco""")
    ws = aba(wb, "Variacao_Preco", ["Código de catálogo", "Unidade", "Grupo (PDM)", "Descrição (exemplo)", "Compras", "Órgãos", "Gasto (R$)",
                                    "Preço mín.", "Preço Q1", "Preço mediano", "Preço Q3", "Preço máx.", "Razão Q3/Q1",
                                    "Compras fora da faixa", "Economia potencial (R$)", "Economia / gasto"],
             d, [16, 22, 30, 60, 10, 10, 18, 12, 12, 14, 12, 14, 12, 14, 22, 14])
    n_var = len(d) + 1
    for r in range(2, n_var + 1):
        ws[f"M{r}"] = f"=K{r}/I{r}"
        ws[f"P{r}"] = f"=IF(G{r}>0,O{r}/G{r},0)"
    formatar(ws, {"E": INT, "F": INT, "G": MOEDA, "H": DEC, "I": DEC, "J": DEC, "K": DEC, "L": DEC, "M": DEC, "N": INT, "O": MOEDA, "P": PCT}, n_var)

    d = q("SELECT tipo, criterio_julgamento, itens, desertos, fracassados FROM vw_08_insucesso")
    ws = aba(wb, "Insucesso", ["Tipo", "Critério de julgamento", "Itens", "Desertos", "Fracassados", "% de insucesso"], d, [12, 26, 12, 12, 14, 16])
    n_ins = len(d) + 1
    for r in range(2, n_ins + 1):
        ws[f"F{r}"] = f"=(D{r}+E{r})/C{r}"
    formatar(ws, {"C": INT, "D": INT, "E": INT, "F": PCT}, n_ins)

    d = q("SELECT tipo, faixa, itens, total_estimado, total_homologado FROM vw_09_estimado_x_homologado")
    ws_est = aba(wb, "Estimado_x_Homologado", ["Tipo", "Faixa", "Itens", "Total estimado (R$)", "Total homologado (R$)"], d, [12, 28, 12, 24, 24])
    n_est = len(d) + 1
    formatar(ws_est, {"C": INT, "D": MOEDA, "E": MOEDA}, n_est)
    faixas = sorted({r[1] for r in d})
    for j, t in enumerate(["Faixa (materiais + serviços)", "Itens", "% dos itens"]):
        c = ws_est.cell(row=1, column=8 + j, value=t)
        c.font, c.fill = F_CAB, P_CAB
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws_est.column_dimensions["H"].width, ws_est.column_dimensions["I"].width, ws_est.column_dimensions["J"].width = 30, 12, 12
    for i, fx in enumerate(faixas):
        r = 2 + i
        ws_est[f"H{r}"] = fx
        ws_est[f"I{r}"] = f"=SUMIFS($C$2:$C${n_est},$B$2:$B${n_est},H{r})"
        ws_est[f"J{r}"] = f"=I{r}/SUM($I$2:$I${1+len(faixas)})"
        ws_est[f"H{r}"].font = ws_est[f"I{r}"].font = ws_est[f"J{r}"].font = F_BASE
        ws_est[f"I{r}"].number_format, ws_est[f"J{r}"].number_format = INT, PCT
    n_fx = 1 + len(faixas)

    d = q("SELECT posicao, fornecedor_id, itens, orgaos, gasto FROM vw_10_concentracao_fornecedores LIMIT 100")
    ws = aba(wb, "Fornecedores", ["Posição", "Fornecedor (código anônimo)", "Itens", "Órgãos", "Gasto (R$)", "% do gasto (segmento Comum)", "% acumulado"],
             d, [10, 26, 10, 10, 20, 20, 14])
    for r in range(2, len(d) + 2):
        ws[f"F{r}"] = f'=E{r}/SUMIF(Segmento!$A$2:$A$3,"Comum",Segmento!$C$2:$C$3)'
        ws[f"G{r}"] = "=F2" if r == 2 else f"=G{r-1}+F{r}"
    formatar(ws, {"C": INT, "D": INT, "E": MOEDA, "F": "0.00%", "G": "0.00%"}, len(d) + 1)

    d = q("SELECT indicador, valor FROM vw_11_qualidade_dados")
    ws = aba(wb, "Qualidade", ["Indicador de qualidade dos dados", "Valor"], d, [72, 14])
    formatar(ws, {"B": INT}, len(d) + 1)

    # ---------------- notas ----------------
    ws = wb.create_sheet("Notas")
    ws.column_dimensions["A"].width = 130
    notas = [
        ("Fonte e período", True),
        ("API de Dados Abertos do Compras.gov.br, módulo de contratações (Lei 14.133/2021), endpoint 2_consultarItensContratacoes_PNCP_14133.", False),
        ("Itens incluídos no PNCP entre 01/03/2025 e 31/03/2025. Download feito em 11/11/2026.", False),
        ("Como este arquivo foi gerado", True),
        ("As abas de dados são o resultado das views SQL (sql/02_analises.sql) sobre a tabela limpa 'itens' (sql/01_limpeza.sql).", False),
        ("Percentuais, acumulados, classes ABC e todos os indicadores da aba Resumo são fórmulas do Excel.", False),
        ("Decisões de método", True),
        ("1. Duplicados: fica a versão mais recente de cada item (maior data de atualização; no empate, a linha com resultado).", False),
        ("2. Gasto = valor total homologado, somente itens com situação 'Homologado' e valor maior que zero.", False),
        ("3. Itens de R$ 100 milhões ou mais formam o segmento 'Mega', analisado à parte (aba Itens_Mega).", False),
        ("4. Curva ABC por código de catálogo, segmento Comum: A até 80% do gasto acumulado, B até 95%, C o restante. A aba ABC_Itens lista só as classes A e B.", False),
        ("5. Variação de preço: materiais do segmento Comum, mesmo código de catálogo e mesma unidade, comprados por 5 ou mais órgãos em 5 ou mais compras.", False),
        ("6. Economia potencial: diferença para a mediana nas compras com preço entre a mediana e 3 vezes a mediana. Preços acima de 3x ou abaixo de 1/3 da mediana ficam fora (coluna 'Compras fora da faixa').", False),
        ("7. Fornecedores aparecem só como códigos anônimos. Nomes e CNPJ de fornecedores não foram carregados.", False),
        ("Limitações", True),
        ("A coluna de categoria da fonte traz 'Informática (TIC)' em 100% dos itens e foi descartada.", False),
        ("Cerca de 3,9% dos itens podem estar ausentes (lacunas na numeração dos itens de 499 compras), provável efeito da paginação da API durante o download.", False),
        ("O mesmo código de catálogo pode reunir marcas e embalagens diferentes. A economia potencial é um teto para investigação, não um valor garantido.", False),
        ("Os valores dos itens Mega não foram conferidos no portal e podem ser valores de teto de contrato ou erro de cadastro.", False),
        ("Na faixa 'Desconto acima de 50%' o total estimado é muito maior que o homologado, o que indica estimativas erradas. Use a distribuição por faixa, não a soma.", False),
        ("Itens de 2025 ainda 'Em andamento' não têm resultado e não entram no gasto.", False),
    ]
    for i, (t, titulo) in enumerate(notas, start=1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = Font(name=FONTE, size=11 if titulo else 10, bold=titulo)
        c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------------- resumo ----------------
    res.sheet_view.showGridLines = False
    res.column_dimensions["A"].width, res.column_dimensions["B"].width, res.column_dimensions["C"].width = 52, 22, 70
    res["A1"] = "Compras públicas federais, itens incluídos no PNCP em março de 2025"
    res["A1"].font = Font(name=FONTE, size=14, bold=True)
    res["A2"] = "Onde está o gasto e quanto varia o preço pago pelo mesmo item entre órgãos. Fonte e método na aba Notas."
    res["A2"].font = Font(name=FONTE, size=10, italic=True, color="52514E")
    for j, t in enumerate(["Indicador", "Valor", "Como ler"], start=1):
        c = res.cell(row=4, column=j, value=t)
        c.font, c.fill = F_CAB, P_CAB
    QB = lambda rot: f'=INDEX(Qualidade!$B:$B,MATCH("{rot}",Qualidade!$A:$A,0))'
    INS = lambda tipo: (f'=(SUMIFS(Insucesso!$D:$D,Insucesso!$A:$A,"{tipo}",Insucesso!$B:$B,"Menor preço")'
                        f'+SUMIFS(Insucesso!$E:$E,Insucesso!$A:$A,"{tipo}",Insucesso!$B:$B,"Menor preço"))'
                        f'/SUMIFS(Insucesso!$C:$C,Insucesso!$A:$A,"{tipo}",Insucesso!$B:$B,"Menor preço")')
    kpis = [
        ("VOLUME", None, None, None),
        ("Linhas baixadas da API", QB("Linhas no arquivo bruto"), INT, "Inclui duplicados gerados pela paginação"),
        ("Itens únicos analisados", QB("Itens unicos apos remover duplicados"), INT, "Versão mais recente de cada item"),
        ("% de itens homologados", '=INDEX(Situacao!$C:$C,MATCH("Homologado",Situacao!$A:$A,0))', PCT, "O restante fracassou, ficou deserto, foi anulado ou está em andamento"),
        ("GASTO", None, None, None),
        ("Gasto homologado total", "=SUM(Segmento!$C$2:$C$3)", MOEDA, "Itens homologados com valor maior que zero"),
        ("Itens Mega (R$ 100 mi ou mais)", '=SUMIF(Segmento!$A:$A,"Mega*",Segmento!$B:$B)', INT, "Lista completa na aba Itens_Mega"),
        ("% do gasto nos itens Mega", '=SUMIF(Segmento!$A:$A,"Mega*",Segmento!$D:$D)', PCT, "Poucos itens concentram a maior parte do valor"),
        ("Gasto do segmento Comum", '=SUMIF(Segmento!$A:$A,"Comum",Segmento!$C:$C)', MOEDA, "Base das análises abaixo"),
        ("CURVA ABC (segmento Comum)", None, None, None),
        ("Itens de catálogo na classe A", '=INDEX(ABC_Resumo!$B:$B,MATCH("A",ABC_Resumo!$A:$A,0))', INT, "Respondem por 80% do gasto"),
        ("Classe A, % dos itens de catálogo", '=INDEX(ABC_Resumo!$C:$C,MATCH("A",ABC_Resumo!$A:$A,0))', PCT, "Onde concentrar negociação e controle"),
        ("Classe C, % dos itens de catálogo", '=INDEX(ABC_Resumo!$C:$C,MATCH("C",ABC_Resumo!$A:$A,0))', PCT, "Muitos itens, pouco valor"),
        ("Classe C, % do gasto", '=INDEX(ABC_Resumo!$E:$E,MATCH("C",ABC_Resumo!$A:$A,0))', PCT, ""),
        ("VARIAÇÃO DE PREÇO ENTRE ÓRGÃOS (materiais)", None, None, None),
        ("Materiais comparáveis (5 ou mais órgãos)", f"=COUNTA(Variacao_Preco!$A$2:$A${n_var})", INT, "Mesmo código de catálogo e mesma unidade"),
        ("Razão Q3/Q1 mediana", f"=MEDIAN(Variacao_Preco!$M$2:$M${n_var})", DEC, "1,42 significa: o 3º quartil de preço é 42% maior que o 1º"),
        ("Materiais com razão Q3/Q1 de 2 ou mais", f'=COUNTIF(Variacao_Preco!$M$2:$M${n_var},">=2")', INT, "Candidatos a padronização ou compra conjunta"),
        ("Gasto coberto pela comparação", f"=SUM(Variacao_Preco!$G$2:$G${n_var})", MOEDA, ""),
        ("Economia potencial (teto)", f"=SUM(Variacao_Preco!$O$2:$O${n_var})", MOEDA, "Se as compras acima da mediana pagassem a mediana (ver Notas)"),
        ("Economia potencial / gasto coberto", f"=SUM(Variacao_Preco!$O$2:$O${n_var})/SUM(Variacao_Preco!$G$2:$G${n_var})", PCT, ""),
        ("LICITAÇÃO E FORNECEDORES", None, None, None),
        ("Insucesso em materiais (menor preço)", INS("Material"), PCT, "Itens desertos ou fracassados"),
        ("Insucesso em serviços (menor preço)", INS("Serviço"), PCT, ""),
        ("Itens com desconto acima de 50% sobre o estimado", '=INDEX(Estimado_x_Homologado!$J:$J,MATCH("6*",Estimado_x_Homologado!$H:$H,0))', PCT, "Sinal de estimativas pouco confiáveis"),
        ("10 maiores fornecedores, % do gasto Comum", "=Fornecedores!$G$11", PCT, "Gasto pulverizado entre milhares de fornecedores"),
    ]
    fina = Side(style="thin", color="D9D9D9")
    for i, (rot, form, fmt, nota) in enumerate(kpis, start=5):
        ca, cb, cc = res.cell(row=i, column=1, value=rot), res.cell(row=i, column=2, value=form), res.cell(row=i, column=3, value=nota)
        if form is None:
            ca.font = Font(name=FONTE, size=10, bold=True, color="1F3A5F")
            ca.fill = cb.fill = cc.fill = PatternFill("solid", start_color="EAF0F7")
        else:
            ca.font, cc.font = F_BASE, Font(name=FONTE, size=9, color="52514E")
            cb.font = Font(name=FONTE, size=10, bold=True)
            cb.number_format = fmt
            cb.alignment = Alignment(horizontal="right")
            for x in (ca, cb, cc):
                x.border = Border(bottom=fina)
    res.freeze_panes = "A5"

    # graficos (ao lado da tabela)
    res.add_chart(grafico("Classe A: 1,3% dos itens de catálogo, 80% do gasto", ws_abc, [3, 5], 1, 2, 4, [AZUL, LARANJA], fmt="0%", com_titulo_serie=True), "E4")
    g2 = grafico("Maiores grupos de materiais, gasto em R$ milhões (sem itens Mega)", ws_grp, [6], 1, 2, 11, [AZUL], horizontal=True, fmt="#,##0")
    g2.height = 11
    res.add_chart(g2, "E22")
    res.add_chart(grafico("Situação dos itens (% dos itens)", wb["Situacao"], [3], 1, 2, n_sit, [AZUL], horizontal=True, fmt="0.0%"), "P4")
    res.add_chart(grafico("Itens por faixa de desconto sobre o estimado", ws_est, [10], 8, 2, n_fx, [AZUL], horizontal=True, fmt="0.0%"), "P22")

    wb.save(a.saida)
    print("gerado:", a.saida)

if __name__ == "__main__":
    principal()
