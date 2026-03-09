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
   POPULANDO TABELAS
   =========================================================
   Linha 1 – LINHA_505   : 2 IHMs reais (DIACom)     → id_ihm 1, 2
   Linha 2 – LINHA_SIMULADA : 5 IHMs fantasma (sim)  → id_ihm 3..7
   ========================================================= */

USE MES_Core;
GO

-- -------------------------------------------------------
-- Linhas de produção
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_linha_producao ON;

INSERT INTO dbo.tb_linha_producao (id_linha_producao, tx_name) VALUES
(1, N'LINHA_505'),       -- máquinas reais, conectadas via DIACom
(2, N'LINHA_SIMULADA');  -- máquinas fantasma, alimentadas pelo simulator.py

SET IDENTITY_INSERT dbo.tb_linha_producao OFF;
GO

-- -------------------------------------------------------
-- IHMs
-- LINHA_505 (real): ajuste os IPs/portas conforme o DIACom
-- LINHA_SIMULADA (fantasma): IPs fictícios, não são acessados via Modbus
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_ihm ON;

INSERT INTO dbo.tb_ihm (id_ihm, tx_ip_address, tx_port_number, id_linha_producao, tx_name) VALUES
-- Linha 1 – reais (altere os IPs para os endereços reais do DIACom)
(1, '192.168.1.1', '502', 1, N'CUSI_02'),
(2, '192.168.1.2', '502', 1, N'MAQ_24'),
-- Linha 2 – fantasmas (IPs não usados; simulação feita pelo simulator.py)
(3, '127.0.0.1', '5020', 2, N'SIM_01'),
(4, '127.0.0.1', '5021', 2, N'SIM_02'),
(5, '127.0.0.1', '5022', 2, N'SIM_03'),
(6, '127.0.0.1', '5023', 2, N'SIM_04'),
(7, '127.0.0.1', '5024', 2, N'SIM_05');

SET IDENTITY_INSERT dbo.tb_ihm OFF;
GO

-- -------------------------------------------------------
-- FTP
-- Máquinas reais: bl_needed=1 (aguardando config real)
-- Máquinas fantasma: bl_needed=0 (não usam FTP)
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_ftp_needed ON;

INSERT INTO dbo.tb_ftp_needed (id_ftp_needed, id_ihm, bl_needed) VALUES
(1, 1, 1),
(2, 2, 1),
(3, 3, 0),
(4, 4, 0),
(5, 5, 0),
(6, 6, 0),
(7, 7, 0);

SET IDENTITY_INSERT dbo.tb_ftp_needed OFF;
GO

-- -------------------------------------------------------
-- Registradores (10 por IHM)
-- id = (id_ihm - 1) * 10 + offset
--  1=operador  2=status_maquina  3=motivo_parada
--  4=produzido 5=reprovado       6=total_produzido
--  7=manutentor 8=engenheiro     9=meta  10=modelo_peça
-- status_maquina: 49=Produzindo, 0=Parada, 4=Limpeza, 52=Manutenção
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_registrador ON;

