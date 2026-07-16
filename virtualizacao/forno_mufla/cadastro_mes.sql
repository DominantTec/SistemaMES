-- ============================================================================
-- Cadastro da máquina Forno Mufla no MES
-- ----------------------------------------------------------------------------
-- Fonte de dados: mock_clp_forno.py (servidor Modbus TCP em Python, porta 5030)
-- rodando no HOST Windows. NÃO há CLP nem ISPSoft nesta máquina — a simulação
-- inteira vive no mock, e o coletor lê exatamente como leria um CLP real.
--
-- IMPORTANTE — tx_ip_address = 'host.docker.internal':
--   o coletor (src/monitoramento) roda DENTRO de um container. '127.0.0.1' ali
--   é o próprio container, não a sua máquina. host.docker.internal é o nome que
--   o Docker dá ao host. (No compose, o serviço monitoramento tem
--   extra_hosts: host.docker.internal:host-gateway para funcionar também no Linux.)
--   Na Fase 7 (CLP físico): troque só tx_ip_address/tx_port_number.
--
-- Contrato dos registradores (ver ../clp/mock_clp_forno.py):
--   * D(n) -> holding register n DIRETO (sem o offset 4096 da convenção DVP)
--   * words 16 bits SEM SINAL, escaladas -> nu_divisor devolve a unidade
--   * nada negativo: a taxa de aquecimento (°C/min) é derivada na API, não é registrador
--
-- Idempotente: pode rodar quantas vezes quiser. Só recria os registradores se o
-- mapa estiver diferente/ausente, e nesse caso limpa os logs antigos (escalas
-- incompatíveis não podem se misturar na mesma série).
-- ============================================================================
SET NOCOUNT ON;

-- 0) Colunas de escala (1=WORD/2=REAL; divisor). Mesmas usadas pela Tração.
IF COL_LENGTH('dbo.tb_registrador', 'nu_qtd_words') IS NULL
    ALTER TABLE dbo.tb_registrador ADD nu_qtd_words INT NOT NULL DEFAULT 1;
IF COL_LENGTH('dbo.tb_registrador', 'nu_divisor') IS NULL
    ALTER TABLE dbo.tb_registrador ADD nu_divisor DECIMAL(18,4) NOT NULL DEFAULT 1;
GO

DECLARE @id_linha INT, @id_ihm INT;

-- 1) Linha de produção (mesma dos ensaios)
SELECT @id_linha = id_linha_producao FROM dbo.tb_linha_producao WHERE tx_name = N'Ensaios Mecânicos';
IF @id_linha IS NULL
BEGIN
    INSERT INTO dbo.tb_linha_producao (tx_name) VALUES (N'Ensaios Mecânicos');
    SET @id_linha = SCOPE_IDENTITY();
END

-- 2) Máquina (IHM)
SELECT @id_ihm = id_ihm FROM dbo.tb_ihm WHERE tx_name = N'Forno Mufla';
IF @id_ihm IS NULL
BEGIN
    INSERT INTO dbo.tb_ihm (tx_ip_address, tx_port_number, id_linha_producao, tx_name)
    VALUES ('host.docker.internal', '5030', @id_linha, N'Forno Mufla');
    SET @id_ihm = SCOPE_IDENTITY();
END
ELSE
BEGIN
    UPDATE dbo.tb_ihm
       SET tx_ip_address = 'host.docker.internal', tx_port_number = '5030'
     WHERE id_ihm = @id_ihm;
END

-- tipo de máquina: é o que faz o MES escolher a tela do forno (registry do front
-- e get_forno_snapshot na API casam por este texto).
IF COL_LENGTH('dbo.tb_ihm', 'tx_tipo_maquina') IS NOT NULL
    UPDATE dbo.tb_ihm SET tx_tipo_maquina = N'Forno Mufla' WHERE id_ihm = @id_ihm;

-- 3) Registradores — recria se o mapa não bater com o esperado.
--    O marcador é 'etapa' (o registrador mais novo do mapa): cadastros anteriores,
--    sem ele, são recriados. Pare o coletor antes de rodar — se ele inserir logs
--    entre o DELETE dos logs e o dos registradores, a FK barra e o mapa fica misturado.
IF NOT EXISTS (
    SELECT 1 FROM dbo.tb_registrador
     WHERE id_ihm = @id_ihm AND tx_descricao = N'etapa'
)
BEGIN
    DELETE FROM dbo.tb_log_registrador WHERE id_ihm = @id_ihm;
    DELETE FROM dbo.tb_registrador     WHERE id_ihm = @id_ihm;

    INSERT INTO dbo.tb_registrador (nu_endereco, tx_descricao, id_ihm, nu_qtd_words, nu_divisor) VALUES
    -- ---- Estado ----
    (0,  N'modo',            @id_ihm, 1, 1),      -- 0 ocioso / 1 aquecendo / 2 patamar / 3 resfriando
    (1,  N'rodando',         @id_ihm, 1, 1),      -- 0/1
    (2,  N'ventoinha',       @id_ihm, 1, 1),      -- 0/1 exaustão ligada
    (3,  N'patamar',         @id_ihm, 1, 1),      -- 0/1 dentro da tolerância do setpoint
    -- etapa do ensaio: só avança, nunca volta -> é o que desenha a linha do tempo na tela
    (4,  N'etapa',           @id_ihm, 1, 1),      -- 0 ocioso 1 aquec 2 queima 3 patamar 4 concluído 5 resfria
    -- ---- Térmico ----
    (10, N'temperatura_c',   @id_ihm, 1, 10),     -- x10  -> °C (câmara)
    (12, N'temp_amostra_c',  @id_ihm, 1, 10),     -- x10  -> °C (corpo de prova)
    (14, N'setpoint_c',      @id_ihm, 1, 10),     -- x10  -> °C
    (16, N'potencia_w',      @id_ihm, 1, 1),      --      -> W
    (18, N'duty',            @id_ihm, 1, 1000),   -- x1000 -> 0..1
    (20, N'energia_kj',      @id_ihm, 1, 1),      --      -> kJ acumulados
    -- ---- Balança / teor de betume (ensaio de ignição: a massa perdida É o betume) ----
    (30, N'peso_inicial_g',  @id_ihm, 1, 10),     -- x10  -> g
    (32, N'peso_atual_g',    @id_ihm, 1, 10),     -- x10  -> g
    (34, N'perda_massa_pct', @id_ihm, 1, 100),    -- x100 -> % (= teor de betume queimado)
    (36, N'taxa_betume',     @id_ihm, 1, 1000),   -- x1000 -> 0..1 (taxa de queima; 0 = betume esgotado)
    -- ---- Tempo de ensaio (zera a cada ensaio -> delimita a curva) ----
    (40, N'tempo_s',         @id_ihm, 1, 1);      --      -> s
END

SELECT @id_ihm AS id_ihm_cadastrada, @id_linha AS id_linha,
       (SELECT COUNT(*) FROM dbo.tb_registrador WHERE id_ihm = @id_ihm) AS qtd_registradores;
GO
