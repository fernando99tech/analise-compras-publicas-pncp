# Compras públicas federais: onde está o gasto e quanto varia o preço do mesmo item

Análise de **194 mil itens de compras** do governo federal incluídos no Portal Nacional de Contratações Públicas (PNCP) em março de 2025, feita com **SQL (SQLite)** e **Excel**, com Python apenas para baixar e carregar os dados.

**Pergunta de negócio:** onde o gasto se concentra e quanto varia o preço pago pelo mesmo material entre órgãos diferentes?

## Principais achados

| # | Achado | Número |
|---|---|---|
| 1 | Poucos itens concentram quase todo o valor | 36 itens de R$ 100 milhões ou mais somam **69,5%** dos R$ 53,4 bilhões homologados |
| 2 | Fora esses 36, vale a regra de Pareto | **1,3%** dos itens de catálogo (546) respondem por **80%** do gasto, e 91,5% respondem por só 5% |
| 3 | O mesmo material é pago a preços bem diferentes | Em 2.870 materiais comprados por 5 ou mais órgãos, o 3º quartil de preço é em mediana **42% maior** que o 1º, e em 611 deles é pelo menos o dobro |
| 4 | Há economia potencial a investigar | Até **R$ 117,8 milhões** (7,7% do gasto comparável) se as compras acima da mediana pagassem a mediana. Dez grupos concentram 49% disso, cinco deles de alimentos |
| 5 | Materiais fracassam mais que serviços | **14,2%** dos itens de material licitados por menor preço terminam desertos ou fracassados, contra 6,8% nos serviços |

## Recomendações

1. **Concentrar controle e negociação na classe A.** São 546 itens de catálogo. Acompanhar preço de perto nesses itens cobre 80% do gasto comum.
2. **Avaliar compra conjunta ou ata de registro de preços para alimentos** (fruta, ovo, carne de ave, carne bovina, legume), que somam muitas compras, muitos órgãos e variação de preço relevante.
3. **Corrigir o cadastro antes de comparar preços em escala.** Categoria, unidade de medida e estimativa de preço têm problemas que hoje limitam qualquer análise (ver Qualidade dos dados).

A economia potencial é um **teto para investigação**, não um valor garantido: o mesmo código de catálogo pode reunir marcas e embalagens diferentes.

## Como foi feito

| Etapa | Ferramenta | Arquivo |
|---|---|---|
| Download paginado da API, com retomada | Python (biblioteca padrão) | `baixar_pncp.py` |
| Redução de colunas e mascaramento de CPF | Python (biblioteca padrão) | `preparar_envio.py` |
| Carga no SQLite e anonimização de fornecedores | Python (biblioteca padrão) | `carregar_sqlite.py` |
| Limpeza: duplicados, tipos, segmentos | SQL | `sql/01_limpeza.sql` |
| Análises: ABC, variação de preço, insucesso, qualidade | SQL (CTEs e funções de janela) | `sql/02_analises.sql` |
| Indicadores, tabela dinâmica e gráficos | Excel | `resumo_compras_2025-03.xlsx` |

Decisões de método:

- **Duplicados:** fica a versão mais recente de cada item (14.143 linhas removidas de 208.584).
- **Gasto:** valor total homologado, só itens com situação "Homologado" e valor maior que zero (152.767 itens).
- **Segmento Mega:** itens de R$ 100 milhões ou mais são analisados à parte, para não distorcer médias e a curva ABC.
- **Curva ABC:** por código de catálogo, A até 80% do gasto acumulado, B até 95%, C o restante.
- **Variação de preço:** mesmo código de catálogo e mesma unidade de medida, 5 ou mais órgãos, quartis de preço unitário.
- **Economia potencial:** diferença para a mediana nas compras com preço entre a mediana e 3 vezes a mediana. Preços acima de 3 vezes ou abaixo de um terço da mediana ficam fora, por serem provável erro de cadastro ou produto diferente.

## Qualidade dos dados

Parte do trabalho foi auditar a base. O que encontrei:

- A coluna de categoria traz "Informática (TIC)" em **100%** dos itens, inclusive óleo diesel e alimentos. Foi descartada.
- **6,8%** das linhas baixadas eram duplicadas, efeito da paginação da API.
- Cerca de **3,9%** dos itens podem estar ausentes (lacunas na numeração dos itens de 499 compras).
- A unidade de medida tem mais de **1.500 grafias** distintas.
- **20%** dos itens homologados com estimativa pública têm preço mais de 50% abaixo do estimado, com totais estimados irreais, o que indica estimativas pouco confiáveis.
- Há preços unitários claramente errados, como óleo diesel a R$ 2,6 milhões o litro.

## Limitações

- Um único mês de inclusão (março de 2025). Não há análise de sazonalidade.
- Os valores dos 36 itens Mega não foram conferidos um a um e podem ser tetos de contrato.
- A comparação de preços não controla marca, embalagem, frete nem região.
- Itens ainda "Em andamento" não têm resultado e ficam fora do gasto.

## Como reproduzir

Requer Python 3 e, só para gerar o Excel, `pip install openpyxl`.

```bash
# 1. Baixar os itens (copie a Request URL do Swagger da API, com as datas desejadas)
python baixar_pncp.py --url "URL_DO_ENDPOINT_2" --saida itens_2025-03.csv

# 2. Reduzir colunas e mascarar CPF em nomes
python preparar_envio.py --entrada itens_2025-03.csv --saida itens_2025-03_reduzido.csv

# 3. Criar o banco e executar o SQL de limpeza e de análise
python carregar_sqlite.py --entrada itens_2025-03_reduzido.csv --banco compras.db

# 4. (opcional) Regenerar a planilha de resumo
python gerar_excel.py --banco compras.db --saida resumo.xlsx
```

Os dados brutos e o banco não estão no repositório (tamanho e dados pessoais). O resultado pode variar um pouco, porque a base do PNCP é atualizada continuamente.

## Fonte dos dados e privacidade

- **Fonte:** API de Dados Abertos do Compras.gov.br, módulo de contratações (Lei 14.133/2021), endpoint `2_consultarItensContratacoes_PNCP_14133`. Disponível em https://dadosabertos.compras.gov.br/swagger-ui/index.html. Download em 11/11/2026.
- **Privacidade:** nomes e CNPJ de fornecedores não são publicados. No banco, cada fornecedor vira um código anônimo. Alguns microempreendedores aparecem na fonte com o CPF no nome, e esses registros foram mascarados antes de qualquer análise.
- Este é um projeto de estudo, sem vínculo com o governo federal. As conclusões são do autor.

## Autor

Fernando Pinheiro dos Santos, [linkedin.com/in/fernando-pinheiro-dados](https://www.linkedin.com/in/fernando-pinheiro-dados)
