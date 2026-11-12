-- =====================================================================
-- 02_analises.sql
-- Views de analise sobre a tabela "itens". Cada view responde a uma
-- pergunta e pode ser aberta no DB Browser (aba "Navegar dados") ou
-- exportada para CSV/Excel.
-- "Gasto" = valor total homologado (conta_gasto = 1).
-- =====================================================================

-- 1) Como terminaram os itens incluidos no periodo?
DROP VIEW IF EXISTS vw_01_situacao_itens;
CREATE VIEW vw_01_situacao_itens AS
SELECT situacao,
       COUNT(*)                                             AS itens,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM itens), 1) AS pct_itens
FROM itens
GROUP BY situacao
ORDER BY itens DESC;

-- 2) Quanto do gasto esta nos itens "Mega"?
DROP VIEW IF EXISTS vw_02_gasto_por_segmento;
CREATE VIEW vw_02_gasto_por_segmento AS
SELECT segmento,
       COUNT(*)                          AS itens,
       ROUND(SUM(vl_total_resultado), 2) AS gasto,
       ROUND(100.0 * SUM(vl_total_resultado)
             / (SELECT SUM(vl_total_resultado) FROM itens WHERE conta_gasto = 1), 1) AS pct_gasto
FROM itens
WHERE conta_gasto = 1
GROUP BY segmento;

-- 3) Lista dos itens Mega, para checagem manual no portal
DROP VIEW IF EXISTS vw_03_itens_mega;
CREATE VIEW vw_03_itens_mega AS
SELECT id_item, orgao_cnpj, tipo, descricao, unidade,
       qtd_resultado, vl_unit_resultado, vl_total_resultado
FROM itens
WHERE conta_gasto = 1 AND segmento <> 'Comum'
ORDER BY vl_total_resultado DESC;

-- 4) Onde esta o gasto com materiais? (grupo = PDM do catalogo)
DROP VIEW IF EXISTS vw_04_gasto_por_grupo_material;
CREATE VIEW vw_04_gasto_por_grupo_material AS
SELECT COALESCE(nome_pdm, '(sem PDM)')    AS grupo,
       COUNT(*)                           AS itens,
       COUNT(DISTINCT orgao_cnpj)         AS orgaos,
       ROUND(SUM(vl_total_resultado), 2)  AS gasto_total,
       ROUND(SUM(CASE WHEN segmento = 'Comum' THEN vl_total_resultado ELSE 0 END), 2) AS gasto_sem_mega
FROM itens
WHERE conta_gasto = 1 AND tipo = 'Material'
GROUP BY 1
ORDER BY gasto_total DESC;

-- 5) Curva ABC por item de catalogo (segmento Comum)
--    A = ate 80% do gasto acumulado, B = ate 95%, C = restante
DROP VIEW IF EXISTS vw_05_abc_itens;
CREATE VIEW vw_05_abc_itens AS
WITH por_item AS (
    SELECT cod_catalogo,
           tipo,
           MIN(descricao)             AS descricao_exemplo,
           COUNT(*)                   AS compras,
           COUNT(DISTINCT orgao_cnpj) AS orgaos,
           SUM(vl_total_resultado)    AS gasto
    FROM itens
    WHERE conta_gasto = 1 AND segmento = 'Comum' AND cod_catalogo IS NOT NULL
    GROUP BY cod_catalogo, tipo
),
acumulado AS (
    SELECT *,
           SUM(gasto) OVER (ORDER BY gasto DESC, cod_catalogo
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS gasto_acum,
           SUM(gasto) OVER ()                                               AS gasto_geral
    FROM por_item
)
SELECT cod_catalogo, tipo, descricao_exemplo, compras, orgaos,
       ROUND(gasto, 2)                            AS gasto,
       ROUND(100.0 * gasto / gasto_geral, 3)      AS pct_gasto,
       ROUND(100.0 * gasto_acum / gasto_geral, 2) AS pct_acumulado,
       CASE WHEN (gasto_acum - gasto) / gasto_geral < 0.80 THEN 'A'
            WHEN (gasto_acum - gasto) / gasto_geral < 0.95 THEN 'B'
            ELSE 'C' END                          AS classe
FROM acumulado
ORDER BY gasto DESC;

DROP VIEW IF EXISTS vw_06_abc_resumo;
CREATE VIEW vw_06_abc_resumo AS
SELECT classe,
       COUNT(*)                                              AS itens_catalogo,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM vw_05_abc_itens), 1) AS pct_itens,
       ROUND(SUM(gasto), 2)                                  AS gasto,
       ROUND(100.0 * SUM(gasto) / (SELECT SUM(gasto) FROM vw_05_abc_itens), 1) AS pct_gasto
FROM vw_05_abc_itens
GROUP BY classe;

