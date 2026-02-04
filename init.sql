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

/* POPULANDO TABELAS */ 

USE MES_Core;
GO

BEGIN TRANSACTION;

SET IDENTITY_INSERT dbo.tb_linha_producao ON;

INSERT INTO dbo.tb_linha_producao (id_linha_producao, tx_name)
VALUES (1, N'LINHA_1');

SET IDENTITY_INSERT dbo.tb_linha_producao OFF;

SET IDENTITY_INSERT dbo.tb_ihm ON;

INSERT INTO dbo.tb_ihm (id_ihm, tx_ip_address, tx_port_number, id_linha_producao, tx_name)
VALUES
(1, '192.168.11.89', 502, 1, N'MAQUINA_1'),
(2, '192.168.11.90', 502, 1, N'MAQUINA_2');

SET IDENTITY_INSERT dbo.tb_ihm OFF;

INSERT INTO dbo.tb_registrador (nu_endereco, tx_descricao, id_ihm)
VALUES
(0,    N'operador',        1),
(3001, N'produzido',       1),
(3010, N'reprovado',       1),
(3000, N'total_produzido', 1),
(1000, N'manutentor',      1),
(1500, N'engenheiro',      1),
(2000, N'status_maquina',  1),
(2000, N'motivo_parada',   1),

(0,    N'operador',        2),
(7024, N'produzido',       2),
(7025, N'reprovado',       2),
(7056, N'total_produzido', 2),
(1000, N'manutentor',      2),
(1500, N'engenheiro',      2),
(2000, N'status_maquina',  2),
(2000, N'motivo_parada',   2);

COMMIT;
GO
