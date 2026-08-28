import datetime
from decimal import Decimal
import fdb


def inserir_lancamento(
    data_movimento,
    valor,
    historico,
    cod_cfo,
    cod_tdo,
    num_doc,
    ccusto,
    caixa,
    cod_forma='01',
):
  conexao = fdb.connect(
      dsn=r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb',
      user='SYSDBA',
      password='masterkey',
      charset='ISO8859_1',
  )
  cursor = conexao.cursor()

  try:
    # 1. Busca o próximo IDLAN para a FLAN
    cursor.execute('SELECT MAX(IDLAN) FROM FLAN')
    res_lan = cursor.fetchone()
    proximo_id_lan = (res_lan[0] or 0) + 1

    # 2. Busca o próximo IDEXTRATO para a FEXTRATO
    cursor.execute('SELECT MAX(IDEXTRATO) FROM FEXTRATO')
    res_ext = cursor.fetchone()
    proximo_id_ext = (res_ext[0] or 0) + 1

    # Define o PAGREC ('P' ou 'R') e o valor absoluto (NUMERIC 15,4)
    pag_rec = 'P' if valor < 0 else 'R'
    valor_absoluto = abs(valor) if valor < 0 else valor
    # Tipo para extrato (Geralmente 'P' para pagamento/débito e 'R' para recebimento/crédito, ou similar)
    tipo_extrato = 'D' if valor < 0 else 'C'

    # --- PASSO A: INSERIR NA FLAN ---
    sql_flan = """
            INSERT INTO FLAN (
                IDLAN, CODEMPRESA, CODFILIAL, CODCFO, CODTDO, NUMERODOCUMENTO,
                PARCELA, NPARCELA, PAGREC, VALORORIGINAL, VALORBAIXADO,
                DATAVENCIMENTO, DATAEMISSAO, DATABAIXA, DATAPREVBAIXA,
                DATADIGITACAO, DATADIGITACAOBAIXA, HISTORICO, HISTORICOBAIXA,
                CODMOEVALORORIGINAL, CODCAIXA, STATUSLAN, CODFORMA, INATIVO,
                USUARIOBAIXA, CCUSTO
            ) VALUES (
                ?, 1, 1, ?, ?, ?, 
                1, 1, ?, ?, ?, 
                ?, ?, ?, ?, 
                ?, ?, ?, ?, 
                ?, ?, 'B', ?, 'F', 
                'FIN', ?
            )
        """
    params_flan = (
        proximo_id_lan,
        str(cod_cfo),
        str(cod_tdo),
        str(num_doc)[:5],
        pag_rec,
        valor_absoluto,
        valor_absoluto,
        data_movimento,
        data_movimento,
        data_movimento,
        data_movimento,
        datetime.datetime.now(),
        datetime.datetime.now(),
        str(historico)[:50],
        str(historico)[:25],
        'R$',
        str(caixa).zfill(2),
        str(cod_forma),
        str(ccusto)[:3],
    )
    cursor.execute(sql_flan, params_flan)

    # --- PASSO B: INSERIR NA FEXTRATO (Espelho do extrato bancário) ---
    sql_extrato = """
            INSERT INTO FEXTRATO (
                IDEXTRATO, CODEMPRESA, CODFILIAL, IDLAN, VALOR, 
                HISTORICO, DATA, DATAVENCIMENTO, DATADIGITACAO, 
                CODCAIXA, CODCFO, TIPO, CONCILIADO, COMPENSADO
            ) VALUES (
                ?, 1, 1, ?, ?, 
                ?, ?, ?, ?, 
                ?, ?, ?, 'F', 'T'
            )
        """
    params_extrato = (
        proximo_id_ext,
        proximo_id_lan,
        valor_absoluto,
        str(historico)[:50],
        data_movimento,
        data_movimento,
        datetime.datetime.now(),
        str(caixa).zfill(2),
        str(cod_cfo),
        tipo_extrato,
    )
    cursor.execute(sql_extrato, params_extrato)

    # --- PASSO C: VINCULAR NA FEXTRATOLANC (Se a tabela exigir ponte) ---
    try:
      sql_ext_lanc = """
                INSERT INTO FEXTRATOLANC (IDEXTRATO, IDLAN, CODEMPRESA) 
                VALUES (?, ?, 1)
            """
      cursor.execute(sql_ext_lanc, (proximo_id_ext, proximo_id_lan))
    except Exception:
      pass  # Caso a tabela não seja obrigatória ou já faça parte, ignora sem quebrar

    # Confirma tudo no banco
    conexao.commit()
    print(
        f'[SUCESSO] Lançamento duplo inserido! IDLAN: {proximo_id_lan} |'
        f' IDEXTRATO: {proximo_id_ext} | Histórico: {historico}'
    )

  except Exception as e:
    conexao.rollback()
    print(f'[ERRO] Falha ao inserir lançamento unificado: {e}')
  finally:
    cursor.close()
    conexao.close()


# Bloco de execução do teste real unificado
if __name__ == '__main__':
  print('Iniciando teste unificado (FLAN + FEXTRATO)...')

  data_teste = datetime.date.today()
  valor_teste = Decimal('-25.50')  # Testando valor de tarifa
  historico_teste = 'TESTE EXTRATO UNIFICADO'

  inserir_lancamento(
      data_movimento=data_teste,
      valor=valor_teste,
      historico=historico_teste,
      cod_cfo='F00001',
      cod_tdo='DP',
      num_doc='999',
      ccusto='1',
      caixa='02',
      cod_forma='01',
  )