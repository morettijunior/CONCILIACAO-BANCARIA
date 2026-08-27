import datetime
from decimal import Decimal
from bd import consultar_lancamento
from ofx import ler_ofx

# 1. Pega todas as transações do OFX
transacoes_ofx = ler_ofx()

print('=== INICIANDO A CONCILIAÇÃO ===\n')

# 2. Varre cada transação do extrato usando um laço for
for item in transacoes_ofx:
  # O item do OFX traz: (data_completa, valor, historico)
  data_ofx = item[
      0
  ].date()  # Pega só a data pura (eliminando a hora 03:00 do OFX)
  valor_ofx = item[1]  # Pega o valor exato
  memo_ofx = item[2]  # Pega o histórico do extrato

  # 3. Consulta o Firebird usando os dados da transação atual do OFX
  resultado_bd = consultar_lancamento(data_ofx, valor_ofx)

  # 4. Analisa o resultado
  if resultado_bd:
    print(f'[CONCILIADO] Data: {data_ofx} | Valor: {valor_ofx} | Histórico:'
        f' {memo_ofx}'
    )
  else:
    print(
        f'[DIVERGÊNCIA] Data: {data_ofx} | Valor: {valor_ofx} | Histórico:'
        f' {memo_ofx}'
    )