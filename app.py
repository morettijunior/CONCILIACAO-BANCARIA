from service.bd import consultar_extrato, saldo_sistema
from service.conciliacao import comparar_listas, inserir_itens
from service.ofx import ler_ofx, saldo_final


def exibir_menu():
  print('\n' + '=' * 30)
  print('     CONCILIAÇÃO BANCÁRIA')
  print('=' * 30)
  print('Escolha o banco:')
  print('1 - Sicredi')
  print('2 - Sicoob')
  print('0 - SAIR')
  print('-' * 30)


def main():
  caminho_extrato = r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO_BANCARIA\bd_firebird\extrato.ofx'

  while True:
    exibir_menu()
    opcao = input('Digite sua opção: ').strip()

    if opcao == '1':
      banco_esperado = 748
      nome_banco = 'Sicredi'
    elif opcao == '2':
      banco_esperado = 756
      nome_banco = 'Sicoob'
    elif opcao == '0':
      print('\nSaindo do sistema. Até logo!')
      break
    else:
      print('\n[ERRO] Opção inválida! Escolha 1, 2 ou 0.')
      continue

    print(f'\nProcessando conciliação para o {nome_banco} (Banco: {banco_esperado})...')

    # 1. Leitura e Consultas
    lista_ofx = ler_ofx(banco_esperado, caminho_extrato)
    if not lista_ofx:
      print('[AVISO] Nenhum lançamento encontrado no OFX ou falha na leitura.')
      continue

    lista_bd = consultar_extrato(banco_esperado, caminho_extrato)
    saldo_banco = saldo_final(banco_esperado, caminho_extrato)
    total_sistema = saldo_sistema(banco_esperado)

    # 2. Comparação inicial
    conciliados, nao_conciliados = comparar_listas(lista_ofx, lista_bd)

    print(f'-> Total de registros no OFX: {len(lista_ofx)}')
    print(f'-> Total de registros no BD: {len(lista_bd)}')
    print(f'-> Já conciliados: {len(conciliados)}')
    print(f'-> Não conciliados (antes das regras): {len(nao_conciliados)}')

    # 3. Aplicação das Regras e Inserção dos pendentes compatíveis
    if nao_conciliados:
      print('\nAplicando regras automáticas aos itens não conciliados...')
      inserir_itens(banco_esperado, nao_conciliados, conciliados)

    # Recalcula o saldo do sistema após eventuais inserções por regras
    total_sistema = saldo_sistema(banco_esperado)

    # 4. Exibição do Resultado Final
    print('\n' + '=' * 40)
    print(f'       RESULTADO FINAL - {nome_banco.upper()}')
    print('=' * 40)
    print(f'Total Conciliados (Final): {len(conciliados)}')
    print(f'Total Não Conciliados (Pendentes): {len(nao_conciliados)}')
    if saldo_banco is not None:
      print(f'Saldo Final do Extrato (OFX): R$ {saldo_banco:,.2f}')
    print(f'Saldo Final do Sistema (BD): R$ {total_sistema:,.2f}')
    print('=' * 40)

    input('\nPressione ENTER para voltar ao menu principal...')


if __name__ == '__main__':
  main()