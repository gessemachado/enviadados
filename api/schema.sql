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
    data_manutencao   TIMESTAMP,
    id_tenant         INTEGER
);

CREATE INDEX IF NOT EXISTS idx_saidas_data_venda    ON saidas (data_venda);
CREATE INDEX IF NOT EXISTS idx_saidas_operacao      ON saidas (operacao);
CREATE INDEX IF NOT EXISTS idx_saidas_id_produto    ON saidas (id_produto);
CREATE INDEX IF NOT EXISTS idx_saidas_id_loja       ON saidas (id_loja);
CREATE INDEX IF NOT EXISTS idx_saidas_id_tenant     ON saidas (id_tenant);

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
    data_atualizacao TIMESTAMP,
    id_tenant       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_produtos_id_grupo   ON produtos (id_grupo);
CREATE INDEX IF NOT EXISTS idx_produtos_id_tenant  ON produtos (id_tenant);

CREATE TABLE IF NOT EXISTS estoque (
    id_estoque      TEXT        PRIMARY KEY,
    id_produto      TEXT,
    cod_produto     TEXT,
    id_loja         INTEGER,
    estoque         NUMERIC(15,3),
    data_atualizacao TIMESTAMP,
    id_tenant       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_estoque_id_produto ON estoque (id_produto);
CREATE INDEX IF NOT EXISTS idx_estoque_id_loja    ON estoque (id_loja);
CREATE INDEX IF NOT EXISTS idx_estoque_id_tenant  ON estoque (id_tenant);

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
    data_atualizacao TIMESTAMP,
    id_tenant       INTEGER
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
    data_atualizacao TIMESTAMP,
    id_tenant       INTEGER
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
    whatsapp        TEXT,
    id_tenant       INTEGER
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
    data_baixa      DATE,
    id_tenant       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_caixa_data      ON caixa (data);
CREATE INDEX IF NOT EXISTS idx_caixa_id_tenant ON caixa (id_tenant);

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
    id_tenant       INTEGER,
    PRIMARY KEY (id_fatura, parcela)
);

CREATE INDEX IF NOT EXISTS idx_contas_receber_id_tenant ON contas_receber (id_tenant);

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
    id_tenant       INTEGER,
    PRIMARY KEY (id_fatura, parcela)
);

CREATE INDEX IF NOT EXISTS idx_contas_pagar_id_tenant ON contas_pagar (id_tenant);

