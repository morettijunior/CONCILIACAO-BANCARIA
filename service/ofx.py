from datetime import datetime
from decimal import Decimal
import os
from ofxparse import OfxParser


def _validar_banco(banco_esperado, caminho):
  if not caminho or not os.path.exists(caminho):
    print(f'[ERRO] O arquivo OFX não foi encontrado no caminho: {caminho}')
    return False
  try:
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    conta = ofx.account
    banco_lido = ''
    if conta and conta.routing_number:
      banco_lido = str(conta.routing_number).strip()

    if banco_lido and str(banco_esperado).strip() != banco_lido:
      print(
          f'[ERRO] O banco do arquivo (routing_number: {banco_lido}) não'
          f' confere com o banco esperado ({banco_esperado}).'
      )
      return False
    return True
  except Exception as e:
    print(f'[ERRO] Falha ao validar o banco no OFX: {e}')
    return False


def ler_ofx(banco_esperado, caminho):
  if not _validar_banco(banco_esperado, caminho):
    return []

  try:
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    conta = ofx.account
    extrato_form_ofx = []

    if conta and conta.statement and conta.statement.transactions:
      for transacao in conta.statement.transactions:
        data_transacao = transacao.date
        if hasattr(data_transacao, 'date'):
          data_transacao = data_transacao.date()

        valor_transacao = Decimal(str(transacao.amount))
        historico_transacao = str(transacao.memo or transacao.payee or '').strip()

        extrato_form_ofx.append({
            'data': data_transacao,
            'valor': valor_transacao,
            'historico': historico_transacao,
        })

    return extrato_form_ofx

  except Exception as e:
    print(f'[ERRO] Falha ao processar o arquivo OFX: {e}')
    return []


def data_inicial(banco_esperado, caminho):
  if not _validar_banco(banco_esperado, caminho):
    return None

  try:
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    conta = ofx.account
    if conta and conta.statement and conta.statement.start_date:
      dt = conta.statement.start_date
      if hasattr(dt, 'date'):
        return dt.date()
      return dt

    print('[AVISO] Tag de data inicial não encontrada no OFX.')
    return None
  except Exception as e:
    print(f'[ERRO] Falha ao extrair a data inicial do OFX: {e}')
    return None


def data_final(banco_esperado, caminho):
  if not _validar_banco(banco_esperado, caminho):
    return None

  try:
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    conta = ofx.account
    if conta and conta.statement and conta.statement.end_date:
      dt = conta.statement.end_date
      if hasattr(dt, 'date'):
        return dt.date()
      return dt

    print('[AVISO] Tag de data final não encontrada no OFX.')
    return None
  except Exception as e:
    print(f'[ERRO] Falha ao extrair a data final do OFX: {e}')
    return None


def saldo_final(banco_esperado, caminho):
  if not _validar_banco(banco_esperado, caminho):
    return None

  try:
    with open(caminho, 'r', encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    conta = ofx.account
    if conta and conta.statement and conta.statement.balance is not None:
      return Decimal(str(conta.statement.balance))

    return None
  except Exception as e:
    print(f'[ERRO] Falha ao extrair o saldo final do OFX: {e}')
    return None