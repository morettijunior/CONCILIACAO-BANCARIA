def obter_proximo_id(cursor, tabela, coluna_id, cod_empresa=1):
    """Busca o maior ID atual, incrementa 1 e atualiza a tabela GAUTOINC considerando
    a empresa, mantendo o cache do TGA perfeitamente sincronizado.
    """
    # 1. Pega o maior ID atual da tabela de destino
    cursor.execute(f"SELECT MAX({coluna_id}) FROM {tabela}")
    res = cursor.fetchone()
    max_id = res[0] if res and res[0] is not None else 0
    novo_id = max_id + 1

    # 2. Atualiza o GAUTOINC considerando a tabela, o campo e a CODEMPRESA
    cursor.execute(
        """
        UPDATE GAUTOINC 
        SET VALOR = ? 
        WHERE TABELA = ? AND CAMPO = ? AND CODEMPRESA = ?
    """,
        (novo_id, tabela.upper(), coluna_id.upper(), cod_empresa),
    )

    return novo_id