INSERT INTO dbo.tb_registrador (id_registrador, nu_endereco, tx_descricao, id_ihm) VALUES
-- IHM 1 – CUSI_02 (real)
(1,  0,   N'operador',        1), (2,  100, N'status_maquina',  1),
(3,  101, N'motivo_parada',   1), (4,  200, N'produzido',       1),
(5,  201, N'reprovado',       1), (6,  202, N'total_produzido', 1),
(7,  300, N'manutentor',      1), (8,  301, N'engenheiro',      1),
(9,  400, N'meta',            1), (10, 401, N'modelo_peça',     1),
-- IHM 2 – MAQ_24 (real)
(11, 0,   N'operador',        2), (12, 100, N'status_maquina',  2),
(13, 101, N'motivo_parada',   2), (14, 200, N'produzido',       2),
(15, 201, N'reprovado',       2), (16, 202, N'total_produzido', 2),
(17, 300, N'manutentor',      2), (18, 301, N'engenheiro',      2),
(19, 400, N'meta',            2), (20, 401, N'modelo_peça',     2),
-- IHM 3 – SIM_01 (fantasma)
(21, 0,   N'operador',        3), (22, 100, N'status_maquina',  3),
(23, 101, N'motivo_parada',   3), (24, 200, N'produzido',       3),
(25, 201, N'reprovado',       3), (26, 202, N'total_produzido', 3),
(27, 300, N'manutentor',      3), (28, 301, N'engenheiro',      3),
(29, 400, N'meta',            3), (30, 401, N'modelo_peça',     3),
-- IHM 4 – SIM_02 (fantasma)
(31, 0,   N'operador',        4), (32, 100, N'status_maquina',  4),
(33, 101, N'motivo_parada',   4), (34, 200, N'produzido',       4),
(35, 201, N'reprovado',       4), (36, 202, N'total_produzido', 4),
(37, 300, N'manutentor',      4), (38, 301, N'engenheiro',      4),
(39, 400, N'meta',            4), (40, 401, N'modelo_peça',     4),
-- IHM 5 – SIM_03 (fantasma)
(41, 0,   N'operador',        5), (42, 100, N'status_maquina',  5),
(43, 101, N'motivo_parada',   5), (44, 200, N'produzido',       5),
(45, 201, N'reprovado',       5), (46, 202, N'total_produzido', 5),
(47, 300, N'manutentor',      5), (48, 301, N'engenheiro',      5),
(49, 400, N'meta',            5), (50, 401, N'modelo_peça',     5),
-- IHM 6 – SIM_04 (fantasma)
(51, 0,   N'operador',        6), (52, 100, N'status_maquina',  6),
(53, 101, N'motivo_parada',   6), (54, 200, N'produzido',       6),
(55, 201, N'reprovado',       6), (56, 202, N'total_produzido', 6),
(57, 300, N'manutentor',      6), (58, 301, N'engenheiro',      6),
(59, 400, N'meta',            6), (60, 401, N'modelo_peça',     6),
-- IHM 7 – SIM_05 (fantasma)
(61, 0,   N'operador',        7), (62, 100, N'status_maquina',  7),
(63, 101, N'motivo_parada',   7), (64, 200, N'produzido',       7),
(65, 201, N'reprovado',       7), (66, 202, N'total_produzido', 7),
(67, 300, N'manutentor',      7), (68, 301, N'engenheiro',      7),
(69, 400, N'meta',            7), (70, 401, N'modelo_peça',     7);

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
-- Linha real
(1, N'Eixo A-12',  1),
(1, N'Base Z',     2),
-- Linha simulada (2 modelos por IHM para permitir troca durante simulação)
(1, N'Corpo X-7',  3), (2, N'Pino B-3',   3),
(1, N'Anel C-7',   4), (2, N'Suporte L',  4),
(1, N'Tampa D-1',  5), (2, N'Flange E-2', 5),
(1, N'Bloco H-4',  6), (2, N'Capa G-9',   6),
(1, N'Eixo F-5',   7), (2, N'Fuso J-2',   7);
GO

-- -------------------------------------------------------
-- De-para: operadores
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_operador (nu_cod_operador, tx_operador, id_ihm) VALUES
-- Linha real
(1, N'Ana S.',      1), (2, N'João M.',    1),
(1, N'João M.',     2),
-- Linha simulada (múltiplos por IHM para rodízio na simulação)
(1, N'Lucas F.',    3), (2, N'Fernanda K.', 3), (3, N'Bruno S.',   3),
(1, N'Ricardo A.',  4), (2, N'Sandra M.',   4),
(1, N'Tatiane B.',  5), (2, N'Carlos R.',   5), (3, N'Marcos P.',  5),
(1, N'Patrícia L.', 6), (2, N'Eduardo N.',  6),
(1, N'Fábio C.',    7), (2, N'Juliana M.',  7);
GO

