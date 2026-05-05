-- Schema EnviaDados — PostgreSQL
-- Execute: psql -d enviadados -f schema.sql

CREATE TABLE IF NOT EXISTS saidas (
    id_saida          TEXT        PRIMARY KEY,
    id_produto        TEXT,
    codigo            TEXT,
    descricao         TEXT,
    numero_cupom      TEXT,
    nota_fiscal       TEXT,
    data_venda        TIMESTAMP,
    quantidade_vendida NUMERIC(15,3),
    preco_venda       NUMERIC(15,2),
    sub_total         NUMERIC(15,2),
    desconto          NUMERIC(15,2),
    id_cliente        TEXT,
    id_vendedor       TEXT,
    id_plano          TEXT,
    id_loja           INTEGER,
    operacao          TEXT,
    data_manutencao   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saidas_data_venda    ON saidas (data_venda);
CREATE INDEX IF NOT EXISTS idx_saidas_operacao      ON saidas (operacao);
CREATE INDEX IF NOT EXISTS idx_saidas_id_produto    ON saidas (id_produto);
CREATE INDEX IF NOT EXISTS idx_saidas_id_loja       ON saidas (id_loja);

CREATE TABLE IF NOT EXISTS produtos (
    id_produto      TEXT        PRIMARY KEY,
    codigo          TEXT,
    descricao       TEXT,
    unidade         TEXT,
    preco           NUMERIC(15,2),
    custo_medio     NUMERIC(15,2),
    est_minimo      NUMERIC(15,3),
    id_grupo        INTEGER,
    grupo           TEXT,
    id_fornecedor   TEXT,
    ativo           TEXT,
    ultima_venda    DATE,
    data_atualizacao TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_produtos_id_grupo ON produtos (id_grupo);

CREATE TABLE IF NOT EXISTS estoque (
    id_estoque      TEXT        PRIMARY KEY,
    id_produto      TEXT,
    cod_produto     TEXT,
    id_loja         INTEGER,
    estoque         NUMERIC(15,3),
    data_atualizacao TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_estoque_id_produto ON estoque (id_produto);
CREATE INDEX IF NOT EXISTS idx_estoque_id_loja    ON estoque (id_loja);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      TEXT        PRIMARY KEY,
    cliente         TEXT,
    cgc_cpf         TEXT,
    telefone        TEXT,
    celular         TEXT,
    whatsapp        TEXT,
    email           TEXT,
    cidade          TEXT,
    uf              TEXT,
    ativo           TEXT,
    ultima_compra   DATE,
    cadastro        DATE,
    data_atualizacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vendedores (
    id_vendedor     TEXT        PRIMARY KEY,
    nome            TEXT,
    apelido         TEXT,
    funcao          TEXT,
    ativo           TEXT,
    meta            NUMERIC(15,2),
    email           TEXT,
    celular         TEXT,
    id_loja         INTEGER,
    data_atualizacao TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id_fornecedor   TEXT        PRIMARY KEY,
    razao_soc       TEXT,
    nome_fanta      TEXT,
    cnpj            TEXT,
    cidade          TEXT,
    uf              TEXT,
    telefone        TEXT,
    email           TEXT,
    whatsapp        TEXT
);

CREATE TABLE IF NOT EXISTS caixa (
    id_caixa        TEXT        PRIMARY KEY,
    data            DATE,
    valor           NUMERIC(15,2),
    historico       TEXT,
    nat             TEXT,
    natureza        TEXT,
    id_conta        TEXT,
    conta           TEXT,
    id_cliente      TEXT,
    id_vendedor     TEXT,
    id_loja         INTEGER,
    baixado         TEXT,
    bx              TEXT,
    data_baixa      DATE
);

CREATE INDEX IF NOT EXISTS idx_caixa_data ON caixa (data);

CREATE TABLE IF NOT EXISTS contas_receber (
    id_fatura       TEXT,
    numero          TEXT,
    parcela         INTEGER,
    emissao         DATE,
    vencimento      DATE,
    valor_parcela   NUMERIC(15,2),
    valor_total     NUMERIC(15,2),
    recebido        NUMERIC(15,2),
    juros           NUMERIC(15,2),
    desconto        NUMERIC(15,2),
    id_cliente      TEXT,
    id_vendedor     TEXT,
    loja            INTEGER,
    bx              TEXT,
    situacao        TEXT,
    data_receb      DATE,
    data_atualizacao TIMESTAMP,
    PRIMARY KEY (id_fatura, parcela)
);

CREATE TABLE IF NOT EXISTS contas_pagar (
    id_fatura       TEXT,
    numero          TEXT,
    parcela         INTEGER,
    emissao         DATE,
    vencimento      DATE,
    valor_parcela   NUMERIC(15,2),
    valor_total     NUMERIC(15,2),
    recebido        NUMERIC(15,2),
    juros           NUMERIC(15,2),
    desconto        NUMERIC(15,2),
    id_cliente      TEXT,
    id_vendedor     TEXT,
    loja            INTEGER,
    bx              TEXT,
    situacao        TEXT,
    data_receb      DATE,
    data_atualizacao TIMESTAMP,
    PRIMARY KEY (id_fatura, parcela)
);

-- Plano de venda (forma de pagamento)
-- Populado via sync do Firebird ou manualmente
CREATE TABLE IF NOT EXISTS plano_venda (
    id_plano    TEXT        PRIMARY KEY,
    descricao   TEXT
);
