/* =========================================================
   DB: MES_Core  (SQL Server 2022)
   ========================================================= */

IF DB_ID(N'MES_Core') IS NULL
BEGIN
    CREATE DATABASE [MES_Core];
END
GO

USE [MES_Core];
GO

CREATE TABLE dbo.tb_linha_producao (
    id_linha_producao INT IDENTITY(1,1) NOT NULL,
    tx_name           NVARCHAR(120)     NOT NULL,
    CONSTRAINT PK_tb_linha_producao PRIMARY KEY CLUSTERED (id_linha_producao),
    CONSTRAINT UQ_tb_linha_producao_tx_name UNIQUE (tx_name)
);
GO

CREATE TABLE dbo.tb_ihm (
    id_ihm           INT IDENTITY(1,1) NOT NULL,
    tx_ip_address    VARCHAR(45)       NOT NULL,
    tx_port_number   VARCHAR(45)       NOT NULL,
    id_linha_producao INT              NOT NULL,
    tx_name          NVARCHAR(120)     NOT NULL,
    CONSTRAINT PK_tb_ihm PRIMARY KEY CLUSTERED (id_ihm),
    CONSTRAINT FK_tb_ihm_linha FOREIGN KEY (id_linha_producao)
        REFERENCES dbo.tb_linha_producao (id_linha_producao),
    CONSTRAINT CK_tb_ihm_port CHECK (tx_port_number BETWEEN 1 AND 65535),
    CONSTRAINT UQ_tb_ihm_ip_port UNIQUE (tx_ip_address, tx_port_number),
    CONSTRAINT UQ_tb_ihm_tx_name UNIQUE (tx_name)
);
GO

CREATE TABLE dbo.tb_registrador (
    id_registrador INT IDENTITY(1,1) NOT NULL,
    nu_endereco    INT               NOT NULL,
    tx_descricao   NVARCHAR(255)     NULL,
    id_ihm         INT               NOT NULL,
    CONSTRAINT PK_tb_registrador PRIMARY KEY CLUSTERED (id_registrador),
    CONSTRAINT FK_tb_registrador_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm)
);
GO

CREATE TABLE dbo.tb_log_registrador (
    id_log_registrador BIGINT IDENTITY(1,1) NOT NULL,
    id_ihm             INT                 NOT NULL,
    id_registrador     INT                 NOT NULL,
    nu_valor_bruto     DECIMAL(18,4)       NOT NULL,
    dt_created_at      DATETIME2(0)        NOT NULL
        CONSTRAINT DF_tb_log_registrador_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_tb_log_registrador PRIMARY KEY CLUSTERED (id_log_registrador),
    CONSTRAINT FK_tb_log_registrador_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT FK_tb_log_registrador_registrador FOREIGN KEY (id_registrador)
        REFERENCES dbo.tb_registrador (id_registrador)
);
GO

CREATE INDEX IX_tb_log_registrador_dt_created_at
    ON dbo.tb_log_registrador (dt_created_at);
GO

CREATE INDEX IX_tb_log_registrador_ihm_registrador_dt
    ON dbo.tb_log_registrador (id_ihm, id_registrador, dt_created_at DESC);
GO

CREATE TABLE dbo.tb_users (
    id_users        INT IDENTITY(1,1) NOT NULL,
    tx_name         NVARCHAR(120)     NOT NULL,
    tx_password     NVARCHAR(255)     NOT NULL,
    tx_role         NVARCHAR(50)      NOT NULL,
    dt_created_at   DATETIME2(0)      NOT NULL
        CONSTRAINT DF_tb_users_created DEFAULT (SYSUTCDATETIME()),
    dt_modified_at  DATETIME2(0)      NULL,
    CONSTRAINT PK_tb_users PRIMARY KEY CLUSTERED (id_users),
    CONSTRAINT UQ_tb_users_tx_name UNIQUE (tx_name)
);
GO

CREATE TABLE dbo.tb_log_portal (
    id_log_portal  BIGINT IDENTITY(1,1) NOT NULL,
    id_users       INT                 NOT NULL,
    tx_description NVARCHAR(500)       NOT NULL,
    dt_created_at  DATETIME2(0)        NOT NULL
        CONSTRAINT DF_tb_log_portal_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_tb_log_portal PRIMARY KEY CLUSTERED (id_log_portal),
    CONSTRAINT FK_tb_log_portal_users FOREIGN KEY (id_users)
        REFERENCES dbo.tb_users (id_users)
);
GO

CREATE INDEX IX_tb_log_portal_users_dt
    ON dbo.tb_log_portal (id_users, dt_created_at DESC);
GO

CREATE TABLE dbo.tb_turnos (
    id_turno        INT IDENTITY(1,1) NOT NULL,
    tx_name         NVARCHAR(120)     NOT NULL,
    dt_inicio       DATETIME2(0)           NOT NULL,
    dt_fim          DATETIME2(0)           NOT NULL,
    id_linha_producao INT             NOT NULL,
    bl_ativo        BIT               NOT NULL
        CONSTRAINT DF_tb_turnos_ativo DEFAULT (1),
    dt_created_at   DATETIME2(0)      NOT NULL
        CONSTRAINT DF_tb_turnos_created DEFAULT (SYSUTCDATETIME()),
    dt_modified_at  DATETIME2(0)      NULL,
    CONSTRAINT PK_tb_turnos PRIMARY KEY CLUSTERED (id_turno),
    CONSTRAINT FK_tb_turnos_linha FOREIGN KEY (id_linha_producao)
        REFERENCES dbo.tb_linha_producao (id_linha_producao)
);
GO