-- 6) Quanto varia o preco do MESMO item (catalogo + unidade) entre orgaos?
--    Apenas materiais, segmento Comum, comprados por 5 ou mais orgaos.
--    Quartis aproximados por posicao.
--    "economia_potencial" = quanto se economizaria se as compras com preco
--    entre a mediana e 3x a mediana tivessem pago a mediana.
--    Precos acima de 3x ou abaixo de 1/3 da mediana sao contados em
--    "compras_fora_da_faixa" e NAO entram na economia: costumam ser erro de
--    cadastro (unidade trocada) ou produto diferente no mesmo codigo.
--    Atencao: o mesmo codigo pode reunir marcas e embalagens diferentes,
--    entao a economia e um teto para investigacao, nao um valor garantido.
DROP VIEW IF EXISTS vw_07_variacao_preco;
CREATE VIEW vw_07_variacao_preco AS
WITH base AS (
    SELECT cod_catalogo, unidade, nome_pdm, descricao, orgao_cnpj,
           qtd_resultado, vl_unit_resultado, vl_total_resultado
    FROM itens
    WHERE conta_gasto = 1 AND segmento = 'Comum' AND tipo = 'Material'
      AND cod_catalogo IS NOT NULL AND unidade IS NOT NULL
      AND vl_unit_resultado > 0 AND qtd_resultado > 0
),
posicao AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY cod_catalogo, unidade ORDER BY vl_unit_resultado) AS pos,
           COUNT(*)     OVER (PARTITION BY cod_catalogo, unidade)                            AS n
    FROM base
),
estat AS (
    SELECT cod_catalogo, unidade,
           MIN(nome_pdm)                AS grupo,
           MIN(descricao)               AS descricao_exemplo,
           COUNT(*)                     AS compras,
           COUNT(DISTINCT orgao_cnpj)   AS orgaos,
           SUM(vl_total_resultado)      AS gasto,
           MIN(vl_unit_resultado)       AS preco_min,
           MAX(CASE WHEN pos = (n + 3) / 4 THEN vl_unit_resultado END)              AS preco_q1,
           AVG(CASE WHEN pos IN ((n + 1) / 2, (n + 2) / 2) THEN vl_unit_resultado END) AS preco_mediana,
           MAX(CASE WHEN pos = (3 * n + 1) / 4 THEN vl_unit_resultado END)          AS preco_q3,
           MAX(vl_unit_resultado)       AS preco_max
    FROM posicao
    GROUP BY cod_catalogo, unidade
    HAVING COUNT(DISTINCT orgao_cnpj) >= 5 AND COUNT(*) >= 5
)
SELECT e.cod_catalogo, e.unidade, e.grupo, e.descricao_exemplo, e.compras, e.orgaos,
       ROUND(e.gasto, 2)          AS gasto,
       ROUND(e.preco_min, 4)      AS preco_min,
       ROUND(e.preco_q1, 4)       AS preco_q1,
       ROUND(e.preco_mediana, 4)  AS preco_mediana,
       ROUND(e.preco_q3, 4)       AS preco_q3,
       ROUND(e.preco_max, 4)      AS preco_max,
       ROUND(e.preco_q3 / e.preco_q1, 2) AS razao_q3_q1,
       (SELECT COUNT(*) FROM base b
         WHERE b.cod_catalogo = e.cod_catalogo AND b.unidade = e.unidade
           AND (b.vl_unit_resultado > 3 * e.preco_mediana
                OR b.vl_unit_resultado < e.preco_mediana / 3)) AS compras_fora_da_faixa,
       ROUND(COALESCE((SELECT SUM((b.vl_unit_resultado - e.preco_mediana) * b.qtd_resultado)
              FROM base b
              WHERE b.cod_catalogo = e.cod_catalogo AND b.unidade = e.unidade
                AND b.vl_unit_resultado > e.preco_mediana
                AND b.vl_unit_resultado <= 3 * e.preco_mediana), 0), 2) AS economia_potencial
FROM estat e
ORDER BY economia_potencial DESC;

-- 7) Taxa de insucesso (Deserto + Fracassado) por tipo e criterio
DROP VIEW IF EXISTS vw_08_insucesso;
CREATE VIEW vw_08_insucesso AS
SELECT tipo, criterio_julgamento,
       COUNT(*)                                                        AS itens,
       SUM(situacao = 'Deserto')                                       AS desertos,
       SUM(situacao = 'Fracassado')                                    AS fracassados,
       ROUND(100.0 * SUM(situacao IN ('Deserto', 'Fracassado')) / COUNT(*), 1) AS pct_insucesso
FROM itens
GROUP BY tipo, criterio_julgamento
HAVING COUNT(*) >= 100
ORDER BY itens DESC;

