-- ============================================================================
-- Re-cadastro da máquina Tração e Flexão no MES apontando para o AS300
-- ----------------------------------------------------------------------------
-- Fonte de dados: CPU AS332T rodando no AS300 Simulator (ISPSoft), Modbus TCP
-- em 127.0.0.1:10002. Contrato do AS (diferente do mock DVP):
--   * D(n) -> holding register n DIRETO (sem o offset 4096 do mock)
--   * inteiros 16 bits (nu_qtd_words = 1)
--   * valores escalados -> nu_divisor devolve a unidade de engenharia
--
-- Mapa AS (ver twin3d/bridge_as.py):
--   D0  modo(0/1/2)   D1  rodando   D2  ruptura
--   D10 desloc x100mm D12 forca N   D14 tensao x10MPa  D16 along x100%
--   D18 modulo MPa    D20 forca_max N  D22 R2 x1000
--
-- Roda em paralelo ao twin: Modbus TCP aceita bridge_as.py + coletor lendo juntos.
-- Na Fase 7 (AS físico): troque só tx_ip_address/tx_port_number (Modbus provável na 502).
--
-- Idempotente: só faz a troca destrutiva se a máquina ainda estiver no cadastro
-- do mock (registradores com nu_endereco >= 4096). Re-rodar depois não apaga
-- dados já coletados do AS.
-- ============================================================================
SET NOCOUNT ON;

-- 0) Garante as colunas de escala (1=WORD/2=REAL; divisor de escala)
IF COL_LENGTH('dbo.tb_registrador', 'nu_qtd_words') IS NULL
    ALTER TABLE dbo.tb_registrador ADD nu_qtd_words INT NOT NULL DEFAULT 1;
IF COL_LENGTH('dbo.tb_registrador', 'nu_divisor') IS NULL
    ALTER TABLE dbo.tb_registrador ADD nu_divisor DECIMAL(18,4) NOT NULL DEFAULT 1;
GO

DECLARE @id_linha INT, @id_ihm INT;

-- 1) Linha de produção
SELECT @id_linha = id_linha_producao FROM dbo.tb_linha_producao WHERE tx_name = N'Ensaios Mecânicos';
IF @id_linha IS NULL
BEGIN
    INSERT INTO dbo.tb_linha_producao (tx_name) VALUES (N'Ensaios Mecânicos');
    SET @id_linha = SCOPE_IDENTITY();
END

-- 2) Máquina (IHM) — cria se não existir, e re-aponta para o AS300 Simulator
SELECT @id_ihm = id_ihm FROM dbo.tb_ihm WHERE tx_name = N'Tração e Flexão';
IF @id_ihm IS NULL
BEGIN
    INSERT INTO dbo.tb_ihm (tx_ip_address, tx_port_number, id_linha_producao, tx_name)
    VALUES ('127.0.0.1', '10002', @id_linha, N'Tração e Flexão');
    SET @id_ihm = SCOPE_IDENTITY();
END
ELSE
BEGIN
    UPDATE dbo.tb_ihm
       SET tx_ip_address = '127.0.0.1', tx_port_number = '10002'
     WHERE id_ihm = @id_ihm;
END

-- tipo de máquina (só se a coluna já existir — é adicionada pelo _ensure_schema da API)
IF COL_LENGTH('dbo.tb_ihm', 'tx_tipo_maquina') IS NOT NULL
    UPDATE dbo.tb_ihm SET tx_tipo_maquina = N'Tração e Flexão' WHERE id_ihm = @id_ihm;

-- 3) Registradores — troca do contrato mock (offset 4096) para o contrato AS.
--    Só executa se ainda houver registradores do mock (nu_endereco >= 4096) OU
--    se a máquina estiver sem registradores. Assim re-rodar não apaga dados do AS.
IF NOT EXISTS (SELECT 1 FROM dbo.tb_registrador WHERE id_ihm = @id_ihm)
   OR EXISTS (SELECT 1 FROM dbo.tb_registrador WHERE id_ihm = @id_ihm AND nu_endereco >= 4096)
BEGIN
    -- Limpa logs antigos (mock) desta máquina: FK impede apagar registrador antes,
    -- e os valores em escala REAL do mock não são comparáveis com a escala do AS.
    DELETE FROM dbo.tb_log_registrador WHERE id_ihm = @id_ihm;
    DELETE FROM dbo.tb_registrador      WHERE id_ihm = @id_ihm;

    INSERT INTO dbo.tb_registrador (nu_endereco, tx_descricao, id_ihm, nu_qtd_words, nu_divisor) VALUES
    -- ---- Estado do ensaio ----
    (0,  N'modo',               @id_ihm, 1, 1),      -- 0 idle / 1 tração / 2 flexão
    (1,  N'rodando',            @id_ihm, 1, 1),      -- 0/1
    (2,  N'ruptura',            @id_ihm, 1, 1),      -- 0/1
    -- ---- Telemetria (inteiros escalados -> unidade de engenharia) ----
    (10, N'deslocamento_mm',    @id_ihm, 1, 100),    -- x100  -> mm
    (12, N'forca_n',            @id_ihm, 1, 1),      --       -> N
    (14, N'tensao_mpa',         @id_ihm, 1, 10),     -- x10   -> MPa
    (16, N'alongamento_pct',    @id_ihm, 1, 100),    -- x100  -> %
    (18, N'modulo_mpa',         @id_ihm, 1, 1),      --       -> MPa
    (20, N'forca_max_n',        @id_ihm, 1, 1),      --       -> N
    (22, N'r2_correlacao',      @id_ihm, 1, 1000);   -- x1000 -> 0..1
END

SELECT @id_ihm AS id_ihm_cadastrada, @id_linha AS id_linha,
       (SELECT COUNT(*) FROM dbo.tb_registrador WHERE id_ihm = @id_ihm) AS qtd_registradores;
GO
