import fdb

conexao = fdb.connect(
    dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
    user='SYSDBA',
    password='masterkey',
    charset='ISO8859_1',
)
cursor = conexao.cursor()

# Soma direta dos valores do extrato para o Caixa 02
sql = """
    SELECT SUM(CODFILIAL) AS SALDO_ATUAL
    FROM FEXTRATO
   
"""

cursor.execute(sql)
resultado = cursor.fetchone()
saldo_atual = resultado[0] or 0

print(f"Saldo Calculado do Caixa 02: R$ {saldo_atual:,.2f}")

cursor.close()
conexao.close()