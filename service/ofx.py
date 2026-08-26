from ofxparse import OfxParser

with open(r'C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO BANCARIA\bd_firebird\teste.ofx', 'rb') as extrato:
    ofx = OfxParser.parse(extrato)

# 1. Dados da Conta
conta = ofx.account
print("=== DADOS DA CONTA ===")
print(f"Conta: {conta.account_id} | Banco (Routing): {conta.routing_number}")

# 2. Dados do Extrato (Statement)
st = conta.statement
print("\n=== PERÍODO E SALDO DO EXTRATO ===")
print(f"Período: de {st.start_date} até {st.end_date}")
print(f"Saldo Final no Extrato: {st.balance}")
print("-" * 40)

# 3. As Transações
print("\n=== TRANSAÇÕES ===")
for t in st.transactions:
    print(f"Data: {t.date} | Valor: {t.amount} | Histórico: {t.memo}")