from decimal import Decimal
import fdb
from .ofx import data_final, data_inicial
from .config import carregar_config


def _obter_conexao_bd(caminho_bd=None):
    if not caminho_bd:
        config = carregar_config()
        caminho_bd = config.get("caminho_bd", r'C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb')
    return fdb.connect(
        dsn=caminho_bd,
        user="SYSDBA",
        password="masterkey",
        charset="ISO8859_1",
    )


def consultar_extrato(banco_esperado, caminho_ofx, caminho_bd):
    dt_inicio = data_inicial(banco_esperado, caminho_ofx)
    dt_fim = data_final(banco_esperado, caminho_ofx)

    if not dt_inicio or not dt_fim:
        print(
            "[ERRO] Não foi possível obter as datas inicial e final do arquivo"
            " OFX."
        )
        return []

    # Define o caixa correto com base no banco selecionado
    codcaixa = "02" if str(banco_esperado) == "748" else "07"

    conexao = _obter_conexao_bd(caminho_bd)
    cursor = conexao.cursor()

    try:
        sql = """
            SELECT DATA, VALOR, HISTORICO, NUMERODOCUMENTO 
            FROM FEXTRATO 
            WHERE CODCAIXA = ? AND DATA BETWEEN ? AND ?
        """
        cursor.execute(sql, (codcaixa, dt_inicio, dt_fim))
        registros = cursor.fetchall()

        extrato_bd = []
        for reg in registros:
            data_bd, valor_bd, historico_bd, numerodocumento_bd = reg
            extrato_bd.append({
                "data": data_bd,
                "valor": Decimal(str(valor_bd)),
                "historico": str(historico_bd or "").strip(),
                "numerodocumento": str(numerodocumento_bd or "").strip(),
            })

        return extrato_bd

    except Exception as e:
        print(f"[ERRO] Falha ao consultar o extrato no banco de dados: {e}")
        return []
    finally:
        cursor.close()
        conexao.close()


def saldo_sistema(banco_esperado, caminho_bd, data_final=None):
    """Calcula o saldo somando a coluna VALOR da tabela FEXTRATO
    filtrando pelo CODCAIXA e opcionalmente limitando até a DATA FINAL.
    """
    codcaixa = "02" if str(banco_esperado) == "748" else "07"

    conexao = _obter_conexao_bd(caminho_bd)
    cursor = conexao.cursor()

    total_saldo = Decimal("0.00")
    try:
        if data_final:
            sql = """
                SELECT SUM(VALOR) 
                FROM FEXTRATO 
                WHERE CODCAIXA = ? AND DATA <= ?
            """
            cursor.execute(sql, (codcaixa, data_final))
        else:
            sql = """
                SELECT SUM(VALOR) 
                FROM FEXTRATO 
                WHERE CODCAIXA = ?
            """
            cursor.execute(sql, (codcaixa,))

        res = cursor.fetchone()

        if res and res[0] is not None:
            total_saldo = Decimal(str(res[0]))

    except Exception as e:
        print(f"[ERRO BD] Falha ao calcular saldo do sistema: {e}")
    finally:
        cursor.close()
        conexao.close()

    return total_saldo


def obter_proximo_id(cursor, nome_tabela):
    """Função padronizada para buscar e atualizar o próximo ID (GAUTOINC)."""
    try:
        cursor.execute("SELECT PROXIMOVALOR FROM GAUTOINC WHERE TABELA = ?", (nome_tabela.upper(),))
        row = cursor.fetchone()
        if row:
            proximo_id = row[0]
            cursor.execute(
                "UPDATE GAUTOINC SET PROXIMOVALOR = ? WHERE TABELA = ?",
                (proximo_id + 1, nome_tabela.upper())
            )
            return proximo_id
    except Exception as e:
        print(f"[ERRO] Falha ao obter próximo ID para {nome_tabela}: {e}")
    return None


def listar_regras(caminho_bd=None):
    """Retorna todas as regras cadastradas na tabela TREGRAOFX."""
    conexao = _obter_conexao_bd(caminho_bd)
    cursor = conexao.cursor()
    try:
        cursor.execute(
            'SELECT CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA, CODCAIXA_ORIGEM, CODCAIXA_DESTINO FROM TREGRAOFX'
        )
        return cursor.fetchall()
    except Exception as e:
        print(f'[ERRO] Falha ao listar regras: {e}')
        return []
    finally:
        cursor.close()
        conexao.close()


def inserir_regra(codcfo, ccusto, historico, historico_busca, codcaixa_origem=None, codcaixa_destino=None, caminho_bd=None):
    """Insere uma nova regra no banco, suportando também regras de transferência entre caixas."""
    conexao = _obter_conexao_bd(caminho_bd)
    cursor = conexao.cursor()
    try:
        sql = """
            INSERT INTO TREGRAOFX (CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA, CODCAIXA_ORIGEM, CODCAIXA_DESTINO)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(
            sql, (
                codcfo.strip() if codcfo else None, 
                ccusto.strip() if ccusto else None, 
                historico.strip() if historico else None, 
                historico_busca.strip().upper(),
                codcaixa_origem.strip() if codcaixa_origem else None,
                codcaixa_destino.strip() if codcaixa_destino else None
            )
        )
        conexao.commit()
        return True
    except Exception as e:
        conexao.rollback()
        print(f'[ERRO] Falha ao inserir regra: {e}')
        return False
    finally:
        cursor.close()
        conexao.close()


def excluir_regra(historico_busca, caminho_bd=None):
    """Exclui uma regra com base no histórico de busca."""
    conexao = _obter_conexao_bd(caminho_bd)
    cursor = conexao.cursor()
    try:
        sql = 'DELETE FROM TREGRAOFX WHERE HISTORICO_BUSCA = ?'
        cursor.execute(sql, (historico_busca.strip().upper(),))
        conexao.commit()
        return True
    except Exception as e:
        conexao.rollback()
        print(f'[ERRO] Falha ao excluir regra: {e}')
        return False
    finally:
        cursor.close()
        conexao.close()