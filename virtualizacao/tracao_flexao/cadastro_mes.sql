-- ============================================================================
-- Cadastro da máquina Tração e Flexão no MES
-- Aponta para o mock Modbus TCP (clp/mock_clp.py) em 127.0.0.1:502.
-- Na Fase 7 (máquina real), troque só o tx_ip_address/tx_port_number para o
-- gateway RS485->TCP. Endereços: nu_endereco = 4096 + D ; REAL = 2 words.
-- Idempotente: pode rodar de novo sem duplicar.
-- ============================================================================
SET NOCOUNT ON;

-- 0) Garante a coluna de tipo de registrador (1=WORD 16bit, 2=REAL 32bit)
IF COL_LENGTH('dbo.tb_registrador', 'nu_qtd_words') IS NULL
    ALTER TABLE dbo.tb_registrador ADD nu_qtd_words INT NOT NULL DEFAULT 1;
GO

DECLARE @id_linha INT, @id_ihm INT;

-- 1) Linha de produção
SELECT @id_linha = id_linha_producao FROM dbo.tb_linha_producao WHERE tx_name = N'Ensaios Mecânicos';
IF @id_linha IS NULL
BEGIN
    INSERT INTO dbo.tb_linha_producao (tx_name) VALUES (N'Ensaios Mecânicos');
    SET @id_linha = SCOPE_IDENTITY();
END

-- 2) Máquina (IHM) apontando para o mock Modbus TCP
SELECT @id_ihm = id_ihm FROM dbo.tb_ihm WHERE tx_name = N'Tração e Flexão';
IF @id_ihm IS NULL
BEGIN
    INSERT INTO dbo.tb_ihm (tx_ip_address, tx_port_number, id_linha_producao, tx_name)
    VALUES ('127.0.0.1', '502', @id_linha, N'Tração e Flexão');
    SET @id_ihm = SCOPE_IDENTITY();
END

-- tipo de máquina (só se a coluna já existir — é adicionada pelo _ensure_schema da API)
IF COL_LENGTH('dbo.tb_ihm', 'tx_tipo_maquina') IS NOT NULL
    UPDATE dbo.tb_ihm SET tx_tipo_maquina = N'Tração e Flexão' WHERE id_ihm = @id_ihm;

-- 3) Registradores (só insere se ainda não houver nenhum para esta máquina)
IF NOT EXISTS (SELECT 1 FROM dbo.tb_registrador WHERE id_ihm = @id_ihm)
BEGIN
    INSERT INTO dbo.tb_registrador (nu_endereco, tx_descricao, id_ihm, nu_qtd_words) VALUES
    -- ---- Ensaio de TRAÇÃO (bloco D3000, REAL = 2 words) ----
    (7096, N'tracao_tensao_mpa',           @id_ihm, 2),  -- D3000
    (7098, N'tracao_modulo_elast_mpa',     @id_ihm, 2),  -- D3002
    (7100, N'tracao_tensao_max_mpa',       @id_ihm, 2),  -- D3004
    (7102, N'tracao_deformacao',           @id_ihm, 2),  -- D3006
    (7104, N'tracao_alongamento_pct',      @id_ihm, 2),  -- D3008
    (7106, N'tracao_deslocamento_mm',      @id_ihm, 2),  -- D3010
    (7108, N'tracao_forca_n',              @id_ihm, 2),  -- D3012
    -- ---- Ensaio de FLEXÃO (bloco D3020, REAL = 2 words) ----
    (7116, N'flexao_forca_n',              @id_ihm, 2),  -- D3020
    (7118, N'flexao_momento_inercia',      @id_ihm, 2),  -- D3022
    (7120, N'flexao_tensao_mpa',           @id_ihm, 2),  -- D3024
    (7122, N'flexao_deformacao_superf',    @id_ihm, 2),  -- D3026
    (7124, N'flexao_modulo_mpa',           @id_ihm, 2),  -- D3028
    (7126, N'flexao_momento_maximo',       @id_ihm, 2),  -- D3030
    (7128, N'flexao_deslocamento_mm',      @id_ihm, 2),  -- D3032
    -- ---- Ao vivo / extras ----
    (4186, N'forca_atual_word',            @id_ihm, 1),  -- D90  (WORD)
    (4814, N'forca_maxima_pico_n',         @id_ihm, 2),  -- D718 (REAL)
    (4124, N'r2_correlacao',               @id_ihm, 2);  -- D28  (REAL)
END

SELECT @id_ihm AS id_ihm_cadastrada, @id_linha AS id_linha;
GO