CREATE INDEX IX_tb_turnos_linha_ativo
    ON dbo.tb_turnos (id_linha_producao, bl_ativo);
GO

CREATE TABLE dbo.tb_ftp_needed (
    id_ftp_needed   INT IDENTITY(1,1)   NOT NULL,
    id_ihm          INT                 NOT NULL,
    bl_needed       BIT                 NOT NULL,
    CONSTRAINT PK_tb_ftp_needed PRIMARY KEY CLUSTERED (id_ftp_needed),
    CONSTRAINT FK_tb_ftp_needed_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm)
);
GO

CREATE TABLE dbo.tb_peca (
    id_peca          INT IDENTITY(1,1) NOT NULL,
    tx_name          NVARCHAR(120)     NOT NULL,
    tempo_producao   INT               NOT NULL,
    CONSTRAINT PK_tb_peca PRIMARY KEY CLUSTERED (id_peca),
    CONSTRAINT UQ_tb_peca_tx_name UNIQUE (tx_name),
    CONSTRAINT CK_tb_peca_tempo CHECK (tempo_producao >= 0)
);
GO

CREATE TABLE dbo.tb_depara_operador (
    id_depara_operador INT IDENTITY(1,1) NOT NULL,
    nu_cod_operador    INT               NOT NULL,
    tx_operador        NVARCHAR(120)     NOT NULL,
    id_ihm             INT               NOT NULL,
    CONSTRAINT PK_tb_depara_operador PRIMARY KEY CLUSTERED (id_depara_operador),
    CONSTRAINT FK_tb_depara_operador_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_operador UNIQUE (id_ihm, nu_cod_operador)
);
GO

CREATE TABLE dbo.tb_depara_engenheiro (
    id_depara_engenheiro INT IDENTITY(1,1) NOT NULL,
    nu_cod_engenheiro    INT               NOT NULL,
    tx_engenheiro        NVARCHAR(120)     NOT NULL,
    id_ihm               INT               NOT NULL,
    CONSTRAINT PK_tb_depara_engenheiro PRIMARY KEY CLUSTERED (id_depara_engenheiro),
    CONSTRAINT FK_tb_depara_engenheiro_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_engenheiro UNIQUE (id_ihm, nu_cod_engenheiro)
);
GO

CREATE TABLE dbo.tb_depara_manutentor (
    id_depara_manutentor INT IDENTITY(1,1) NOT NULL,
    nu_cod_manutentor    INT               NOT NULL,
    tx_manutentor        NVARCHAR(120)     NOT NULL,
    id_ihm               INT               NOT NULL,
    CONSTRAINT PK_tb_depara_manutentor PRIMARY KEY CLUSTERED (id_depara_manutentor),
    CONSTRAINT FK_tb_depara_manutentor_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_manutentor UNIQUE (id_ihm, nu_cod_manutentor)
);
GO

CREATE TABLE dbo.tb_depara_motivo_parada (
    id_depara_motivo_parada INT IDENTITY(1,1) NOT NULL,
    nu_cod_motivo_parada    INT               NOT NULL,
    tx_motivo_parada        NVARCHAR(200)     NOT NULL,
    id_ihm                  INT               NOT NULL,
    CONSTRAINT PK_tb_depara_motivo_parada PRIMARY KEY CLUSTERED (id_depara_motivo_parada),
    CONSTRAINT FK_tb_depara_motivo_parada_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_motivo_parada UNIQUE (id_ihm, nu_cod_motivo_parada)
);
GO

CREATE TABLE dbo.tb_depara_justificativa (
    id_depara_justificativa INT IDENTITY(1,1) NOT NULL,
    nu_cod_justificativa    INT               NOT NULL,
    tx_justificativa        NVARCHAR(200)     NOT NULL,
    id_ihm                  INT               NOT NULL,
    CONSTRAINT PK_tb_depara_justificativa PRIMARY KEY CLUSTERED (id_depara_justificativa),
    CONSTRAINT FK_tb_depara_justificativa_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_justificativa UNIQUE (id_ihm, nu_cod_justificativa)
);
GO

CREATE TABLE dbo.tb_depara_peca (
    id_depara_peca INT IDENTITY(1,1) NOT NULL,
    nu_cod_peca    INT               NOT NULL,
    tx_peca        NVARCHAR(120)     NOT NULL,
    id_ihm         INT               NOT NULL,
    CONSTRAINT PK_tb_depara_peca PRIMARY KEY CLUSTERED (id_depara_peca),
    CONSTRAINT FK_tb_depara_peca_ihm FOREIGN KEY (id_ihm)
        REFERENCES dbo.tb_ihm (id_ihm),
    CONSTRAINT UQ_tb_depara_peca UNIQUE (id_ihm, nu_cod_peca)
);
GO

/* =========================================================
   POPULANDO TABELAS - DADOS GENÉRICOS
   Baseado nos mocks de queries.py
   ========================================================= */

USE MES_Core;
GO

-- -------------------------------------------------------
-- Linhas de produção
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_linha_producao ON;

INSERT INTO dbo.tb_linha_producao (id_linha_producao, tx_name) VALUES
(1, N'LINHA_505'),
(2, N'LINHA_504');

SET IDENTITY_INSERT dbo.tb_linha_producao OFF;
GO

-- -------------------------------------------------------
-- IHMs (máquinas)
-- Linha 1 (LINHA_505): ids 1-6
-- Linha 2 (LINHA_504): ids 7-12
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_ihm ON;

