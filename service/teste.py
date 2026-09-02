import fdb

# Ajuste para o caminho real do seu .fdb
caminho_banco = r'C:/Users/rondo/Desktop/Phyton/BD FIREBIRD/TGA.FDB'

conexao = fdb.connect(
    dsn=caminho_banco, user='SYSDBA', password='masterkey', charset='ISO8859_1'
)
cursor = conexao.cursor()

print('--- TODOS OS REGISTROS DO CAIXA 3 NÃO COMPENSADOS ---')
cursor.execute("""
    IDEXTRATO, CODCAIXA, VALOR, CODFORMA, COMPENSADO, HISTORICO, NUMERODOCUMENTO 
    FROM FEXTRATO 
    WHERE CODCAIXA = 3 AND COMPENSADO = 'F'
""")
registros = cursor.fetchall()

if not registros:
  print('Nenhum registro encontrado com CODCAIXA = 3 e COMPENSADO = F.')
  # Vamos tentar sem filtro de caixa para ver o CODCAIXA real
  cursor.execute("""
        SELECT FIRST 20 IDEXTRATO, CODCAIXA, VALOR, CODFORMA, COMPENSADO, HISTORICO 
        FROM FEXTRATO 
        WHERE COMPENSADO = 'F' ORDER BY IDEXTRATO DESC
    """)
  print('\nÚltimos 20 registros não compensados em qualquer caixa:')
  for r in cursor.fetchall():
    print(r)
else:
  for r in registros:
    print(r)

cursor.close()
conexao.close()