-- 8) Estimado x homologado (preco unitario), so onde a estimativa existe
--    e o orcamento nao e sigiloso. Faixas de desconto.
DROP VIEW IF EXISTS vw_09_estimado_x_homologado;
CREATE VIEW vw_09_estimado_x_homologado AS
WITH d AS (
    SELECT tipo,
           1.0 - vl_unit_resultado / vl_unit_estimado AS desconto,
           vl_unit_estimado * qtd_resultado           AS total_estimado,
           vl_total_resultado
    FROM itens
    WHERE conta_gasto = 1 AND segmento = 'Comum' AND orcamento_sigiloso = 0
      AND vl_unit_estimado > 0 AND vl_unit_resultado > 0
)
SELECT tipo,
       CASE WHEN desconto < -0.001 THEN '1. Acima do estimado'
            WHEN desconto <= 0.001 THEN '2. Igual ao estimado'
            WHEN desconto <= 0.10  THEN '3. Desconto ate 10%'
            WHEN desconto <= 0.30  THEN '4. Desconto de 10% a 30%'
            WHEN desconto <= 0.50  THEN '5. Desconto de 30% a 50%'
            ELSE                        '6. Desconto acima de 50%' END AS faixa,
       COUNT(*)                         AS itens,
       ROUND(SUM(total_estimado), 2)    AS total_estimado,
       ROUND(SUM(vl_total_resultado), 2) AS total_homologado
FROM d
GROUP BY tipo, faixa
ORDER BY tipo, faixa;

-- 9) Concentracao de fornecedores (codigos anonimos), segmento Comum
DROP VIEW IF EXISTS vw_10_concentracao_fornecedores;
CREATE VIEW vw_10_concentracao_fornecedores AS
WITH f AS (
    SELECT fornecedor_id,
           COUNT(*)                   AS itens,
           COUNT(DISTINCT orgao_cnpj) AS orgaos,
           SUM(vl_total_resultado)    AS gasto
    FROM itens
    WHERE conta_gasto = 1 AND segmento = 'Comum' AND fornecedor_id IS NOT NULL
    GROUP BY fornecedor_id
)
SELECT ROW_NUMBER() OVER (ORDER BY gasto DESC) AS posicao,
       fornecedor_id, itens, orgaos,
       ROUND(gasto, 2) AS gasto,
       ROUND(100.0 * gasto / SUM(gasto) OVER (), 2) AS pct_gasto,
       ROUND(100.0 * SUM(gasto) OVER (ORDER BY gasto DESC, fornecedor_id
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(gasto) OVER (), 2) AS pct_acumulado
FROM f
ORDER BY gasto DESC;

-- 10) Painel de qualidade dos dados
DROP VIEW IF EXISTS vw_11_qualidade_dados;
CREATE VIEW vw_11_qualidade_dados AS
SELECT 'Linhas no arquivo bruto' AS indicador, (SELECT COUNT(*) FROM itens_bruto) AS valor
UNION ALL SELECT 'Itens unicos apos remover duplicados', (SELECT COUNT(*) FROM itens)
UNION ALL SELECT 'Linhas duplicadas removidas', (SELECT COUNT(*) FROM itens_bruto) - (SELECT COUNT(*) FROM itens)
UNION ALL SELECT 'Itens com categoria "Informática (TIC)" no bruto (campo descartado)',
                 (SELECT COUNT(*) FROM itens_bruto WHERE itemCategoriaNome = 'Informática (TIC)')
UNION ALL SELECT 'Itens sem codigo de catalogo', (SELECT COUNT(*) FROM itens WHERE cod_catalogo IS NULL)
UNION ALL SELECT 'Itens com estimativa zerada ou vazia', (SELECT COUNT(*) FROM itens WHERE COALESCE(vl_unit_estimado, 0) = 0)
UNION ALL SELECT 'Itens com orcamento sigiloso', (SELECT COUNT(*) FROM itens WHERE orcamento_sigiloso = 1)
UNION ALL SELECT 'Itens nao homologados com resultado preenchido',
                 (SELECT COUNT(*) FROM itens WHERE situacao <> 'Homologado' AND vl_total_resultado IS NOT NULL)
UNION ALL SELECT 'Resultados com preco unitario <= 0', (SELECT COUNT(*) FROM itens WHERE vl_unit_resultado <= 0)
UNION ALL SELECT 'Resultados com data anterior a inclusao', (SELECT COUNT(*) FROM itens WHERE data_resultado < data_inclusao)
UNION ALL SELECT 'Grafias distintas de unidade de medida', (SELECT COUNT(DISTINCT unidade) FROM itens)
UNION ALL SELECT 'Compras com lacuna na numeracao dos itens',
                 (SELECT COUNT(*) FROM (SELECT id_compra FROM itens GROUP BY id_compra HAVING MAX(numero_item) > COUNT(*)))
UNION ALL SELECT 'Itens possivelmente ausentes (lacunas)',
                 (SELECT SUM(falta) FROM (SELECT MAX(numero_item) - COUNT(*) AS falta FROM itens GROUP BY id_compra HAVING MAX(numero_item) > COUNT(*)));
