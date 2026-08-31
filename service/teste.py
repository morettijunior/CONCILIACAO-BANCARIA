from ofxparse import OfxParser


def inspecionar_ofx(caminho):
  try:
    with open(caminho, encoding='ISO-8859-1') as arquivo_ofx:
      ofx = OfxParser.parse(arquivo_ofx)

    print('=== DADOS DA CONTA ===')
    conta = ofx.account
    if conta:
      print(f'account_id (Número da Conta): {getattr(conta, "account_id", None)}')
      print(f'routing_number: {getattr(conta, "routing_number", None)}')
      print(f'branch_id (Agência): {getattr(conta, "branch_id", None)}')
      print(f'type (Tipo de Conta): {getattr(conta, "type", None)}')

      print('\n=== DADOS DA INSTITUIÇÃO ===')
      inst = getattr(conta, 'institution', None)
      if inst:
        print(f'organization: {getattr(inst, "organization", None)}')
        print(f'fid: {getattr(inst, "fid", None)}')
      else:
        print('Nenhuma instituição encontrada.')

      print('\n=== DADOS DO EXTRATO (STATEMENT) ===')
      stmt = getattr(conta, 'statement', None)
      if stmt:
        print(f'start_date: {getattr(stmt, "start_date", None)}')
        print(f'end_date: {getattr(stmt, "end_date", None)}')
        print(f'balance (Saldo): {getattr(stmt, "balance", None)}')
        print(
            f'available_balance: {getattr(stmt, "available_balance", None)}'
        )

        transacoes = getattr(stmt, 'transactions', [])
        print(f'\nTotal de transações encontradas: {len(transacoes)}')

        if transacoes:
          print(
              '\n--- Exemplo da primeira transação encontrada ---'
          )
          t = transacoes[0]
          print(f'  - date: {getattr(t, "date", None)}')
          print(f'  - amount (Valor): {getattr(t, "amount", None)}')
          print(f'  - type: {getattr(t, "type", None)}')
          print(f'  - memo: {getattr(t, "memo", None)}')
          print(f'  - payee: {getattr(t, "payee", None)}')
          print(f'  - id: {getattr(t, "id", None)}')
      else:
        print('Nenhum extrato (statement) encontrado.')
    else:
      print('Nenhuma conta encontrada no arquivo.')

  except Exception as e:
    print(f'[ERRO] Falha ao inspecionar o arquivo OFX: {e}')


if __name__ == '__main__':
  caminho_teste = r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO BANCARIA\bd_firebird\extrato.ofx'
  inspecionar_ofx(caminho_teste)