INSERT INTO dbo.tb_ihm (id_ihm, tx_ip_address, tx_port_number, id_linha_producao, tx_name) VALUES
(1,  '192.168.1.1',  '502', 1, N'CUSI_02'),
(2,  '192.168.1.2',  '502', 1, N'MAQ_24'),
(3,  '192.168.1.3',  '502', 1, N'MAQ_26'),
(4,  '192.168.1.4',  '502', 1, N'TORNO_05'),
(5,  '192.168.1.5',  '502', 1, N'RET_08'),
(6,  '192.168.1.6',  '502', 1, N'ROBO_12'),
(7,  '192.168.1.7',  '502', 2, N'PMAQ_37'),
(8,  '192.168.1.8',  '502', 2, N'MAQ_10'),
(9,  '192.168.1.9',  '502', 2, N'MAQ_08'),
(10, '192.168.1.10', '502', 2, N'MAQ_37'),
(11, '192.168.1.11', '502', 2, N'MAQ_28'),
(12, '192.168.1.12', '502', 2, N'MAQ_59');

SET IDENTITY_INSERT dbo.tb_ihm OFF;
GO

-- -------------------------------------------------------
-- FTP
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_ftp_needed ON;

INSERT INTO dbo.tb_ftp_needed (id_ftp_needed, id_ihm, bl_needed) VALUES
(1,  1,  1), (2,  2,  1), (3,  3,  1), (4,  4,  1),
(5,  5,  1), (6,  6,  1), (7,  7,  1), (8,  8,  1),
(9,  9,  1), (10, 10, 1), (11, 11, 1), (12, 12, 0);

SET IDENTITY_INSERT dbo.tb_ftp_needed OFF;
GO

-- -------------------------------------------------------
-- Registradores (10 por IHM)
-- id = (id_ihm - 1) * 10 + offset
--  1=operador  2=status_maquina  3=motivo_parada
--  4=produzido 5=reprovado       6=total_produzido
--  7=manutentor 8=engenheiro     9=meta  10=modelo_peça
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_registrador ON;

INSERT INTO dbo.tb_registrador (id_registrador, nu_endereco, tx_descricao, id_ihm) VALUES
-- IHM 1 – CUSI_02
(1,  0,   N'operador',        1), (2,  100, N'status_maquina',  1),
(3,  101, N'motivo_parada',   1), (4,  200, N'produzido',       1),
(5,  201, N'reprovado',       1), (6,  202, N'total_produzido', 1),
(7,  300, N'manutentor',      1), (8,  301, N'engenheiro',      1),
(9,  400, N'meta',            1), (10, 401, N'modelo_peça',     1),
-- IHM 2 – MAQ_24
(11, 0,   N'operador',        2), (12, 100, N'status_maquina',  2),
(13, 101, N'motivo_parada',   2), (14, 200, N'produzido',       2),
(15, 201, N'reprovado',       2), (16, 202, N'total_produzido', 2),
(17, 300, N'manutentor',      2), (18, 301, N'engenheiro',      2),
(19, 400, N'meta',            2), (20, 401, N'modelo_peça',     2),
-- IHM 3 – MAQ_26
(21, 0,   N'operador',        3), (22, 100, N'status_maquina',  3),
(23, 101, N'motivo_parada',   3), (24, 200, N'produzido',       3),
(25, 201, N'reprovado',       3), (26, 202, N'total_produzido', 3),
(27, 300, N'manutentor',      3), (28, 301, N'engenheiro',      3),
(29, 400, N'meta',            3), (30, 401, N'modelo_peça',     3),
-- IHM 4 – TORNO_05
(31, 0,   N'operador',        4), (32, 100, N'status_maquina',  4),
(33, 101, N'motivo_parada',   4), (34, 200, N'produzido',       4),
(35, 201, N'reprovado',       4), (36, 202, N'total_produzido', 4),
(37, 300, N'manutentor',      4), (38, 301, N'engenheiro',      4),
(39, 400, N'meta',            4), (40, 401, N'modelo_peça',     4),
-- IHM 5 – RET_08
(41, 0,   N'operador',        5), (42, 100, N'status_maquina',  5),
(43, 101, N'motivo_parada',   5), (44, 200, N'produzido',       5),
(45, 201, N'reprovado',       5), (46, 202, N'total_produzido', 5),
(47, 300, N'manutentor',      5), (48, 301, N'engenheiro',      5),
(49, 400, N'meta',            5), (50, 401, N'modelo_peça',     5),
-- IHM 6 – ROBO_12
(51, 0,   N'operador',        6), (52, 100, N'status_maquina',  6),
(53, 101, N'motivo_parada',   6), (54, 200, N'produzido',       6),
(55, 201, N'reprovado',       6), (56, 202, N'total_produzido', 6),
(57, 300, N'manutentor',      6), (58, 301, N'engenheiro',      6),
(59, 400, N'meta',            6), (60, 401, N'modelo_peça',     6),
-- IHM 7 – PMAQ_37
(61, 0,   N'operador',        7), (62, 100, N'status_maquina',  7),
(63, 101, N'motivo_parada',   7), (64, 200, N'produzido',       7),
(65, 201, N'reprovado',       7), (66, 202, N'total_produzido', 7),
(67, 300, N'manutentor',      7), (68, 301, N'engenheiro',      7),
(69, 400, N'meta',            7), (70, 401, N'modelo_peça',     7),
-- IHM 8 – MAQ_10
(71, 0,   N'operador',        8), (72, 100, N'status_maquina',  8),
(73, 101, N'motivo_parada',   8), (74, 200, N'produzido',       8),
(75, 201, N'reprovado',       8), (76, 202, N'total_produzido', 8),
(77, 300, N'manutentor',      8), (78, 301, N'engenheiro',      8),
(79, 400, N'meta',            8), (80, 401, N'modelo_peça',     8),
-- IHM 9 – MAQ_08
(81, 0,   N'operador',        9), (82, 100, N'status_maquina',  9),
(83, 101, N'motivo_parada',   9), (84, 200, N'produzido',       9),
(85, 201, N'reprovado',       9), (86, 202, N'total_produzido', 9),
(87, 300, N'manutentor',      9), (88, 301, N'engenheiro',      9),
(89, 400, N'meta',            9), (90, 401, N'modelo_peça',     9),
-- IHM 10 – MAQ_37
(91,  0,   N'operador',        10), (92,  100, N'status_maquina',  10),
(93,  101, N'motivo_parada',   10), (94,  200, N'produzido',       10),
(95,  201, N'reprovado',       10), (96,  202, N'total_produzido', 10),
(97,  300, N'manutentor',      10), (98,  301, N'engenheiro',      10),
(99,  400, N'meta',            10), (100, 401, N'modelo_peça',     10),
-- IHM 11 – MAQ_28
(101, 0,   N'operador',        11), (102, 100, N'status_maquina',  11),
(103, 101, N'motivo_parada',   11), (104, 200, N'produzido',       11),
(105, 201, N'reprovado',       11), (106, 202, N'total_produzido', 11),
(107, 300, N'manutentor',      11), (108, 301, N'engenheiro',      11),
(109, 400, N'meta',            11), (110, 401, N'modelo_peça',     11),
-- IHM 12 – MAQ_59
(111, 0,   N'operador',        12), (112, 100, N'status_maquina',  12),
(113, 101, N'motivo_parada',   12), (114, 200, N'produzido',       12),
(115, 201, N'reprovado',       12), (116, 202, N'total_produzido', 12),
(117, 300, N'manutentor',      12), (118, 301, N'engenheiro',      12),
(119, 400, N'meta',            12), (120, 401, N'modelo_peça',     12);

