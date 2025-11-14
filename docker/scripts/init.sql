USE [master]
GO
/****** Object:  Database [IHM_Testes_2]    Script Date: 27/10/2025 14:46:23 ******/
CREATE DATABASE [IHM_Testes_2]
GO
IF (1 = FULLTEXTSERVICEPROPERTY('IsFullTextInstalled'))
begin
EXEC [IHM_Testes_2].[dbo].[sp_fulltext_database] @action = 'enable'
end
GO
ALTER DATABASE [IHM_Testes_2] SET ANSI_NULL_DEFAULT OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET ANSI_NULLS OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET ANSI_PADDING OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET ANSI_WARNINGS OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET ARITHABORT OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET AUTO_CLOSE OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET AUTO_SHRINK OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET AUTO_UPDATE_STATISTICS ON 
GO
ALTER DATABASE [IHM_Testes_2] SET CURSOR_CLOSE_ON_COMMIT OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET CURSOR_DEFAULT  GLOBAL 
GO
ALTER DATABASE [IHM_Testes_2] SET CONCAT_NULL_YIELDS_NULL OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET NUMERIC_ROUNDABORT OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET QUOTED_IDENTIFIER OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET RECURSIVE_TRIGGERS OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET  DISABLE_BROKER 
GO
ALTER DATABASE [IHM_Testes_2] SET AUTO_UPDATE_STATISTICS_ASYNC OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET DATE_CORRELATION_OPTIMIZATION OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET TRUSTWORTHY OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET ALLOW_SNAPSHOT_ISOLATION OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET PARAMETERIZATION SIMPLE 
GO
ALTER DATABASE [IHM_Testes_2] SET READ_COMMITTED_SNAPSHOT OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET HONOR_BROKER_PRIORITY OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET RECOVERY SIMPLE 
GO
ALTER DATABASE [IHM_Testes_2] SET  MULTI_USER 
GO
ALTER DATABASE [IHM_Testes_2] SET PAGE_VERIFY CHECKSUM  
GO
ALTER DATABASE [IHM_Testes_2] SET DB_CHAINING OFF 
GO
ALTER DATABASE [IHM_Testes_2] SET FILESTREAM( NON_TRANSACTED_ACCESS = OFF ) 
GO
ALTER DATABASE [IHM_Testes_2] SET TARGET_RECOVERY_TIME = 60 SECONDS 
GO
ALTER DATABASE [IHM_Testes_2] SET DELAYED_DURABILITY = DISABLED 
GO
ALTER DATABASE [IHM_Testes_2] SET ACCELERATED_DATABASE_RECOVERY = OFF  
GO
ALTER DATABASE [IHM_Testes_2] SET QUERY_STORE = ON
GO
ALTER DATABASE [IHM_Testes_2] SET QUERY_STORE (OPERATION_MODE = READ_WRITE, CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 30), DATA_FLUSH_INTERVAL_SECONDS = 900, INTERVAL_LENGTH_MINUTES = 60, MAX_STORAGE_SIZE_MB = 1000, QUERY_CAPTURE_MODE = AUTO, SIZE_BASED_CLEANUP_MODE = AUTO, MAX_PLANS_PER_QUERY = 200, WAIT_STATS_CAPTURE_MODE = ON)
GO
USE [IHM_Testes_2]
GO
/****** Object:  Schema [SoftIHM]    Script Date: 27/10/2025 14:46:23 ******/
CREATE SCHEMA [SoftIHM]
GO
USE [IHM_Testes_2]
GO
/****** Object:  Sequence [dbo].[LogBatchSequence]    Script Date: 27/10/2025 14:46:23 ******/
CREATE SEQUENCE [dbo].[LogBatchSequence] 
 AS [bigint]
 START WITH 100000
 INCREMENT BY 1
 MINVALUE -9223372036854775808
 MAXVALUE 9223372036854775807
 NO CACHE 
