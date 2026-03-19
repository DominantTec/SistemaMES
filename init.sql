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
   Linha 1 – LINHA ACM     : 2 IHMs reais (DIACom)     → id_ihm 1, 2
   Linha 2 – LINHA PINTURA : 5 IHMs fantasma (sim)  → id_ihm 3..7
   ========================================================= */

USE MES_Core;
GO

-- -------------------------------------------------------
-- Linhas de produção
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_linha_producao ON;

INSERT INTO dbo.tb_linha_producao (id_linha_producao, tx_name) VALUES
(1, N'LINHA ACM'),       -- máquinas reais, conectadas via DIACom
(2, N'LINHA PINTURA');   -- máquinas fantasma, alimentadas pelo simulator.py

SET IDENTITY_INSERT dbo.tb_linha_producao OFF;
GO

-- -------------------------------------------------------
-- IHMs
-- LINHA ACM (real): ajuste os IPs/portas conforme o DIACom
-- LINHA PINTURA (fantasma): IPs fictícios, não são acessados via Modbus
-- -------------------------------------------------------
SET IDENTITY_INSERT dbo.tb_ihm ON;

INSERT INTO dbo.tb_ihm (id_ihm, tx_ip_address, tx_port_number, id_linha_producao, tx_name) VALUES
-- Linha 1 – reais (altere os IPs para os endereços reais do DIACom)
(1, '192.168.11.89', '502', 1, N'ACM 1'),
(2, '192.168.11.90', '502', 1, N'ACM 2'),
-- Linha 2 – fantasmas (IPs não usados; simulação feita pelo simulator.py)
(3, '127.0.0.1', '5020', 2, N'TRATAMENTO 1'),
(4, '127.0.0.1', '5021', 2, N'PRIMER 1'),
(5, '127.0.0.1', '5022', 2, N'PINTURA 1'),
(6, '127.0.0.1', '5023', 2, N'PINTURA 2'),
(7, '127.0.0.1', '5024', 2, N'ESTUFA 1');

SET IDENTITY_INSERT dbo.tb_ihm OFF;
GO

SET IDENTITY_INSERT dbo.tb_ftp_needed ON;

INSERT INTO dbo.tb_ftp_needed (id_ftp_needed, id_ihm, bl_needed) VALUES
(1, 1, 1),
(2, 2, 0),
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

INSERT INTO dbo.tb_registrador (nu_endereco, tx_descricao, id_ihm) VALUES
-- IHM 1 – CUSI_02 (real)
(0,    N'operador',        1),
(3001, N'produzido',       1),
(3010, N'reprovado',       1),
(3000, N'total_produzido', 1),
(1000, N'manutentor',      1),
(1500, N'engenheiro',      1),
(2000, N'status_maquina',  1),
(2000, N'motivo_parada',   1),
(4000, N'meta',            1),
(4100, N'modelo_peça',     1),
-- IHM 2 – MAQ_24 (real) --
(0,    N'operador',        2),
(7024, N'produzido',       2),
(7025, N'reprovado',       2),
(7056, N'total_produzido', 2),
(1000, N'manutentor',      2),
(1500, N'engenheiro',      2),
(2000, N'status_maquina',  2),
(2000, N'motivo_parada',   2),
(4000, N'meta',            2),
(4100, N'modelo_peça',     2),
-- IHM 3 – SIM_01 (fantasma)
(0,   N'operador',        3),
(100, N'status_maquina',  3),
(101, N'motivo_parada',   3),
(200, N'produzido',       3),
(201, N'reprovado',       3),
(202, N'total_produzido', 3),
(300, N'manutentor',      3),
(301, N'engenheiro',      3),
(400, N'meta',            3),
(401, N'modelo_peça',     3),
-- IHM 4 – SIM_02 (fantasma)
(0,   N'operador',        4),
(100, N'status_maquina',  4),
(101, N'motivo_parada',   4),
(200, N'produzido',       4),
(201, N'reprovado',       4),
(202, N'total_produzido', 4),
(300, N'manutentor',      4),
(301, N'engenheiro',      4),
(400, N'meta',            4),
(401, N'modelo_peça',     4),
-- IHM 5 – SIM_03 (fantasma)
(0,   N'operador',        5),
(100, N'status_maquina',  5),
(101, N'motivo_parada',   5),
(200, N'produzido',       5),
(201, N'reprovado',       5),
(202, N'total_produzido', 5),
(300, N'manutentor',      5),
(301, N'engenheiro',      5),
(400, N'meta',            5),
(401, N'modelo_peça',     5),
-- IHM 6 – SIM_04 (fantasma)
(0,   N'operador',        6),
(100, N'status_maquina',  6),
(101, N'motivo_parada',   6),
(200, N'produzido',       6),
(201, N'reprovado',       6),
(202, N'total_produzido', 6),
(300, N'manutentor',      6),
(301, N'engenheiro',      6),
(400, N'meta',            6),
(401, N'modelo_peça',     6),
-- IHM 7 – SIM_05 (fantasma)
(0,   N'operador',        7),
(100, N'status_maquina',  7),
(101, N'motivo_parada',   7),
(200, N'produzido',       7),
(201, N'reprovado',       7),
(202, N'total_produzido', 7),
(300, N'manutentor',      7),
(301, N'engenheiro',      7),
(400, N'meta',            7),
(401, N'modelo_peça',     7);