SET IDENTITY_INSERT dbo.tb_registrador OFF;
GO

-- -------------------------------------------------------
-- Turnos (T1/T2/T3 para hoje, para as duas linhas)
-- -------------------------------------------------------
INSERT INTO dbo.tb_turnos (tx_name, dt_inicio, dt_fim, id_linha_producao, bl_ativo)
SELECT turno, dt_inicio, dt_fim, linha, 1
FROM (VALUES
    (N'T1', DATEADD(hour,  6, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 14, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 1),
    (N'T2', DATEADD(hour, 14, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 22, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 1),
    (N'T3', DATEADD(hour, 22, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 30, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 1),
    (N'T1', DATEADD(hour,  6, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 14, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 2),
    (N'T2', DATEADD(hour, 14, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 22, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 2),
    (N'T3', DATEADD(hour, 22, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), DATEADD(hour, 30, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0))), 2)
) AS t(turno, dt_inicio, dt_fim, linha);
GO

-- -------------------------------------------------------
-- De-para: peças
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_peca (nu_cod_peca, tx_peca, id_ihm) VALUES
(1, N'Eixo A-12',  1),
(1, N'Base Z',     2),
(1, N'Corpo X-7',  3),
(1, N'Pino B-3',   4),
(1, N'Anel C-7',   5),
(1, N'Suporte L',  6),
(1, N'Tampa D-1',  7),
(1, N'Bloco H-4',  8),
(1, N'Flange E-2', 9),
(1, N'Eixo F-5',   10),
(1, N'Capa G-9',   11),
(1, N'Fuso J-2',   12);
GO

-- -------------------------------------------------------
-- De-para: operadores
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_operador (nu_cod_operador, tx_operador, id_ihm) VALUES
(1, N'Ana S.',     1),
(2, N'João M.',    1),
(1, N'João M.',    2),
(1, N'Carlos R.',  4),
(1, N'Maria L.',   5),
(1, N'Pedro L.',   7),
(1, N'Roberta S.', 9),
(1, N'Pedro L.',   10),
(1, N'Roberta S.', 11);
GO

-- -------------------------------------------------------
-- De-para: manutentores
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_manutentor (nu_cod_manutentor, tx_manutentor, id_ihm) VALUES
(1, N'Marcos T.', 1),
(1, N'Marcos T.', 2),
(1, N'Lucas P.',  7),
(1, N'Lucas P.',  8);
GO

-- -------------------------------------------------------
-- De-para: engenheiros
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_engenheiro (nu_cod_engenheiro, tx_engenheiro, id_ihm) VALUES
(1, N'Dr. Silva',  1),
(1, N'Dr. Silva',  2),
(1, N'Eng. Costa', 7);
GO

-- -------------------------------------------------------
-- De-para: motivos de parada
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_motivo_parada (nu_cod_motivo_parada, tx_motivo_parada, id_ihm) VALUES
(1, N'Aguardando Matéria Prima', 1),
(2, N'Falta de operador',        1),
(3, N'Manutenção Preventiva',    1),
(4, N'Limpeza programada',       1),
(5, N'Troca de ferramental',     1),
(1, N'Aguardando Matéria Prima', 2),
(2, N'Falta de operador',        2),
(1, N'Aguardando Matéria Prima', 7);
GO

-- -------------------------------------------------------
-- Logs de produção (snapshots do turno T1 de hoje)
-- Cada snapshot = uma linha por registrador no mesmo instante
-- status_maquina: 49=Produzindo, 0=Parada, 4=Limpeza
--                 52=Máquina em manutenção
-- -------------------------------------------------------
DECLARE @t0 DATETIME2(0) = DATEADD(hour, 6, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0)));

-- IHM 1 (CUSI_02) – Produzindo, oee~88%
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(1, 1,  1,   @t0),                        (1, 2,  49,  @t0),
(1, 3,  0,   @t0),                        (1, 4,  0,   @t0),
(1, 5,  0,   @t0),                        (1, 6,  0,   @t0),
(1, 7,  0,   @t0),                        (1, 8,  0,   @t0),
(1, 9,  600, @t0),                        (1, 10, 1,   @t0),

(1, 1,  1,   DATEADD(hour, 3, @t0)),      (1, 2,  49,  DATEADD(hour, 3, @t0)),
(1, 3,  0,   DATEADD(hour, 3, @t0)),      (1, 4,  225, DATEADD(hour, 3, @t0)),
(1, 5,  0,   DATEADD(hour, 3, @t0)),      (1, 6,  225, DATEADD(hour, 3, @t0)),
(1, 7,  0,   DATEADD(hour, 3, @t0)),      (1, 8,  0,   DATEADD(hour, 3, @t0)),
(1, 9,  600, DATEADD(hour, 3, @t0)),      (1, 10, 1,   DATEADD(hour, 3, @t0)),

(1, 1,  1,   DATEADD(hour, 7, @t0)),      (1, 2,  49,  DATEADD(hour, 7, @t0)),
(1, 3,  0,   DATEADD(hour, 7, @t0)),      (1, 4,  450, DATEADD(hour, 7, @t0)),
(1, 5,  0,   DATEADD(hour, 7, @t0)),      (1, 6,  450, DATEADD(hour, 7, @t0)),
(1, 7,  0,   DATEADD(hour, 7, @t0)),      (1, 8,  0,   DATEADD(hour, 7, @t0)),
(1, 9,  600, DATEADD(hour, 7, @t0)),      (1, 10, 1,   DATEADD(hour, 7, @t0));

-- IHM 2 (MAQ_24) – Alerta (baixa disponibilidade)
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(2, 11, 1,   @t0),                        (2, 12, 0,   @t0),   -- Parada no início
(2, 13, 2,   @t0),                        (2, 14, 0,   @t0),
(2, 15, 0,   @t0),                        (2, 16, 0,   @t0),
(2, 17, 0,   @t0),                        (2, 18, 0,   @t0),
(2, 19, 600, @t0),                        (2, 20, 1,   @t0),

(2, 11, 1,   DATEADD(hour, 4, @t0)),      (2, 12, 49,  DATEADD(hour, 4, @t0)),
(2, 13, 0,   DATEADD(hour, 4, @t0)),      (2, 14, 0,   DATEADD(hour, 4, @t0)),
(2, 15, 0,   DATEADD(hour, 4, @t0)),      (2, 16, 0,   DATEADD(hour, 4, @t0)),
(2, 17, 0,   DATEADD(hour, 4, @t0)),      (2, 18, 0,   DATEADD(hour, 4, @t0)),
(2, 19, 600, DATEADD(hour, 4, @t0)),      (2, 20, 1,   DATEADD(hour, 4, @t0)),

(2, 11, 1,   DATEADD(hour, 7, @t0)),      (2, 12, 49,  DATEADD(hour, 7, @t0)),
(2, 13, 0,   DATEADD(hour, 7, @t0)),      (2, 14, 1080, DATEADD(hour, 7, @t0)),
(2, 15, 40,  DATEADD(hour, 7, @t0)),      (2, 16, 1120, DATEADD(hour, 7, @t0)),
(2, 17, 0,   DATEADD(hour, 7, @t0)),      (2, 18, 0,   DATEADD(hour, 7, @t0)),
(2, 19, 600, DATEADD(hour, 7, @t0)),      (2, 20, 1,   DATEADD(hour, 7, @t0));

-- IHM 3 (MAQ_26) – Parada (sem operador)
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(3, 21, 0,   @t0),                        (3, 22, 0,   @t0),
(3, 23, 2,   @t0),                        (3, 24, 0,   @t0),
(3, 25, 0,   @t0),                        (3, 26, 0,   @t0),
(3, 27, 0,   @t0),                        (3, 28, 0,   @t0),
(3, 29, 600, @t0),                        (3, 30, 1,   @t0),

(3, 21, 0,   DATEADD(hour, 4, @t0)),      (3, 22, 0,   DATEADD(hour, 4, @t0)),
(3, 23, 2,   DATEADD(hour, 4, @t0)),      (3, 24, 0,   DATEADD(hour, 4, @t0)),
(3, 25, 0,   DATEADD(hour, 4, @t0)),      (3, 26, 0,   DATEADD(hour, 4, @t0)),
(3, 27, 0,   DATEADD(hour, 4, @t0)),      (3, 28, 0,   DATEADD(hour, 4, @t0)),
(3, 29, 600, DATEADD(hour, 4, @t0)),      (3, 30, 1,   DATEADD(hour, 4, @t0)),

(3, 21, 0,   DATEADD(hour, 7, @t0)),      (3, 22, 0,   DATEADD(hour, 7, @t0)),
(3, 23, 2,   DATEADD(hour, 7, @t0)),      (3, 24, 0,   DATEADD(hour, 7, @t0)),
(3, 25, 0,   DATEADD(hour, 7, @t0)),      (3, 26, 0,   DATEADD(hour, 7, @t0)),
(3, 27, 0,   DATEADD(hour, 7, @t0)),      (3, 28, 0,   DATEADD(hour, 7, @t0)),
(3, 29, 600, DATEADD(hour, 7, @t0)),      (3, 30, 1,   DATEADD(hour, 7, @t0));

-- IHM 4 (TORNO_05) – Produzindo, oee~91%
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(4, 31, 1,   @t0),                        (4, 32, 49,  @t0),
(4, 33, 0,   @t0),                        (4, 34, 0,   @t0),
(4, 35, 0,   @t0),                        (4, 36, 0,   @t0),
(4, 37, 0,   @t0),                        (4, 38, 0,   @t0),
(4, 39, 600, @t0),                        (4, 40, 1,   @t0),

(4, 31, 1,   DATEADD(hour, 4, @t0)),      (4, 32, 49,  DATEADD(hour, 4, @t0)),
(4, 33, 0,   DATEADD(hour, 4, @t0)),      (4, 34, 380, DATEADD(hour, 4, @t0)),
(4, 35, 4,   DATEADD(hour, 4, @t0)),      (4, 36, 384, DATEADD(hour, 4, @t0)),
(4, 37, 0,   DATEADD(hour, 4, @t0)),      (4, 38, 0,   DATEADD(hour, 4, @t0)),
(4, 39, 600, DATEADD(hour, 4, @t0)),      (4, 40, 1,   DATEADD(hour, 4, @t0)),

(4, 31, 1,   DATEADD(hour, 7, @t0)),      (4, 32, 49,  DATEADD(hour, 7, @t0)),
(4, 33, 0,   DATEADD(hour, 7, @t0)),      (4, 34, 775, DATEADD(hour, 7, @t0)),
(4, 35, 5,   DATEADD(hour, 7, @t0)),      (4, 36, 780, DATEADD(hour, 7, @t0)),
(4, 37, 0,   DATEADD(hour, 7, @t0)),      (4, 38, 0,   DATEADD(hour, 7, @t0)),
(4, 39, 600, DATEADD(hour, 7, @t0)),      (4, 40, 1,   DATEADD(hour, 7, @t0));

-- IHM 5 (RET_08) – Produzindo, oee~73%
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(5, 41, 1,   @t0),                        (5, 42, 49,  @t0),
(5, 43, 0,   @t0),                        (5, 44, 0,   @t0),
(5, 45, 0,   @t0),                        (5, 46, 0,   @t0),
(5, 47, 0,   @t0),                        (5, 48, 0,   @t0),
(5, 49, 600, @t0),                        (5, 50, 1,   @t0),

(5, 41, 1,   DATEADD(hour, 4, @t0)),      (5, 42, 49,  DATEADD(hour, 4, @t0)),
(5, 43, 0,   DATEADD(hour, 4, @t0)),      (5, 44, 170, DATEADD(hour, 4, @t0)),
(5, 45, 6,   DATEADD(hour, 4, @t0)),      (5, 46, 176, DATEADD(hour, 4, @t0)),
(5, 47, 0,   DATEADD(hour, 4, @t0)),      (5, 48, 0,   DATEADD(hour, 4, @t0)),
(5, 49, 600, DATEADD(hour, 4, @t0)),      (5, 50, 1,   DATEADD(hour, 4, @t0)),

(5, 41, 1,   DATEADD(hour, 7, @t0)),      (5, 42, 49,  DATEADD(hour, 7, @t0)),
(5, 43, 0,   DATEADD(hour, 7, @t0)),      (5, 44, 328, DATEADD(hour, 7, @t0)),
(5, 45, 12,  DATEADD(hour, 7, @t0)),      (5, 46, 340, DATEADD(hour, 7, @t0)),
(5, 47, 0,   DATEADD(hour, 7, @t0)),      (5, 48, 0,   DATEADD(hour, 7, @t0)),
(5, 49, 600, DATEADD(hour, 7, @t0)),      (5, 50, 1,   DATEADD(hour, 7, @t0));

-- IHM 6 (ROBO_12) – Manutenção
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(6, 51, 0,   @t0),                        (6, 52, 52,  @t0),
(6, 53, 3,   @t0),                        (6, 54, 0,   @t0),
(6, 55, 0,   @t0),                        (6, 56, 0,   @t0),
(6, 57, 1,   @t0),                        (6, 58, 0,   @t0),
(6, 59, 600, @t0),                        (6, 60, 1,   @t0),

(6, 51, 0,   DATEADD(hour, 4, @t0)),      (6, 52, 52,  DATEADD(hour, 4, @t0)),
(6, 53, 3,   DATEADD(hour, 4, @t0)),      (6, 54, 0,   DATEADD(hour, 4, @t0)),
(6, 55, 0,   DATEADD(hour, 4, @t0)),      (6, 56, 0,   DATEADD(hour, 4, @t0)),
(6, 57, 1,   DATEADD(hour, 4, @t0)),      (6, 58, 0,   DATEADD(hour, 4, @t0)),
(6, 59, 600, DATEADD(hour, 4, @t0)),      (6, 60, 1,   DATEADD(hour, 4, @t0)),

(6, 51, 0,   DATEADD(hour, 7, @t0)),      (6, 52, 52,  DATEADD(hour, 7, @t0)),
(6, 53, 3,   DATEADD(hour, 7, @t0)),      (6, 54, 0,   DATEADD(hour, 7, @t0)),
(6, 55, 0,   DATEADD(hour, 7, @t0)),      (6, 56, 0,   DATEADD(hour, 7, @t0)),
(6, 57, 1,   DATEADD(hour, 7, @t0)),      (6, 58, 0,   DATEADD(hour, 7, @t0)),
(6, 59, 600, DATEADD(hour, 7, @t0)),      (6, 60, 1,   DATEADD(hour, 7, @t0));

-- IHM 7 (PMAQ_37) – Alerta
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(7, 61, 1,   @t0),                        (7, 62, 49,  @t0),
(7, 63, 0,   @t0),                        (7, 64, 0,   @t0),
(7, 65, 0,   @t0),                        (7, 66, 0,   @t0),
(7, 67, 0,   @t0),                        (7, 68, 0,   @t0),
(7, 69, 600, @t0),                        (7, 70, 1,   @t0),

(7, 61, 1,   DATEADD(hour, 4, @t0)),      (7, 62, 49,  DATEADD(hour, 4, @t0)),
(7, 63, 0,   DATEADD(hour, 4, @t0)),      (7, 64, 258, DATEADD(hour, 4, @t0)),
(7, 65, 15,  DATEADD(hour, 4, @t0)),      (7, 66, 273, DATEADD(hour, 4, @t0)),
(7, 67, 0,   DATEADD(hour, 4, @t0)),      (7, 68, 0,   DATEADD(hour, 4, @t0)),
(7, 69, 600, DATEADD(hour, 4, @t0)),      (7, 70, 1,   DATEADD(hour, 4, @t0)),

(7, 61, 1,   DATEADD(hour, 7, @t0)),      (7, 62, 49,  DATEADD(hour, 7, @t0)),
(7, 63, 0,   DATEADD(hour, 7, @t0)),      (7, 64, 487, DATEADD(hour, 7, @t0)),
(7, 65, 30,  DATEADD(hour, 7, @t0)),      (7, 66, 517, DATEADD(hour, 7, @t0)),
(7, 67, 0,   DATEADD(hour, 7, @t0)),      (7, 68, 0,   DATEADD(hour, 7, @t0)),
(7, 69, 600, DATEADD(hour, 7, @t0)),      (7, 70, 1,   DATEADD(hour, 7, @t0));

-- IHM 8 (MAQ_10) – Parada
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(8, 71, 0,   @t0),                        (8, 72, 0,   @t0),
(8, 73, 2,   @t0),                        (8, 74, 0,   @t0),
(8, 75, 0,   @t0),                        (8, 76, 0,   @t0),
(8, 77, 0,   @t0),                        (8, 78, 0,   @t0),
(8, 79, 600, @t0),                        (8, 80, 1,   @t0),

(8, 71, 0,   DATEADD(hour, 4, @t0)),      (8, 72, 0,   DATEADD(hour, 4, @t0)),
(8, 73, 2,   DATEADD(hour, 4, @t0)),      (8, 74, 0,   DATEADD(hour, 4, @t0)),
(8, 75, 0,   DATEADD(hour, 4, @t0)),      (8, 76, 0,   DATEADD(hour, 4, @t0)),
(8, 77, 0,   DATEADD(hour, 4, @t0)),      (8, 78, 0,   DATEADD(hour, 4, @t0)),
(8, 79, 600, DATEADD(hour, 4, @t0)),      (8, 80, 1,   DATEADD(hour, 4, @t0)),

(8, 71, 0,   DATEADD(hour, 7, @t0)),      (8, 72, 0,   DATEADD(hour, 7, @t0)),
(8, 73, 2,   DATEADD(hour, 7, @t0)),      (8, 74, 0,   DATEADD(hour, 7, @t0)),
(8, 75, 0,   DATEADD(hour, 7, @t0)),      (8, 76, 0,   DATEADD(hour, 7, @t0)),
(8, 77, 0,   DATEADD(hour, 7, @t0)),      (8, 78, 0,   DATEADD(hour, 7, @t0)),
(8, 79, 600, DATEADD(hour, 7, @t0)),      (8, 80, 1,   DATEADD(hour, 7, @t0));

-- IHM 9 (MAQ_08) – Produzindo, oee~51%
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(9, 81, 1,   @t0),                        (9, 82, 49,  @t0),
(9, 83, 0,   @t0),                        (9, 84, 0,   @t0),
(9, 85, 0,   @t0),                        (9, 86, 0,   @t0),
(9, 87, 0,   @t0),                        (9, 88, 0,   @t0),
(9, 89, 600, @t0),                        (9, 90, 1,   @t0),

(9, 81, 1,   DATEADD(hour, 4, @t0)),      (9, 82, 49,  DATEADD(hour, 4, @t0)),
(9, 83, 0,   DATEADD(hour, 4, @t0)),      (9, 84, 126, DATEADD(hour, 4, @t0)),
(9, 85, 4,   DATEADD(hour, 4, @t0)),      (9, 86, 130, DATEADD(hour, 4, @t0)),
(9, 87, 0,   DATEADD(hour, 4, @t0)),      (9, 88, 0,   DATEADD(hour, 4, @t0)),
(9, 89, 600, DATEADD(hour, 4, @t0)),      (9, 90, 1,   DATEADD(hour, 4, @t0)),

(9, 81, 1,   DATEADD(hour, 7, @t0)),      (9, 82, 49,  DATEADD(hour, 7, @t0)),
(9, 83, 0,   DATEADD(hour, 7, @t0)),      (9, 84, 244, DATEADD(hour, 7, @t0)),
(9, 85, 8,   DATEADD(hour, 7, @t0)),      (9, 86, 252, DATEADD(hour, 7, @t0)),
(9, 87, 0,   DATEADD(hour, 7, @t0)),      (9, 88, 0,   DATEADD(hour, 7, @t0)),
(9, 89, 600, DATEADD(hour, 7, @t0)),      (9, 90, 1,   DATEADD(hour, 7, @t0));

-- IHM 10 (MAQ_37) – Produzindo, oee~74%
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(10, 91,  1,   @t0),                      (10, 92,  49,  @t0),
(10, 93,  0,   @t0),                      (10, 94,  0,   @t0),
(10, 95,  0,   @t0),                      (10, 96,  0,   @t0),
(10, 97,  0,   @t0),                      (10, 98,  0,   @t0),
(10, 99,  600, @t0),                      (10, 100, 1,   @t0),

(10, 91,  1,   DATEADD(hour, 4, @t0)),    (10, 92,  49,  DATEADD(hour, 4, @t0)),
(10, 93,  0,   DATEADD(hour, 4, @t0)),    (10, 94,  180, DATEADD(hour, 4, @t0)),
(10, 95,  1,   DATEADD(hour, 4, @t0)),    (10, 96,  181, DATEADD(hour, 4, @t0)),
(10, 97,  0,   DATEADD(hour, 4, @t0)),    (10, 98,  0,   DATEADD(hour, 4, @t0)),
(10, 99,  600, DATEADD(hour, 4, @t0)),    (10, 100, 1,   DATEADD(hour, 4, @t0)),

(10, 91,  1,   DATEADD(hour, 7, @t0)),    (10, 92,  49,  DATEADD(hour, 7, @t0)),
(10, 93,  0,   DATEADD(hour, 7, @t0)),    (10, 94,  356, DATEADD(hour, 7, @t0)),
(10, 95,  3,   DATEADD(hour, 7, @t0)),    (10, 96,  359, DATEADD(hour, 7, @t0)),
(10, 97,  0,   DATEADD(hour, 7, @t0)),    (10, 98,  0,   DATEADD(hour, 7, @t0)),
(10, 99,  600, DATEADD(hour, 7, @t0)),    (10, 100, 1,   DATEADD(hour, 7, @t0));

-- IHM 11 (MAQ_28) – Limpeza
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(11, 101, 1,   @t0),                      (11, 102, 49,  @t0),
(11, 103, 0,   @t0),                      (11, 104, 0,   @t0),
(11, 105, 0,   @t0),                      (11, 106, 0,   @t0),
(11, 107, 0,   @t0),                      (11, 108, 0,   @t0),
(11, 109, 600, @t0),                      (11, 110, 1,   @t0),

(11, 101, 1,   DATEADD(hour, 4, @t0)),    (11, 102, 49,  DATEADD(hour, 4, @t0)),
(11, 103, 0,   DATEADD(hour, 4, @t0)),    (11, 104, 200, DATEADD(hour, 4, @t0)),
(11, 105, 5,   DATEADD(hour, 4, @t0)),    (11, 106, 205, DATEADD(hour, 4, @t0)),
(11, 107, 0,   DATEADD(hour, 4, @t0)),    (11, 108, 0,   DATEADD(hour, 4, @t0)),
(11, 109, 600, DATEADD(hour, 4, @t0)),    (11, 110, 1,   DATEADD(hour, 4, @t0)),

(11, 101, 1,   DATEADD(hour, 7, @t0)),    (11, 102, 4,   DATEADD(hour, 7, @t0)),  -- Limpeza
(11, 103, 4,   DATEADD(hour, 7, @t0)),    (11, 104, 295, DATEADD(hour, 7, @t0)),
(11, 105, 10,  DATEADD(hour, 7, @t0)),    (11, 106, 305, DATEADD(hour, 7, @t0)),
(11, 107, 0,   DATEADD(hour, 7, @t0)),    (11, 108, 0,   DATEADD(hour, 7, @t0)),
(11, 109, 600, DATEADD(hour, 7, @t0)),    (11, 110, 1,   DATEADD(hour, 7, @t0));

-- IHM 12 (MAQ_59) – Manutenção
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(12, 111, 0,   @t0),                      (12, 112, 52,  @t0),
(12, 113, 5,   @t0),                      (12, 114, 0,   @t0),
(12, 115, 0,   @t0),                      (12, 116, 0,   @t0),
(12, 117, 1,   @t0),                      (12, 118, 0,   @t0),
(12, 119, 600, @t0),                      (12, 120, 1,   @t0),

(12, 111, 0,   DATEADD(hour, 4, @t0)),    (12, 112, 52,  DATEADD(hour, 4, @t0)),
(12, 113, 5,   DATEADD(hour, 4, @t0)),    (12, 114, 0,   DATEADD(hour, 4, @t0)),
(12, 115, 0,   DATEADD(hour, 4, @t0)),    (12, 116, 0,   DATEADD(hour, 4, @t0)),
(12, 117, 1,   DATEADD(hour, 4, @t0)),    (12, 118, 0,   DATEADD(hour, 4, @t0)),
(12, 119, 600, DATEADD(hour, 4, @t0)),    (12, 120, 1,   DATEADD(hour, 4, @t0)),

(12, 111, 0,   DATEADD(hour, 7, @t0)),    (12, 112, 52,  DATEADD(hour, 7, @t0)),
(12, 113, 5,   DATEADD(hour, 7, @t0)),    (12, 114, 0,   DATEADD(hour, 7, @t0)),
(12, 115, 0,   DATEADD(hour, 7, @t0)),    (12, 116, 0,   DATEADD(hour, 7, @t0)),
(12, 117, 1,   DATEADD(hour, 7, @t0)),    (12, 118, 0,   DATEADD(hour, 7, @t0)),
(12, 119, 600, DATEADD(hour, 7, @t0)),    (12, 120, 1,   DATEADD(hour, 7, @t0));
GO
