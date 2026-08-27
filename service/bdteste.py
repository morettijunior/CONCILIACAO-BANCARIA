import fdb

# 1. Configurando os parâmetros de conexão local
dsn = r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb'  # Caminho completo do arquivo do banco
usuario = 'SYSDBA'
senha = 'masterkey'  # Ou a senha padrão do seu Firebird

# 2. Abrindo a conexão
conexao = fdb.connect(
    dsn=dsn, user=usuario, password=senha, charset='ISO8859_1'
)

# 3. Criando o cursor (o executor de comandos)
cursor = conexao.cursor()
print("Dentro do BD")
# (Aqui rodaremos nossos comandos SQL de SELECT ou UPDATE no futuro...)

# 4. Fechando tudo com segurança
cursor.close()
conexao.close()
print("Conexão fechada. Teste ok")