-- -------------------------------------------------------
-- De-para: manutentores
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_manutentor (nu_cod_manutentor, tx_manutentor, id_ihm) VALUES
-- Linha real
(1, N'Marcos T.',   1),
(1, N'Marcos T.',   2),
-- Linha simulada
(1, N'Lucas P.',    3),
(1, N'Lucas P.',    4),
(1, N'Roberto C.',  5),
(1, N'Roberto C.',  6),
(1, N'Lucas P.',    7), (2, N'Roberto C.', 7);
GO

-- -------------------------------------------------------
-- De-para: engenheiros
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_engenheiro (nu_cod_engenheiro, tx_engenheiro, id_ihm) VALUES
-- Linha real
(1, N'Dr. Silva',    1),
(1, N'Dr. Silva',    2),
-- Linha simulada
(1, N'Eng. Costa',   3),
(1, N'Eng. Costa',   4),
(1, N'Eng. Costa',   5),
(1, N'Eng. Almeida', 6),
(1, N'Eng. Almeida', 7);
GO

-- -------------------------------------------------------
-- De-para: motivos de parada
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_motivo_parada (nu_cod_motivo_parada, tx_motivo_parada, id_ihm) VALUES
-- Linha real
(1, N'Aguardando Matéria Prima', 1), (2, N'Falta de operador',     1),
(3, N'Manutenção Preventiva',    1), (4, N'Limpeza programada',    1),
(5, N'Troca de ferramental',     1),
(1, N'Aguardando Matéria Prima', 2), (2, N'Falta de operador',     2),
-- Linha simulada (mesmo conjunto para todas as IHMs fantasma)
(1, N'Aguardando Matéria Prima', 3), (2, N'Falta de operador',     3),
(3, N'Manutenção Preventiva',    3), (4, N'Limpeza programada',    3),
(5, N'Troca de ferramental',     3),
(1, N'Aguardando Matéria Prima', 4), (2, N'Falta de operador',     4),
(3, N'Manutenção Preventiva',    4), (4, N'Limpeza programada',    4),
(5, N'Troca de ferramental',     4),
(1, N'Aguardando Matéria Prima', 5), (2, N'Falta de operador',     5),
(3, N'Manutenção Preventiva',    5), (4, N'Limpeza programada',    5),
(5, N'Troca de ferramental',     5),
(1, N'Aguardando Matéria Prima', 6), (2, N'Falta de operador',     6),
(3, N'Manutenção Preventiva',    6), (4, N'Limpeza programada',    6),
(5, N'Troca de ferramental',     6),
(1, N'Aguardando Matéria Prima', 7), (2, N'Falta de operador',     7),
(3, N'Manutenção Preventiva',    7), (4, N'Limpeza programada',    7),
(5, N'Troca de ferramental',     7);
GO

-- -------------------------------------------------------
-- Logs de produção – snapshots iniciais do turno T1
--
-- status_maquina: 49=Produzindo, 0=Parada, 4=Limpeza, 52=Manutenção
--
-- Linha real (IHMs 1-2): snapshots em t0, t0+3h e t0+7h
-- Linha simulada (IHMs 3-7): snapshot inicial em t0
--   o simulator.py continuará a partir daqui
-- -------------------------------------------------------
DECLARE @t0 DATETIME2(0) = DATEADD(hour, 6, CAST(CAST(GETDATE() AS DATE) AS DATETIME2(0)));

-- ── IHM 1 (CUSI_02) – Produzindo normalmente ──────────────────────────────
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

-- ── IHM 2 (MAQ_24) – Parada no início, volta depois ───────────────────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(2, 11, 0,   @t0),                        (2, 12, 0,   @t0),  -- Parada (sem operador)
(2, 13, 2,   @t0),                        (2, 14, 0,   @t0),
(2, 15, 0,   @t0),                        (2, 16, 0,   @t0),
(2, 17, 0,   @t0),                        (2, 18, 0,   @t0),
(2, 19, 600, @t0),                        (2, 20, 1,   @t0),

