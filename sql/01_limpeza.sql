-- =====================================================================
-- 01_limpeza.sql
-- Cria a tabela "itens" (uma linha por item de compra) a partir de
-- "itens_bruto". Decisoes de limpeza, todas documentadas no README:
--   1. Duplicados: fica a versao mais recente de cada idCompraItem
--      (maior dataAtualizacaoPncp; no empate, a linha com resultado).
--   2. Tipos: quantidades e valores viram REAL; ids continuam TEXTO.
--   3. A coluna itemCategoriaNome e descartada (100% "Informatica (TIC)").
--   4. conta_gasto = 1 so para item Homologado com valor total > 0.
--   5. segmento separa os itens de R$ 100 milhoes ou mais ("Mega"),
--      que concentram a maior parte do valor e distorcem as medias.
-- =====================================================================

DROP TABLE IF EXISTS itens;

CREATE TABLE itens AS
WITH ordenado AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY idCompraItem
               ORDER BY dataAtualizacaoPncp DESC,
                        (valorTotalResultado IS NOT NULL) DESC,  -- desempate: prefere a linha com resultado
                        rowid DESC
           ) AS versao
    FROM itens_bruto
)
SELECT
    idCompraItem                                AS id_item,
    idCompra                                    AS id_compra,
    orgaoEntidadeCnpj                           AS orgao_cnpj,
    unidadeOrgaoCodigoUnidade                   AS unidade_compradora,
    CAST(numeroItemPncp AS INTEGER)             AS numero_item,
    descricaoResumida                           AS descricao,
    CASE materialOuServico WHEN 'M' THEN 'Material' WHEN 'S' THEN 'Serviço' END AS tipo,
    codItemCatalogo                             AS cod_catalogo,
    codigoClasse                                AS cod_classe,
    nomePdm                                     AS nome_pdm,
    unidade_norm                                AS unidade,
    CASE orcamentoSigiloso WHEN 'True' THEN 1 ELSE 0 END AS orcamento_sigiloso,
    criterioJulgamentoNome                      AS criterio_julgamento,
    situacaoCompraItemNome                      AS situacao,
    CAST(quantidade AS REAL)                    AS qtd_estimada,
    CAST(valorUnitarioEstimado AS REAL)         AS vl_unit_estimado,
    CAST(valorTotal AS REAL)                    AS vl_total_estimado,
    fornecedor_id,
    CAST(quantidadeResultado AS REAL)           AS qtd_resultado,
    CAST(valorUnitarioResultado AS REAL)        AS vl_unit_resultado,
    CAST(valorTotalResultado AS REAL)           AS vl_total_resultado,
    substr(dataInclusaoPncp, 1, 10)             AS data_inclusao,
    substr(dataAtualizacaoPncp, 1, 10)          AS data_atualizacao,
    substr(dataResultado, 1, 10)                AS data_resultado,
    CASE WHEN situacaoCompraItemNome = 'Homologado'
              AND CAST(valorTotalResultado AS REAL) > 0
         THEN 1 ELSE 0 END                      AS conta_gasto,
    CASE WHEN CAST(valorTotalResultado AS REAL) >= 100000000
         THEN 'Mega (R$ 100 mi ou mais)' ELSE 'Comum' END AS segmento
FROM ordenado
WHERE versao = 1;

CREATE UNIQUE INDEX idx_itens_id       ON itens (id_item);
CREATE INDEX        idx_itens_catalogo ON itens (cod_catalogo, unidade);
CREATE INDEX        idx_itens_compra   ON itens (id_compra);
