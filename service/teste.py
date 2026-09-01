from datetime import datetime
from decimal import Decimal
import fdb

# Ajuste aqui se o caminho do banco no seu config for diferente
CAMINHO_BD = r"SERVIDOR:C:\tga\Dados\TGA.FDB"


def testar_extrato_banco():
  print("=" * 60)
  print(" SCRIPT DE DIAGNÓSTICO DE SALDO - FEXTRATO (ATÉ 31/08)")
  print("=" * 60)

  banco = int(
      input("Digite o código do banco para testar (748 ou 756): ").strip()
  )
  codcaixa = "02" if banco == 748 else "07"
  nome_banco = "Sicredi" if banco == 748 else "Sicoob"

  # Definindo a data limite como 31/08/2026
  data_limite = datetime(2026, 8, 31).date()

  print(
      f"\nConectando ao banco para o {nome_banco} (Caixa: {codcaixa}) até"
      f" {data_limite.strftime('%d/%m/%Y')}..."
  )

  try:
    conexao = fdb.connect(
        dsn=CAMINHO_BD,
        user="SYSDBA",
        password="masterkey",
        charset="ISO8859_1",
    )
    cursor = conexao.cursor()

    # 1. Soma total da coluna VALOR para o caixa específico até a data limite
    sql_soma = """
            SELECT SUM(VALOR), COUNT(*) 
            FROM FEXTRATO 
            WHERE CODCAIXA = ? AND DATA <= ?
        """
    cursor.execute(sql_soma, (codcaixa, data_limite))
    res_soma = cursor.fetchone()

    total_soma = (
        Decimal(str(res_soma[0]))
        if res_soma and res_soma[0] is not None
        else Decimal("0.00")
    )
    qtd_registros = res_soma[1] if res_soma else 0

    print(f"\n[RESULTADO DA SOMA ATÉ 31/08]")
    print(f"Total de registros no caixa {codcaixa}: {qtd_registros}")
    print(f"Soma total da coluna VALOR: R$ {total_soma:,.2f}")

    # 2. Mostra os últimos 20 lançamentos desse caixa até a data limite para conferência
    print(f"\n--- ÚLTIMOS 20 LANÇAMENTOS DO CAIXA {codcaixa} (ATÉ 31/08) ---")
    sql_ultimos = """
            SELECT FIRST 20 DATA, VALOR, HISTORICO, IDEXTRATO 
            FROM FEXTRATO 
            WHERE CODCAIXA = ? AND DATA <= ?
            ORDER BY DATA DESC, IDEXTRATO DESC
        """
    cursor.execute(sql_ultimos, (codcaixa, data_limite))
    ultimos = cursor.fetchall()

    if not ultimos:
      print("Nenhum lançamento encontrado para este período/caixa.")
    else:
      for row in ultimos:
        data_l, valor_l, hist_l, id_l = row
        data_fmt = (
            data_l.strftime("%d/%m/%Y")
            if hasattr(data_l, "strftime")
            else str(data_l)
        )
        print(
            f"ID: {id_l} | Data: {data_fmt} | Valor: R$ {valor_l:10,.2f} | Hist:"
            f" {hist_l}"
        )

    cursor.close()
    conexao.close()

  except Exception as e:
    print(f"\n[ERRO DE CONEXÃO OU SQL]: {e}")


if __name__ == "__main__":
  testar_extrato_banco()