GO
/****** Object:  Table [dbo].[notificacoes]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[notificacoes](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_ihm] [int] NOT NULL,
	[titulo] [nvarchar](100) NOT NULL,
	[mensagem] [nvarchar](max) NOT NULL,
	[status] [bit] NOT NULL,
	[tipo] [nvarchar](255) NULL,
	[data_hora] [datetime] NOT NULL,
	[nivel] [int] NULL,
	[batch_id] [int] NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  View [dbo].[vw_NotificacoesLidas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE   VIEW [dbo].[vw_NotificacoesLidas] AS 
SELECT COUNT(*) AS TotalLidas FROM dbo.Notificacoes WHERE status = 1;
GO
/****** Object:  View [dbo].[vw_NotificacoesLidasPorMaquina]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

CREATE   VIEW [dbo].[vw_NotificacoesLidasPorMaquina] AS 
SELECT id_ihm, COUNT(*) AS TotalLidas 
FROM dbo.Notificacoes 
WHERE status = 1 
GROUP BY id_ihm;
GO
/****** Object:  Table [dbo].[ihms]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ihms](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[ip_address] [nvarchar](100) NOT NULL,
	[port_number] [nvarchar](255) NULL,
	[id_linha_producao] [int] NOT NULL,
	[nome_maquina] [nvarchar](50) NOT NULL,
	[acumulado] [int] NULL,
	[operador] [nvarchar](100) NULL,
	[manutentor] [nvarchar](100) NULL,
	[status_maquina] [nvarchar](50) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  View [dbo].[vw_NotificacoesPorLinha]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE   VIEW [dbo].[vw_NotificacoesPorLinha] AS 
SELECT 
    n.id, 
    n.mensagem, 
    n.data_hora, -- Renomeando dataCriacao para data_hora
    n.id_ihm, 
    n.status, -- Substituindo lida por status
    n.tipo,  
    n.titulo, 
    m.id_linha_producao 
FROM notificacoes AS n 
JOIN ihms AS m ON n.id_ihm = m.id 
WHERE m.id_linha_producao IS NOT NULL;
GO
/****** Object:  Table [dbo].[dados_receitas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[dados_receitas](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_receita] [int] NOT NULL,
	[codigo] [int] NOT NULL,
	[descricao] [nvarchar](max) NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[fila_batch_ids]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[fila_batch_ids](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[batch_id] [int] NULL,
	[status] [int] NULL,
 CONSTRAINT [PK_fila_batch_ids] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[fila_paradas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[fila_paradas](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[batch_id] [int] NULL,
	[status] [int] NULL
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[linhas_producao]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[linhas_producao](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[nome] [nvarchar](100) NOT NULL,
	[id_sistema] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[logs_registradores]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[logs_registradores](
	[id] [bigint] IDENTITY(1,1) NOT NULL,
	[id_ihm] [int] NOT NULL,
	[id_registrador] [int] NOT NULL,
	[batch_id] [bigint] NOT NULL,
	[valor_bruto] [nvarchar](255) NOT NULL,
	[datahora] [datetime] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[maqteste_status_geral]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[maqteste_status_geral](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[datahora] [datetime] NULL,
	[produzido] [int] NULL,
	[reprovado] [int] NULL,
	[total_produzido] [int] NULL,
	[operador] [nvarchar](255) NULL,
	[manutentor] [nvarchar](255) NULL,
	[engenharia] [nvarchar](255) NULL,
	[status_maquina] [nvarchar](255) NULL,
	[motivo_parada] [nvarchar](255) NULL,
	[batch_id] [int] NULL,
	[id_ihm] [int] NULL,
	[oee] [decimal](5, 2) NULL,
	[eficiencia] [decimal](5, 2) NULL,
	[qualidade] [decimal](5, 2) NULL,
	[meta] [int] NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[ordens_servico]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[ordens_servico](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[hora_abertura] [datetime] NULL,
	[hora_inicio] [datetime] NULL,
	[hora_fim] [datetime] NULL,
	[falha] [varchar](100) NULL,
	[batch_id_abertura] [int] NULL,
	[batch_id_inicio] [int] NULL,
	[batch_id_fim] [int] NULL,
	[id_ihm] [int] NULL,
	[manutentor_inicio] [varchar](100) NULL,
	[manutentor_fim] [varchar](100) NULL,
	[operador] [varchar](100) NULL,
 CONSTRAINT [PK_ordens_servico] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[paradas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[paradas](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_ihm] [int] NULL,
	[batch_id_inicio] [int] NULL,
	[batch_id_fim] [int] NULL,
	[hora_inicio] [datetime] NULL,
	[hora_fim] [datetime] NULL,
	[motivo] [varchar](100) NULL,
	[id_os] [int] NULL,
	[operador] [varchar](100) NULL,
 CONSTRAINT [PK_paradas] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[parametros]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[parametros](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_ihm] [int] NULL,
	[tempo_producao] [time](7) NULL,
	[producao_teorica] [time](7) NULL,
	[meta] [int] NULL,
 CONSTRAINT [PK_parametros] PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[receitas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[receitas](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_sistema] [int] NOT NULL,
	[nome] [nvarchar](100) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [dbo].[registradores]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[registradores](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[id_receita] [int] NULL,
	[endereco] [int] NOT NULL,
	[descricao] [nvarchar](max) NULL,
	[id_ihm] [int] NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
/****** Object:  Table [dbo].[sistemas]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[sistemas](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[Nome] [nvarchar](100) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
/****** Object:  Table [SoftIHM].[usuarios]    Script Date: 27/10/2025 14:46:23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [SoftIHM].[usuarios](
	[id] [int] IDENTITY(1,1) NOT NULL,
	[nome] [varchar](100) NOT NULL,
	[usuario] [varchar](50) NOT NULL,
	[senha] [varchar](255) NOT NULL,
	[tipo_usuario] [varchar](20) NOT NULL,
PRIMARY KEY CLUSTERED 
(
	[id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY],
UNIQUE NONCLUSTERED 
(
	[usuario] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO
ALTER TABLE [dbo].[logs_registradores] ADD  DEFAULT (getdate()) FOR [datahora]
GO
ALTER TABLE [dbo].[notificacoes] ADD  DEFAULT ((0)) FOR [status]
GO
ALTER TABLE [dbo].[notificacoes] ADD  DEFAULT (getdate()) FOR [data_hora]
GO
ALTER TABLE [dbo].[dados_receitas]  WITH CHECK ADD  CONSTRAINT [FK_dados_receitas] FOREIGN KEY([id_receita])
REFERENCES [dbo].[receitas] ([id])
GO
ALTER TABLE [dbo].[dados_receitas] CHECK CONSTRAINT [FK_dados_receitas]
GO
ALTER TABLE [dbo].[ihms]  WITH CHECK ADD  CONSTRAINT [FK_ihms_linhas_producao] FOREIGN KEY([id_linha_producao])
REFERENCES [dbo].[linhas_producao] ([id])
GO
ALTER TABLE [dbo].[ihms] CHECK CONSTRAINT [FK_ihms_linhas_producao]
GO
ALTER TABLE [dbo].[linhas_producao]  WITH CHECK ADD FOREIGN KEY([id_sistema])
REFERENCES [dbo].[sistemas] ([id])
GO
ALTER TABLE [dbo].[logs_registradores]  WITH CHECK ADD  CONSTRAINT [FK_Logs_IHMs] FOREIGN KEY([id_ihm])
REFERENCES [dbo].[ihms] ([id])
GO
ALTER TABLE [dbo].[logs_registradores] CHECK CONSTRAINT [FK_Logs_IHMs]
GO
ALTER TABLE [dbo].[logs_registradores]  WITH CHECK ADD  CONSTRAINT [FK_Logs_Registradores] FOREIGN KEY([id_registrador])
REFERENCES [dbo].[registradores] ([id])
GO
ALTER TABLE [dbo].[logs_registradores] CHECK CONSTRAINT [FK_Logs_Registradores]
GO
ALTER TABLE [dbo].[notificacoes]  WITH CHECK ADD  CONSTRAINT [FK_Notificacoes_IHMs] FOREIGN KEY([id_ihm])
REFERENCES [dbo].[ihms] ([id])
GO
ALTER TABLE [dbo].[notificacoes] CHECK CONSTRAINT [FK_Notificacoes_IHMs]
GO
ALTER TABLE [dbo].[receitas]  WITH CHECK ADD  CONSTRAINT [FK_receitas_sistemas] FOREIGN KEY([id_sistema])
REFERENCES [dbo].[sistemas] ([id])
GO
ALTER TABLE [dbo].[receitas] CHECK CONSTRAINT [FK_receitas_sistemas]
GO
ALTER TABLE [dbo].[registradores]  WITH CHECK ADD  CONSTRAINT [FK_registrador_ihm] FOREIGN KEY([id_ihm])
REFERENCES [dbo].[ihms] ([id])
GO
ALTER TABLE [dbo].[registradores] CHECK CONSTRAINT [FK_registrador_ihm]
GO
ALTER TABLE [dbo].[registradores]  WITH CHECK ADD  CONSTRAINT [FK_registradores_receitas] FOREIGN KEY([id_receita])
REFERENCES [dbo].[receitas] ([id])
GO
ALTER TABLE [dbo].[registradores] CHECK CONSTRAINT [FK_registradores_receitas]
GO
ALTER TABLE [dbo].[notificacoes]  WITH CHECK ADD CHECK  (([tipo]='Outro' OR [tipo]='Manutenção realizada' OR [tipo]='Aguardando manutenção' OR [tipo]='Erro'))
GO
ALTER TABLE [SoftIHM].[usuarios]  WITH CHECK ADD CHECK  (([tipo_usuario]='comum' OR [tipo_usuario]='admin'))
GO
USE [master]
GO
ALTER DATABASE [IHM_Testes_2] SET  READ_WRITE 
GO

/***** POPULANDO AS TABELAS *****/