-- Plano de venda (forma de pagamento)
-- Populado via sync do Firebird ou manualmente
CREATE TABLE IF NOT EXISTS plano_venda (
    id_plano    TEXT        PRIMARY KEY,
    descricao   TEXT,
    id_tenant   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_plano_venda_id_tenant ON plano_venda (id_tenant);

-- ── Multi-loja / Multi-tenant ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS lojas (
    id_loja     SERIAL      PRIMARY KEY,
    nome        TEXT        NOT NULL,
    cnpj        TEXT,
    id_tenant   INTEGER,
    ativo       BOOLEAN     DEFAULT TRUE,
    criado_em   TIMESTAMP   DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario  SERIAL      PRIMARY KEY,
    nome        TEXT        NOT NULL,
    email       TEXT        UNIQUE NOT NULL,
    senha_hash  TEXT        NOT NULL,
    id_loja     INTEGER,            -- NULL = admin (acessa todas as lojas)
    admin       BOOLEAN     DEFAULT FALSE,
    ativo       BOOLEAN     DEFAULT TRUE,
    criado_em   TIMESTAMP   DEFAULT NOW()
);

-- Admin inicial (mesma senha já usada no sistema)
INSERT INTO usuarios (nome, email, senha_hash, admin)
VALUES ('Admin', 'gesseinvest@gmail.com',
        '33fa1b511447a982a4e7827bc6ab6a8d41173da2c039b394836e9385c501a93d', TRUE)
ON CONFLICT (email) DO NOTHING;

-- ── Migração: adicionar id_tenant às tabelas existentes ───────────────────────
-- Seguro executar múltiplas vezes (ADD COLUMN IF NOT EXISTS)

-- ── Migração: adicionar PB (peso bruto) à tabela produtos ────────────────────
ALTER TABLE produtos        ADD COLUMN IF NOT EXISTS pb NUMERIC(15,3);

ALTER TABLE saidas          ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE estoque         ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE produtos        ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE clientes        ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE vendedores      ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE fornecedores    ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE caixa           ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE contas_receber  ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE contas_pagar    ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE plano_venda     ADD COLUMN IF NOT EXISTS id_tenant INTEGER;
ALTER TABLE lojas           ADD COLUMN IF NOT EXISTS id_tenant INTEGER;

CREATE INDEX IF NOT EXISTS idx_saidas_id_tenant         ON saidas (id_tenant);
CREATE INDEX IF NOT EXISTS idx_estoque_id_tenant        ON estoque (id_tenant);
CREATE INDEX IF NOT EXISTS idx_produtos_id_tenant       ON produtos (id_tenant);
CREATE INDEX IF NOT EXISTS idx_vendedores_id_tenant     ON vendedores (id_tenant);
CREATE INDEX IF NOT EXISTS idx_caixa_id_tenant          ON caixa (id_tenant);
CREATE INDEX IF NOT EXISTS idx_contas_receber_id_tenant ON contas_receber (id_tenant);
CREATE INDEX IF NOT EXISTS idx_contas_pagar_id_tenant   ON contas_pagar (id_tenant);
CREATE INDEX IF NOT EXISTS idx_plano_venda_id_tenant    ON plano_venda (id_tenant);

-- ── Migração: valor de despesa administrativa por item de venda (DRE) ───────
ALTER TABLE produtos DROP COLUMN IF EXISTS val_desp_adm;
ALTER TABLE saidas   ADD COLUMN IF NOT EXISTS val_desp_adm NUMERIC(15,2);

-- ── Migração: impostos por item de venda (DRE) ───────────────────────────────
ALTER TABLE saidas ADD COLUMN IF NOT EXISTS val_enc_fed NUMERIC(15,2);
ALTER TABLE saidas ADD COLUMN IF NOT EXISTS val_icms_recolher NUMERIC(15,2);

-- ── Migração: custo total por item de venda (DRE) ────────────────────────────
ALTER TABLE saidas ADD COLUMN IF NOT EXISTS custo_total NUMERIC(15,2);

-- ── Marketing WhatsApp (Gupshup) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gupshup_envios (
    id              SERIAL      PRIMARY KEY,
    id_tenant       INTEGER,
    id_usuario      INTEGER,
    id_cliente      TEXT,
    destino         TEXT        NOT NULL,
    appname         TEXT,
    source          TEXT,
    template_id     TEXT,
    template_nome   TEXT,
    params          JSONB,
    status          TEXT,
    http_status     INTEGER,
    message_id      TEXT,
    response_body   TEXT,
    lote_id         TEXT,
    enviado_em      TIMESTAMP   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gupshup_envios_tenant  ON gupshup_envios (id_tenant);
CREATE INDEX IF NOT EXISTS idx_gupshup_envios_data    ON gupshup_envios (enviado_em);
CREATE INDEX IF NOT EXISTS idx_gupshup_envios_lote    ON gupshup_envios (lote_id);
CREATE INDEX IF NOT EXISTS idx_gupshup_envios_cliente ON gupshup_envios (id_cliente);

-- ── Webhook Gupshup: status de entrega/leitura por mensagem ──────────────────
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS sent_at      TIMESTAMP;
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP;
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS read_at      TIMESTAMP;
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS failed_at    TIMESTAMP;
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS error_code   TEXT;
ALTER TABLE gupshup_envios ADD COLUMN IF NOT EXISTS error_reason TEXT;
CREATE INDEX IF NOT EXISTS idx_gupshup_envios_msgid   ON gupshup_envios (message_id);

-- ── Marketing WhatsApp (Z-API) ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zapi_envios (
    id            SERIAL      PRIMARY KEY,
    id_tenant     INTEGER,
    id_usuario    INTEGER,
    id_cliente    TEXT,
    destino       TEXT        NOT NULL,
    mensagem      TEXT,
    status        TEXT,
    resultado     TEXT,
    lote_id       TEXT,
    enviado_em    TIMESTAMP   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zapi_envios_tenant  ON zapi_envios (id_tenant);
CREATE INDEX IF NOT EXISTS idx_zapi_envios_data    ON zapi_envios (enviado_em);
CREATE INDEX IF NOT EXISTS idx_zapi_envios_lote    ON zapi_envios (lote_id);
CREATE INDEX IF NOT EXISTS idx_zapi_envios_cliente ON zapi_envios (id_cliente);

-- ── Opt-in do cliente (LGPD / política Meta) ─────────────────────────────────
-- Rastro de auditoria de quem consentiu receber WhatsApp da loja, quando e como.
-- A Meta pode auditar isso; sem opt-in registrado, campanhas podem ser bloqueadas.
CREATE TABLE IF NOT EXISTS cliente_optin (
    id             SERIAL     PRIMARY KEY,
    id_tenant      INTEGER    NOT NULL,
    id_cliente     TEXT,
    telefone       TEXT       NOT NULL,
    canal          TEXT       DEFAULT 'whatsapp',
    texto          TEXT,              -- o que o cliente aceitou (ex: "aceito receber promoções")
    origem         TEXT,              -- form_web, cadastro_loja, importacao, manual
    ativo          BOOLEAN    DEFAULT TRUE,
    data_optin     TIMESTAMP  DEFAULT NOW(),
    data_optout    TIMESTAMP,
    id_usuario     INTEGER,           -- usuário que registrou (se manual)
    observacao     TEXT
);

CREATE INDEX IF NOT EXISTS idx_optin_tenant   ON cliente_optin (id_tenant);
CREATE INDEX IF NOT EXISTS idx_optin_telefone ON cliente_optin (telefone);
CREATE INDEX IF NOT EXISTS idx_optin_cliente  ON cliente_optin (id_cliente);
CREATE UNIQUE INDEX IF NOT EXISTS uq_optin_tenant_tel_ativo
    ON cliente_optin (id_tenant, telefone) WHERE ativo = TRUE;
