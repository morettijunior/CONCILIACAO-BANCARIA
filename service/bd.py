from decimal import Decimal
import fdb
from .ofx import data_final, data_inicial


from decimal import Decimal
import fdb
from .ofx import data_final, data_inicial


def consultar_extrato(banco_esperado, caminho_ofx, caminho_bd):
  dt_inicio = data_inicial(banco_esperado, caminho_ofx)
  dt_fim = data_final(banco_esperado, caminho_ofx)

  if not dt_inicio or not dt_fim:
    print(
        '[ERRO] Não foi possível obter as datas inicial e final do arquivo OFX.'
    )
    return []

  conexao = fdb.connect(
      dsn=caminho_bd,
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()

  try:
    sql = """
            SELECT DATA, VALOR, HISTORICO 
            FROM FEXTRATO 
            WHERE DATA BETWEEN ? AND ?
        """
    cursor.execute(sql, (dt_inicio, dt_fim))
    registros = cursor.fetchall()

    extrato_bd = []
    for reg in registros:
      data_bd, valor_bd, historico_bd = reg
      extrato_bd.append({
          'data': data_bd,
          'valor': Decimal(str(valor_bd)),
          'historico': str(historico_bd or '').strip(),
      })

    return extrato_bd

  except Exception as e:
    print(f'[ERRO] Falha ao consultar o extrato no banco de dados: {e}')
    return []
  finally:
    cursor.close()
    conexao.close()


from decimal import Decimal
import fdb


def saldo_sistema(banco_esperado, caminho_bd, data_final=None):
  """Calcula o saldo somando a coluna VALOR da tabela FEXTRATO

  filtrando pelo CODCAIXA e opcionalmente limitando até a DATA FINAL.
  """
  codcaixa = "02" if str(banco_esperado) == "748" else "07"

  conexao = fdb.connect(
      dsn=caminho_bd,
      user="SYSDBA",
      password="masterkey",
      charset="ISO8859_1",
  )
  cursor = conexao.cursor()

  total_saldo = Decimal("0.00")
  try:
    if data_final:
      sql = """
                SELECT SUM(VALOR) 
                FROM FEXTRATO 
                WHERE CODCAIXA = ? AND DATA <= ?
            """
      cursor.execute(sql, (codcaixa, data_final))
    else:
      sql = """
                SELECT SUM(VALOR) 
                FROM FEXTRATO 
                WHERE CODCAIXA = ?
            """
      cursor.execute(sql, (codcaixa,))

    res = cursor.fetchone()

    if res and res[0] is not None:
      total_saldo = Decimal(str(res[0]))

  except Exception as e:
    print(f"[ERRO BD] Falha ao calcular saldo do sistema: {e}")
  finally:
    cursor.close()
    conexao.close()

  return total_saldo

def listar_regras():
  """Retorna todas as regras cadastradas na tabela TREGRAOFX."""
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
    return cursor.fetchall()
  except Exception as e:
    print(f'[ERRO] Falha ao listar regras: {e}')
    return []
  finally:
    cursor.close()
    conexao.close()


def inserir_regra(codcfo, ccusto, historico, historico_busca):
  """Insere uma nova regra no banco."""
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()
  try:
    sql = """
            INSERT INTO TREGRAOFX (CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA)
            VALUES (?, ?, ?, ?)
        """
    cursor.execute(
        sql, (codcfo.strip(), ccusto.strip(), historico.strip(), historico_busca.strip().upper())
    )
    conexao.commit()
    return True
  except Exception as e:
    conexao.rollback()
    print(f'[ERRO] Falha ao inserir regra: {e}')
    return False
  finally:
    cursor.close()
    conexao.close()


def excluir_regra(historico_busca):
  """Exclui uma regra com base no histórico de busca."""
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()
  try:
    sql = 'DELETE FROM TREGRAOFX WHERE HISTORICO_BUSCA = ?'
    cursor.execute(sql, (historico_busca.strip().upper(),))
    conexao.commit()
    return True
  except Exception as e:
    conexao.rollback()
    print(f'[ERRO] Falha ao excluir regra: {e}')
    return False
  finally:
    cursor.close()
    conexao.close()