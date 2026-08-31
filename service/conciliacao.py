from datetime import datetime
from decimal import Decimal
import fdb


def comparar_listas(extrato_ofx, extrato_bd):
  ofx_pendentes = list(extrato_ofx)
  bd_pendentes = list(extrato_bd)

  extrato_conciliado = []
  extrato_nao_conciliado = []

  for item_ofx in extrato_ofx:
    encontrado = False
    for item_bd in bd_pendentes:
      if (
          item_ofx['data'] == item_bd['data']
          and item_ofx['valor'] == item_bd['valor']
      ):
        extrato_conciliado.append({'ofx': item_ofx, 'bd': item_bd})
        bd_pendentes.remove(item_bd)
        encontrado = True
        break

    if not encontrado:
      extrato_nao_conciliado.append({'origem': 'OFX', 'item': item_ofx})

  for item_bd in bd_pendentes:
    extrato_nao_conciliado.append({'origem': 'BD', 'item': item_bd})

  return extrato_conciliado, extrato_nao_conciliado


def inserir_itens(banco_esperado, extrato_nao_conciliado, extrato_conciliado):
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()

  try:
    cursor.execute(
        'SELECT CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA FROM TREGRAOFX'
    )
    regras = cursor.fetchall()

    itens_para_processar = list(extrato_nao_conciliado)

    for item_nao_conc in itens_para_processar:
      if item_nao_conc['origem'] != 'OFX':
        continue

      dados_item = item_nao_conc['item']
      historico_item = str(dados_item['historico']).upper()

      regra_encontrada = None
      for regra in regras:
        c_cfo, c_custo, hist_regra, hist_busca = regra
        if hist_busca and hist_busca.upper() in historico_item:
          regra_encontrada = {
              'CODCFO': c_cfo,
              'CCUSTO': c_custo,
              'HISTORICO': hist_regra,
          }
          break

      if regra_encontrada:
        cursor.execute('SELECT MAX(IDLAN) FROM FLAN')
        res_lan = cursor.fetchone()
        novo_idlan = (res_lan[0] or 0) + 1

        cursor.execute('SELECT MAX(IDEXTRATO) FROM FEXTRATO')
        res_ext = cursor.fetchone()
        novo_idextrato = (res_ext[0] or 0) + 1

        valor_item = dados_item['valor']
        pagrec = 'P' if valor_item < 0 else 'R'
        codcaixa = '02' if str(banco_esperado) == '748' else '07'
        valor_abs = abs(Decimal(str(valor_item)))
        data_item = dados_item['data']
        agora = datetime.now()

        sql_flan = """
                INSERT INTO FLAN (
                    IDLAN, CODEMPRESA, CODFILIAL, CODCFO, CODTDO, NUMERODOCUMENTO, 
                    PARCELA, PAGREC, CCUSTO, DATAVENCIMENTO, DATAEMISSAO, 
                    DATABAIXA, DATAPREVBAIXA, HISTORICO, CODMOEVALORORIGINAL, 
                    CODCAIXA, VALORORIGINAL, VALORBAIXADO, STATUSLAN, 
                    DATADIGITACAO, NPARCELA, CODFORMA, HISTORICOBAIXA, DATADIGITACAOBAIXA
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        cursor.execute(
            sql_flan,
            (
                novo_idlan,
                1,
                1,
                regra_encontrada['CODCFO'],
                'DP',
                'AUTOS',
                1,
                pagrec,
                regra_encontrada['CCUSTO'],
                data_item,
                data_item,
                data_item,
                data_item,
                regra_encontrada['HISTORICO'],
                'R$',
                codcaixa,
                valor_abs,
                valor_abs,
                'B',
                agora,
                1,
                '01',
                regra_encontrada['HISTORICO'],
                agora,
            ),
        )

        sql_fextrato = """
                INSERT INTO FEXTRATO (
                    IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, VALOR, IDLAN, 
                    COMPENSADO, HISTORICO, NUMERODOCUMENTO, DATACOMPENSACAO, 
                    DATA, DATADIGITACAO, CCUSTO, CODFORMA, DATAVENCIMENTO, 
                    CODCFO, CONCILIADO, INTEGRADONFE
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        cursor.execute(
            sql_fextrato,
            (
                novo_idextrato,
                1,
                1,
                codcaixa,
                valor_item,
                novo_idlan,
                'T',
                regra_encontrada['HISTORICO'],
                'AUTOS',
                data_item,
                data_item,
                agora,
                regra_encontrada['CCUSTO'],
                '01',
                data_item,
                regra_encontrada['CODCFO'],
                'F',
                'F',
            ),
        )

        conexao.commit()

        extrato_nao_conciliado.remove(item_nao_conc)
        extrato_conciliado.append({
            'ofx': dados_item,
            'bd': {
                'data': data_item,
                'valor': valor_item,
                'historico': regra_encontrada['HISTORICO'],
            },
        })
        print(
            f"[REGRA APLICADA] Data: {data_item.strftime('%d/%m/%Y')} |"
            f" '{dados_item['historico']}' -> Inserido no FLAN/FEXTRATO (IDLAN:"
            f' {novo_idlan})'
        )

  except Exception as e:
    conexao.rollback()
    print(f'[ERRO] Falha ao processar regras: {e}')
  finally:
    cursor.close()
    conexao.close()