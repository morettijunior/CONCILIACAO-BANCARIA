from ofxparse import OfxParser


def ler_ofx():
  # 1. Criamos a lista vazia localmente dentro da função
  transacoes_extraidas = []

  with open(
      r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO BANCARIA\bd_firebird\teste.ofx',
      'rb',
  ) as extrato:
    ofx = OfxParser.parse(extrato)
    conta = ofx.account
    st = conta.statement

    # 2. Percorremos e adicionamos na lista local
    for item in st.transactions:
      movimento_unico = (
          item.date,
          item.amount,
          item.memo,
      )  
      transacoes_extraidas.append(movimento_unico)

  # 3. A função devolve a lista pronta para quem a chamou
  return transacoes_extraidas


# Testando a função
if __name__ == '__main__':
  resultado = ler_ofx()
  print(resultado)