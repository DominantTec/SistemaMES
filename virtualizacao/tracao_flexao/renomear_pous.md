
# Renomeação padronizada dos POUs / FBs (checklist)

> Aplicar no ISPSoft (botão direito no item da árvore → **Rename**). O ISPSoft atualiza as
> chamadas automaticamente — rode um **Compile** depois pra conferir. **Endereços `D`/`M` NÃO
> mudam** → o mapa Modbus e o cadastro no MES continuam válidos.
>
> Convenção: `AREA_DESCRICAO`, MAIÚSCULAS, **sem acento**, PT. Prefixos:
> `COM_`=comunicação · `CEL_`=célula/força · `MOT_`=motor/movimento · `ENS_`=lógica do ensaio ·
> `CAL_`=cálculos · `FB_`=function blocks.

## Programas
| ☐ | Atual | Novo |
|:--:|-------|------|
| ☐ | `Comunicação_Modubus_485` | `COM_MODBUS_485` |
| ☐ | `Celula_de_Carga` | `CEL_LEITURA_CARGA` |
| ☐ | `Conversão_de_Unidades` | `CEL_CONV_UNIDADES` |
| ☐ | `CON_DIST_PROG` | `MOT_DIST_PROGRAMADA` |
| ☐ | `CONV_DISTAN_REAL` | `MOT_DIST_REAL` |
| ☐ | `CONTROL_MOTOR_PASSO` | `MOT_CONTROLE_PASSO` |
| ☐ | `NOVO_VELOCIDADE` *(disabled)* | `MOT_VELOCIDADE_AMOSTRA` |
| ☐ | `Analise_de_deformação_elast` | `ENS_VEL_ELASTICA` |
| ☐ | `Trygers` | `ENS_TRIGGER_CAPTURA` |
| ☐ | `Parada_Ruptura` | `ENS_PARADA_RUPTURA` |
| ☐ | `Limite_da_Celula_Carga` *(disabled)* | `ENS_SOBRECARGA` |
| ☐ | `HOLD_TARA` | `CAL_PICOS_TARA` |
| ☐ | `Formulas` | `CAL_RESULTADOS` |
| ☐ | `MÓDULO_DE_FLEXÃO_PARCIAL` | `CAL_MODULO_FLEXAO_REG` |

## Function Blocks
| ☐ | Atual | Novo |
|:--:|-------|------|
| — | `DFB_COM2_Protocol` | **não renomear** (FB de biblioteca Delta) |
| ☐ | `CONVERTE_PARA_NEWTON` | `FB_CONV_NEWTON` |
| ☐ | `MOMENTO_INERCIA_DA_SEÇÃO` | `FB_MOMENTO_INERCIA` |
| ☐ | `TENSÃO_DE_FLEXÃO` | `FB_TENSAO_FLEXAO` |
| ☐ | `DEFORMAÇÃO_SUPERFICIAL` | `FB_DEFORM_SUPERFICIAL` |
| ☐ | `MÓDULO_DE_FLEXÃO` | `FB_MODULO_FLEXAO` |
| ☐ | `MOMENTO_MAXIMO` | `FB_MOMENTO_MAXIMO` |
| ☐ | `SOMATORIAS` | `FB_SOMATORIAS` |
| ☐ | `Regrassão_Linear_M` | `FB_REGRESSAO_LINEAR` |
| ☐ | `Coeficinete_de_correlação` | `FB_COEF_CORRELACAO` |
| ☐ | `NOVO_MODULO_DE_FLEXÃO` | `FB_MODULO_FLEXAO_REG` |

> Quando terminar, me avisa que eu atualizo os nomes nos `.md` (docs + índice) pra bater.