COMMIT;
GO

-- -------------------------------------------------------
-- Turnos: T1/T2/T3 para cada dia da semana, 5 semanas
-- passadas + 1 futura, para as duas linhas.
-- -------------------------------------------------------
DECLARE @seed_start DATE = DATEADD(week, -5, CAST(GETDATE() AS DATE));
DECLARE @seed_end   DATE = DATEADD(week,  1, CAST(GETDATE() AS DATE));
DECLARE @d          DATE = @seed_start;

WHILE @d <= @seed_end
BEGIN
    DECLARE @base DATETIME2(0) = CAST(@d AS DATETIME2(0));

    INSERT INTO dbo.tb_turnos (tx_name, dt_inicio, dt_fim, id_linha_producao, bl_ativo)
    VALUES
      (N'T1', DATEADD(hour,  6, @base), DATEADD(hour, 14, @base), 1, 1),
      (N'T2', DATEADD(hour, 14, @base), DATEADD(hour, 22, @base), 1, 1),
      (N'T3', DATEADD(hour, 22, @base), DATEADD(hour, 30, @base), 1, 1),
      (N'T1', DATEADD(hour,  6, @base), DATEADD(hour, 14, @base), 2, 1),
      (N'T2', DATEADD(hour, 14, @base), DATEADD(hour, 22, @base), 2, 1),
      (N'T3', DATEADD(hour, 22, @base), DATEADD(hour, 30, @base), 2, 1);

    SET @d = DATEADD(day, 1, @d);
END
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
(1,  N'Antonia Tomaz',        1),
(2,  N'Janice Souza',         1),
(3,  N'Daiane Godofredo',     1),
(5,  N'Claudia Almeida',      1),
(7,  N'Sueli Ferreira',       1),
(22, N'Janete Azevedo',       1),
(23, N'Andreia Vilela',       1),
(24, N'Joana Darc',           1),
(26, N'Carlos Cesar',         1),
(28, N'Katia da Silva',       1),
(34, N'Crisleide Oliveira',   1),
(45, N'Sueli Pereira',        1),
(46, N'Dislene da Silva',     1),
(47, N'Luciana Ribeiro',      1),
(48, N'Luziete Ribeiro',      1),
(49, N'Vanessa Michael',      1),
(50, N'Rosanfega de Jesus',   1),
(11, N'Clesia Maria',         1),
(6,  N'Doralice',             1),
(48, N'Luziete',              1),
(53, N'Luciano Barbeiro',     1),
(1,  N'Zoãozinho F.',        2),
-- Linha simulada (múltiplos por IHM para rodízio na simulação)
(1, N'Lucas F.',    3),
(2, N'Fernanda K.', 3),
(3, N'Bruno S.',   3),
(1, N'Ricardo A.',  4),
(2, N'Sandra M.',   4),
(1, N'Tatiane B.',  5),
(2, N'Carlos R.',   5),
(3, N'Marcos P.',  5),
(1, N'Patrícia L.', 6),
(2, N'Eduardo N.',  6),
(1, N'Fábio C.',    7),
(2, N'Juliana M.',  7);
GO

