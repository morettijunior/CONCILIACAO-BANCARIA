from decimal import Decimal
from bd import consultar_extrato_bd, inserir_lancamento, fdb
from ofx import ler_ofx


def buscar_regra_ofx(historico_ofx):
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()

  try:
    cursor.execute("""
            SELECT TERMO_BUSCA, CODEMPRESA, CODFILIAL, CODCAIXA, CODCFO, TIPO, CONCILIADO, COMPENSADO 
            FROM TREGRAOFX
        """)
    regras = cursor.fetchall()

    for regra in regras:
      termo_busca, empresa, filial, caixa, cfo, tipo, conciliado, compensado = (
          regra
      )
      if termo_busca.upper() in historico_ofx.upper():
        return {
            'cod_empresa': empresa,
            'cod_filial': filial,
            'caixa': caixa,
            'cod_cfo': cfo,
            'tipo': tipo,
        }
    return None
  except Exception as e:
    print(f'[ERRO] Falha ao consultar regras: {e}')
    return None
  finally:
    cursor.close()
    conexao.close()


def processar_conciliacao(caminho_ofx, caixa_alvo='02'):
  print('1. Lendo arquivo OFX...')
  transacoes_ofx = ler_ofx(caminho_ofx)

  print('2. Consultando lançamentos já existentes no Banco de Dados...')
  registros_bd = consultar_extrato_bd(caixa=caixa_alvo)

  # Cria um conjunto de chaves únicas do que já está no banco: "YYYY-MM-DD|VALOR|HISTORICO"
  chaves_bd = set()
  for reg in registros_bd:
    _, data_bd, valor_bd, hist_bd, _, tipo_bd = reg
    data_str = str(data_bd)[:10]
    val = Decimal(str(valor_bd))
    if tipo_bd and str(tipo_bd).strip().upper() == 'D':
      val = -abs(val)
    # Normaliza o histórico para evitar divergências de espaços/truncamentos
    hist_limpo = str(hist_bd).strip().upper() if hist_bd else ''
    chaves_bd.add(f'{data_str}|{val}|{hist_limpo}')

  conciliados = []
  nao_conciliados = []

  print('3. Cruzando transações do OFX com o Banco...')
  for transacao in transacoes_ofx:
    if isinstance(transacao, (list, tuple)):
      data_ofx, valor_ofx, historico_ofx = transacao
    else:
      data_ofx = transacao['data']
      valor_ofx = transacao['valor']
      historico_ofx = transacao['historico']

    data_str = str(data_ofx)[:10]
    val_dec = Decimal(str(valor_ofx))
    hist_limpo = str(historico_ofx).strip().upper()

    chave_ofx = f'{data_str}|{val_dec}|{hist_limpo}'

    item = {
        'data': data_ofx,
        'valor': val_dec,
        'historico': historico_ofx,
    }

    if chave_ofx in chaves_bd:
      conciliados.append(item)
    else:
      nao_conciliados.append(item)

  print(f'\n[JÁ EXISTENTES NO BANCO] Total: {len(conciliados)}')

  inseridos = 0
  pendentes_manual = []

  print('\n--- PROCESSANDO ITENS ÓRFÃOS ---')
  for item in nao_conciliados:
    regra = buscar_regra_ofx(item['historico'])

    if regra:
      res = inserir_lancamento(
          data_movimento=item['data'],
          valor=item['valor'],
          historico=item['historico'],
          cod_cfo=regra['cod_cfo'],
          cod_tdo='DP',
          num_doc='OFX',
          ccusto='1',
          caixa=regra['caixa'],
          cod_forma='01',
      )

      if res:
        inseridos += 1
        print(
            f"[AUTO-INSERIDO] Data: {item['data']} | Valor:"
            f" R$ {item['valor']:,.2f} | Hist: {item['historico']}"
        )
      else:
        pendentes_manual.append(item)
    else:
      pendentes_manual.append(item)

  print(f'\n[PENDENTES PARA LANÇAMENTO MANUAL] Total: {len(pendentes_manual)}')
  for item in pendentes_manual:
    print(
        f"  -> Data: {item['data']} | Valor: R$ {item['valor']:,.2f} | Hist:"
        f" {item['historico']}"
    )

  print('\n--- RESUMO FINAL ---')
  print(f'Já existentes no banco: {len(conciliados)}')
  print(f'Inseridos automaticamente: {inseridos}')
  print(f'Pendentes de lançamento manual: {len(pendentes_manual)}')


if __name__ == '__main__':
  caminho_teste = r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO BANCARIA\bd_firebird\teste_regras.ofx'
  processar_conciliacao(caminho_teste, caixa_alvo='02')