(2, 11, 1,   DATEADD(hour, 3, @t0)),      (2, 12, 49,  DATEADD(hour, 3, @t0)),  -- Voltou a produzir
(2, 13, 0,   DATEADD(hour, 3, @t0)),      (2, 14, 0,   DATEADD(hour, 3, @t0)),
(2, 15, 0,   DATEADD(hour, 3, @t0)),      (2, 16, 0,   DATEADD(hour, 3, @t0)),
(2, 17, 0,   DATEADD(hour, 3, @t0)),      (2, 18, 0,   DATEADD(hour, 3, @t0)),
(2, 19, 600, DATEADD(hour, 3, @t0)),      (2, 20, 1,   DATEADD(hour, 3, @t0)),

(2, 11, 1,   DATEADD(hour, 7, @t0)),      (2, 12, 49,  DATEADD(hour, 7, @t0)),
(2, 13, 0,   DATEADD(hour, 7, @t0)),      (2, 14, 312, DATEADD(hour, 7, @t0)),
(2, 15, 8,   DATEADD(hour, 7, @t0)),      (2, 16, 320, DATEADD(hour, 7, @t0)),
(2, 17, 0,   DATEADD(hour, 7, @t0)),      (2, 18, 0,   DATEADD(hour, 7, @t0)),
(2, 19, 600, DATEADD(hour, 7, @t0)),      (2, 20, 1,   DATEADD(hour, 7, @t0));

-- ── IHM 3 (SIM_01) – Produzindo (estado inicial para o simulador) ──────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(3, 21, 1,   @t0), (3, 22, 49,  @t0),
(3, 23, 0,   @t0), (3, 24, 0,   @t0),
(3, 25, 0,   @t0), (3, 26, 0,   @t0),
(3, 27, 0,   @t0), (3, 28, 0,   @t0),
(3, 29, 1000, @t0), (3, 30, 1,   @t0);

-- ── IHM 4 (SIM_02) – Produzindo ───────────────────────────────────────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(4, 31, 2,   @t0), (4, 32, 49,  @t0),
(4, 33, 0,   @t0), (4, 34, 0,   @t0),
(4, 35, 0,   @t0), (4, 36, 0,   @t0),
(4, 37, 0,   @t0), (4, 38, 0,   @t0),
(4, 39, 1000, @t0), (4, 40, 1,   @t0);

-- ── IHM 5 (SIM_03) – Produzindo ───────────────────────────────────────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(5, 41, 1,   @t0), (5, 42, 49,  @t0),
(5, 43, 0,   @t0), (5, 44, 0,   @t0),
(5, 45, 0,   @t0), (5, 46, 0,   @t0),
(5, 47, 0,   @t0), (5, 48, 0,   @t0),
(5, 49, 1000, @t0), (5, 50, 1,   @t0);

-- ── IHM 6 (SIM_04) – Produzindo ───────────────────────────────────────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(6, 51, 1,   @t0), (6, 52, 49,  @t0),
(6, 53, 0,   @t0), (6, 54, 0,   @t0),
(6, 55, 0,   @t0), (6, 56, 0,   @t0),
(6, 57, 0,   @t0), (6, 58, 0,   @t0),
(6, 59, 1000, @t0), (6, 60, 1,   @t0);

-- ── IHM 7 (SIM_05) – Produzindo ───────────────────────────────────────────
INSERT INTO dbo.tb_log_registrador (id_ihm, id_registrador, nu_valor_bruto, dt_created_at) VALUES
(7, 61, 1,   @t0), (7, 62, 49,  @t0),
(7, 63, 0,   @t0), (7, 64, 0,   @t0),
(7, 65, 0,   @t0), (7, 66, 0,   @t0),
(7, 67, 0,   @t0), (7, 68, 0,   @t0),
(7, 69, 1000, @t0), (7, 70, 1,   @t0);
GO