-- -------------------------------------------------------
-- De-para: manutentores
-- -------------------------------------------------------
INSERT INTO dbo.tb_depara_manutentor (nu_cod_manutentor, tx_manutentor, id_ihm) VALUES
(100, N'Hugo cesar',           1),
(101, N'Cleberson Sarmento',   1),
(102, N'Tiago Bastos',         1),
(103, N'Mateus Braga',         1),
(104, N'Carlos Eduardo',       1),
(105, N'Rafel Rodrigues',      1),
(106, N'Alexandre Lima',       1),
(107, N'Wagner de Souza',      1),
(108, N'Roberto Satori',       1),
(109, N'Marcus Ribeiro',       1),
(110, N'Marcelo Ricardo',      1),
(111, N'Fernando Jose',        1),
(112, N'Edson da Luz',         1),
(113, N'Willian Marcos',       1),
(114, N'Johnny Neris',         1),
(115, N'Jose Carlos',          1),
(116, N'Gean Cardoso',         1),
(117, N'Ricardo Macena',       1),
(118, N'Diego Jose',           1),
(119, N'Maicon Ribeiro',       1),
(120, N'Flavio Balera',        1),
(121, N'Gildasio Reis',        1),
(122, N'Jonas Mendes',         1),
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
(500, N'Marcelo Francelino',   1),
(501, N'Willian Correa',       1),
(502, N'Yanke Vinicius',       1),
(503, N'Michael dos Santos',   1),
(504, N'Marcos Guimaraes',     1),
(505, N'Fabricio Santos',      1),
(506, N'Marcelo Ardito',       1),
(507, N'Antonia Tomaz',        1),
(508, N'Janice Souza',         1),
(509, N'Luciano Ribeiro',      1),
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
-- Linha real (IHM 1) – códigos reais do robô
(0,  N'Máquina Parada',                     1),
(1,  N'Passar Padrão',                      1),
(2,  N'Troca de Caixa de Saida',            1),
(3,  N'Abastecimento de Material',          1),
(4,  N'Limpeza Geral da Máquina',           1),
(5,  N'DDS / Ginástica',                    1),
(6,  N'Refeição',                           1),
(7,  N'Troca de Operador',                  1),
(8,  N'Ausência do Posto de Trabalho',      1),
(9,  N'Reunião',                            1),
(10, N'Disco Enroscado no Alimentador',     1),
(11, N'Borboleta Enroscada no Alimentador', 1),
(12, N'Registro Enroscado no Alimentador',  1),
(13, N'Inspeção de Torque',                 1),
(14, N'Falta de Material para Produção',    1),
(15, N'Treinamento',                        1),
(16, N'Troca de EPI',                       1),
(17, N'Troca do Anel ORING',                1),
(18, N'Aguardando Qualidade',               1),
(19, N'Testes da Qualidade',                1),
(20, N'Limpeza do Vedante',                 1),
(21, N'Abastecimento de Vedante',           1),
(22, N'Falha no Ciclo',                     1),
(23, N'Baixa Pressão de Ar',                1),
(24, N'Ajuste',                             1),
(25, N'Aguardando Engenharia',              1),
(26, N'Testes da Engenharia',               1),
(27, N'Teste de Tração',                    1),
(28, N'Falha na Tampa',                     1),
(29, N'Falha na Mola',                      1),
(30, N'Falha no Corpo',                     1),
(31, N'Falha na Sobretampa (506)',           1),
(32, N'Corpo Enroscado no Alimentador',     1),
(49, N'Máquina Produzindo',                 1),
(50, N'Máquina Liberada',                   1),
(51, N'Aguardando Manutentor',              1),
(52, N'Máquina em Manutenção',              1),
(53, N'Alteração de Parâmetros',            1),
(0,  N'Máquina Parada',                     2),
(49, N'Máquina Produzindo',                 2),
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
