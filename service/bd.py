import fdb


def consultar_lancamento(data_busca, valor_busca):
  # 1. Abre a conexão
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )

  # 2. Cria o cursor
  cursor = conexao.cursor()

  # 3. O comando SQL vai DENTRO do cursor (usando ? para evitar erros e SQL Injection)
  sql = (
      'SELECT FIRST 1 DATABAIXA, VALORBAIXADO, HISTORICO FROM FLAN WHERE'
      ' DATABAIXA = ? AND VALORBAIXADO = ?'
  )

  # Aqui o cursor executa o comando passando os dados
  cursor.execute(sql, (data_busca, valor_busca))

  # 4. Pega o resultado que o cursor trouxe
  resultado = cursor.fetchone()  # Traz o primeiro registro encontrado

  # 5. Fecha tudo (boa prática)
  cursor.close()
  conexao.close()

  # 6. Retorna o que achou (ou None se não achou nada)
  return resultado

#TESTE
from decimal import Decimal
import datetime
if __name__ == '__main__':
  # Usando exatamente a data e o valor que você encontrou no FLAN
  data_teste = datetime.date(2026, 8, 21)
  valor_teste = Decimal('5.7')

  resultado = consultar_lancamento(data_teste, valor_teste)
  print('Resultado da busca:', resultado)