USE [IHM_Testes_2]
GO
SET IDENTITY_INSERT [dbo].[sistemas] ON 

INSERT [dbo].[sistemas] ([id], [Nome]) VALUES (1, N'piloto_1')
SET IDENTITY_INSERT [dbo].[sistemas] OFF
GO
SET IDENTITY_INSERT [dbo].[linhas_producao] ON 

INSERT [dbo].[linhas_producao] ([id], [nome], [id_sistema]) VALUES (1, N'Linha Produção 1', 1)
INSERT [dbo].[linhas_producao] ([id], [nome], [id_sistema]) VALUES (2, N'Linha Produção 2', 1)
INSERT [dbo].[linhas_producao] ([id], [nome], [id_sistema]) VALUES (3, N'Linha Produção 3', 1)
INSERT [dbo].[linhas_producao] ([id], [nome], [id_sistema]) VALUES (4, N'Linha Produção 4', 1)
SET IDENTITY_INSERT [dbo].[linhas_producao] OFF
GO
SET IDENTITY_INSERT [dbo].[ihms] ON 

INSERT [dbo].[ihms] ([id], [ip_address], [port_number], [id_linha_producao], [nome_maquina], [acumulado], [operador], [manutentor], [status_maquina]) VALUES (1, N'192.168.11.89', N'502', 1, N'MAQ1', NULL, NULL, NULL, NULL)
SET IDENTITY_INSERT [dbo].[ihms] OFF
GO
SET IDENTITY_INSERT [dbo].[receitas] ON 

INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (1, 1, N'operadores')
INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (2, 1, N'manutentores')
INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (3, 1, N'engenheiros')
INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (4, 1, N'motivos_paradas')
INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (5, 1, N'falhas')
INSERT [dbo].[receitas] ([id], [id_sistema], [nome]) VALUES (6, 1, N'status_maquina')
SET IDENTITY_INSERT [dbo].[receitas] OFF
GO
SET IDENTITY_INSERT [dbo].[registradores] ON 

INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1, 1, 0, N'operador', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (2, NULL, 7024, N'produzido', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (3, NULL, 7025, N'reprovado', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1002, NULL, 7056, N'total_produzido', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1003, 2, 1000, N'manutentor', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1004, 3, 1500, N'engenheiro', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1005, 6, 2000, N'status_maquina', 1)
INSERT [dbo].[registradores] ([id], [id_receita], [endereco], [descricao], [id_ihm]) VALUES (1006, 4, 2000, N'motivo_parada', 1)
SET IDENTITY_INSERT [dbo].[registradores] OFF
GO
SET IDENTITY_INSERT [dbo].[dados_receitas] ON 

INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1, 1, 1, N'Antonia Tomaz')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (2, 1, 2, N'Janice Souza')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (3, 1, 3, N'Daiane Godofredo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (4, 1, 5, N'Claudia Almeida')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (5, 1, 7, N'Sueli Ferreira')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (6, 1, 22, N'Janete Azevedo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (7, 1, 23, N'Andreia Vilela')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (8, 1, 24, N'Joana Darc')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (9, 1, 26, N'Carlos Cesar')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (10, 1, 28, N'Katia da Silva')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (11, 1, 34, N'Crisleide Oliveira')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (12, 1, 45, N'Sueli Pereira')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (13, 1, 46, N'Dislene da Silva')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (14, 1, 47, N'Luciana Ribeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (15, 1, 48, N'Luziete Ribeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (16, 1, 49, N'Vanessa Michael')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (17, 1, 50, N'Rosanfega de Jesus')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (18, 1, 11, N'Clesia Maria')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (19, 1, 6, N'Doralice')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (20, 1, 48, N'Luziete')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (21, 1, 53, N'Luciano Barbeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1002, 2, 100, N'Hugo Cesar')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1003, 2, 101, N'Cleberson Sarmento')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1004, 2, 102, N'Tiago Bastos')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1005, 2, 103, N'Mateus Braga')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1006, 2, 104, N'Carlos Eduardo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1007, 2, 105, N'Rafael Rodrigues')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1008, 2, 106, N'Alexandre Lima')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1009, 2, 107, N'Wagner de Souza')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1010, 2, 108, N'Roberto Satori')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1011, 2, 109, N'Marcus Ribeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1012, 2, 110, N'Marcelo Ricardo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1013, 2, 111, N'Fernando Jose')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1014, 2, 112, N'Edson da Luz')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1015, 2, 113, N'Willian Marcos')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1016, 2, 114, N'Johnny Neris')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1017, 2, 115, N'Jose Carlos')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1018, 2, 116, N'Gean Cardoso')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1019, 2, 117, N'Ricardo Macena')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1020, 2, 118, N'Diego Jose')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1021, 2, 119, N'Maicon Ribeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1022, 2, 120, N'Flavio Balera')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1023, 2, 121, N'Gildasio Reis')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1024, 2, 122, N'Jonas Mendes')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1025, 3, 500, N'Marcelo Francelino')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1026, 3, 501, N'Willian Correa')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1027, 3, 502, N'Yanke Vinicius')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1028, 3, 503, N'Michael dos Santos')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1029, 3, 504, N'Marcos Guimaraes')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1030, 3, 505, N'Fabricio Santos')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1031, 3, 506, N'Marcelo Ardito')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1032, 3, 507, N'Antonia Tomaz')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1033, 3, 508, N'Janice Souza')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1034, 3, 509, N'Luciano Ribeiro')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1035, 4, 1, N'Passar Padrao')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1036, 4, 2, N'troca da caixa de saida')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1037, 4, 3, N'abastecimento de material')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1038, 4, 4, N'Limpeza geral da maquina ')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1039, 4, 5, N'DDS e/ou Ginastica')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1040, 4, 6, N'Refeicao')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1041, 4, 7, N'Troca de operador')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1042, 4, 8, N'Ausencia do posto de trabalho')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1043, 4, 9, N'Reunião')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1044, 4, 10, N'Disco enroscado na alimentador')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1045, 4, 11, N'Borboleta enroscada na alimentador')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1046, 4, 12, N'Registro enroscado na alimentador')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1047, 4, 13, N'Inspecao de torque')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1048, 4, 14, N'Falta de material para producao')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1049, 4, 15, N'Treinamento ')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1050, 4, 16, N'Fora de turno ')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1051, 4, 17, N'Reset da maquina')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1052, 4, 18, N'Aguardando qualidade')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1053, 4, 19, N'Testes de Qualidade')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1054, 4, 20, N'Limpeza de Vedante ')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1055, 4, 21, N'abastecimento de vedante')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1056, 4, 22, N'Falha no ciclo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1057, 4, 23, N'Baixa Pressao de Ar')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1058, 4, 24, N'Ajuste')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1059, 6, 0, N'Máquina sem produção')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1060, 6, 1, N'Máquina liberada')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1061, 6, 2, N'Manutenção')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1062, 6, 3, N'Motivo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1063, 6, 4, N'Aguardando eletricista')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1064, 6, 5, N'Aguardando mecânico')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1065, 6, 6, N'Máquina sem produção')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1066, 6, 7, N'Máquina produzindo')
INSERT [dbo].[dados_receitas] ([id], [id_receita], [codigo], [descricao]) VALUES (1067, 4, 3300, N'Falha teste')
SET IDENTITY_INSERT [dbo].[dados_receitas] OFF
GO
SET IDENTITY_INSERT [dbo].[parametros] ON 

INSERT [dbo].[parametros] ([id], [id_ihm], [tempo_producao], [producao_teorica], [meta]) VALUES (1, 1, CAST(N'07:00:00' AS Time), CAST(N'00:00:15' AS Time), 50)
SET IDENTITY_INSERT [dbo].[parametros] OFF
GO