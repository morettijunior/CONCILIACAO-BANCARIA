from datetime import datetime
from decimal import Decimal
import os
from ofxparse import OfxParser


def ler_ofx(banco_esperado, caminho):
  # 1. Validação do caminho do arquivo
  if not caminho or not os.path.exists(caminho):
    print(f'[ERRO] O arquivo OFX não foi encontrado no caminho: {caminho}')
    return []

  try:
    # 2. Leitura do arquivo OFX usando ofxparse
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    # Obtém a conta e o routing_number (código do banco)
    conta = ofx.account
    banco_lido = ''
    if conta and conta.routing_number:
      banco_lido = str(conta.routing_number).strip()

    # 3. Validação do código do banco
    if banco_lido and str(banco_esperado).strip() != banco_lido:
      print(
          f'[ERRO] O banco do arquivo (routing_number: {banco_lido}) não'
          f' confere com o banco esperado ({banco_esperado}).'
      )
      return []

    extrato_ofx = []
    extrato_form_ofx = []

    # 4. Gravação dos dados recebidos na lista bruta
    if conta and conta.statement and conta.statement.transactions:
      for transacao in conta.statement.transactions:
        data_transacao = transacao.date
        if hasattr(data_transacao, 'date'):
          data_transacao = data_transacao.date()

        valor_transacao = Decimal(str(transacao.amount))
        historico_transacao = str(transacao.memo or transacao.payee or '').strip()

        extrato_ofx.append(
            (data_transacao, historico_transacao, valor_transacao)
        )

    # 5. Formatação para o padrão do BD (Data, Valor, Histórico)
    for data, historico, valor in extrato_ofx:
      extrato_form_ofx.append({
          'data': data,
          'valor': valor,
          'historico': historico,
      })

    return extrato_form_ofx

  except Exception as e:
    print(f'[ERRO] Falha ao processar o arquivo OFX: {e}')
    return []


from datetime import datetime
import os
from ofxparse import OfxParser


def data_inicial(banco_esperado, caminho):
  # 1. Validação do caminho do arquivo
  if not caminho or not os.path.exists(caminho):
    print(f'[ERRO] O arquivo OFX não foi encontrado no caminho: {caminho}')
    return None

  try:
    # 2. Leitura do arquivo OFX
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    # 3. Validação do código do banco (routing_number)
    conta = ofx.account
    banco_lido = ''
    if conta and conta.routing_number:
      banco_lido = str(conta.routing_number).strip()

    if banco_lido and str(banco_esperado).strip() != banco_lido:
      print(
          f'[ERRO] O banco do arquivo (routing_number: {banco_lido}) não'
          f' confere com o banco esperado ({banco_esperado}).'
      )
      return None

    # 4. Extração e formatação da data inicial (start_date)
    if conta and conta.statement and conta.statement.start_date:
      data_inicio = conta.statement.start_date

      # Padroniza para remover horas/minutos se vier como datetime completo
      if hasattr(data_inicio, 'date'):
        data_inicio = data_inicio.date()

      return data_inicio

    return None

  except Exception as e:
    print(f'[ERRO] Falha ao extrair a data inicial do OFX: {e}')
    return None


def data_final(banco_esperado, caminho):
  # 1. Validação do caminho do arquivo
  if not caminho or not os.path.exists(caminho):
    print(f'[ERRO] O arquivo OFX não foi encontrado no caminho: {caminho}')
    return None

  try:
    # 2. Leitura do arquivo OFX
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    # 3. Validação do código do banco (routing_number)
    conta = ofx.account
    banco_lido = ''
    if conta and conta.routing_number:
      banco_lido = str(conta.routing_number).strip()

    if banco_lido and str(banco_esperado).strip() != banco_lido:
      print(
          f'[ERRO] O banco do arquivo (routing_number: {banco_lido}) não'
          f' confere com o banco esperado ({banco_esperado}).'
      )
      return None

    # 4. Extração e formatação da data final (end_date)
    if conta and conta.statement and conta.statement.end_date:
      data_fim = conta.statement.end_date

      # Padroniza para remover horas/minutos se vier como datetime completo
      if hasattr(data_fim, 'date'):
        data_fim = data_fim.date()

      return data_fim

    return None

  except Exception as e:
    print(f'[ERRO] Falha ao extrair a data final do OFX: {e}')
    return None


from decimal import Decimal
import os
from ofxparse import OfxParser


def saldo_final(banco_esperado, caminho):
  # 1. Validação do caminho do arquivo
  if not caminho or not os.path.exists(caminho):
    print(f'[ERRO] O arquivo OFX não foi encontrado no caminho: {caminho}')
    return None

  try:
    # 2. Leitura do arquivo OFX
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    # 3. Validação do código do banco (routing_number)
    conta = ofx.account
    banco_lido = ''
    if conta and conta.routing_number:
      banco_lido = str(conta.routing_number).strip()

    if banco_lido and str(banco_esperado).strip() != banco_lido:
      print(
          f'[ERRO] O banco do arquivo (routing_number: {banco_lido}) não'
          f' confere com o banco esperado ({banco_esperado}).'
      )
      return None

    # 4. Extração e formatação do saldo final (balance) para Decimal (padrão BD)
    if conta and conta.statement and conta.statement.balance is not None:
      saldo = Decimal(str(conta.statement.balance))
      return saldo

    return None

  except Exception as e:
    print(f'[ERRO] Falha ao extrair o saldo final do OFX: {e}')
    return None


# Testando a função
if __name__ == '__main__':
  caminho_teste = r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO BANCARIA\bd_firebird\extrato.ofx'
  saldo = saldo_final(748, caminho_teste)
  print(f'Saldo Final do Extrato: {saldo}')