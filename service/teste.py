import fdb


def ajustar_ccusto_e_inserir_regras():
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()

  try:
    print('Alterando o tamanho da coluna CCUSTO para VARCHAR(20)...')
    cursor.execute('ALTER TABLE TREGRAOFX ALTER COLUMN CCUSTO TYPE VARCHAR(20)')
    conexao.commit()
    print('Coluna CCUSTO alterada com sucesso!')

  except Exception as e:
    conexao.rollback()
    print(f'[AVISO] Erro ao alterar CCUSTO: {e}')

  regras = [
      ('C01737', '3.12.002', 'PGTO TAXA IOF', 'IOF'),
      ('C01737', '3.12.003', 'PGTO JUROS LIMITE CHEQUE ESPECIAL', 'CH.ESP'),
      ('C01737', '3.12.010', 'INTEGRACAO CAPITAL SICREDI', 'CAPITAL SUBSCRITO'),
      ('C01737', '3.12.008', 'PGTO MENSALIDADE SICREDI', 'CESTA DE RELACIONAMENTO'),
      ('C01737', '3.12.001', 'TARIFA PIX SICREDI', 'TARIFA PIX'),
  ]

  try:
    sql = """
            INSERT INTO TREGRAOFX (CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA)
            VALUES (?, ?, ?, ?)
        """
    cursor.executemany(sql, regras)
    conexao.commit()
    print(f'{len(regras)} regras inseridas com sucesso na tabela TREGRAOFX!')

  except Exception as e:
    conexao.rollback()
    print(f'[ERRO] Falha ao inserir as regras: {e}')
  finally:
    cursor.close()
    conexao.close()


if __name__ == '__main__':
  ajustar_ccusto_e_inserir_regras()