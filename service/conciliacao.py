from datetime import datetime
from decimal import Decimal
import fdb


def comparar_listas(extrato_ofx, extrato_bd):
  bd_pendentes = list(extrato_bd)

  cartoes_conciliado = []
  cartoes_nao_conciliado = []
  boletos_conciliado = []
  boletos_nao_conciliado = []
  outros_conciliado = []
  outros_nao_conciliado = []

  # 1. Classificar cada item do OFX no seu respectivo bloco
  for item_ofx in extrato_ofx:
    hist = str(item_ofx["historico"]).upper()

    if any(k in hist for k in ["VISA", "MASTER", "AMEX", "CIELO", "CARTAO", "CREDIT", "DEBIT"]):
      item_ofx["bloco"] = "cartoes"
    elif "CRÉD.LIQUIDAÇÃO COBRANÇA" in hist or "CRED.LIQUIDACAO COBRANCA" in hist:
      item_ofx["bloco"] = "boletos"
    else:
      item_ofx["bloco"] = "outros"

  # 2. Cruzamento 1 para 1 normal (Data e Valor exatos)
  ofx_pendentes = list(extrato_ofx)

  for item_ofx in ofx_pendentes:
    encontrado = False
    for item_bd in bd_pendentes:
      if (
          item_ofx["data"] == item_bd["data"]
          and item_ofx["valor"] == item_bd["valor"]
      ):
        par = {"ofx": item_ofx, "bd": item_bd}
        if item_ofx["bloco"] == "cartoes":
          cartoes_conciliado.append(par)
        elif item_ofx["bloco"] == "boletos":
          boletos_conciliado.append(par)
        else:
          outros_conciliado.append(par)

        bd_pendentes.remove(item_bd)
        encontrado = True
        break

    if not encontrado:
      nao_conc_item = {"origem": "OFX", "item": item_ofx}
      if item_ofx["bloco"] == "cartoes":
        cartoes_nao_conciliado.append(nao_conc_item)
      elif item_ofx["bloco"] == "boletos":
        boletos_nao_conciliado.append(nao_conc_item)
      else:
        outros_nao_conciliado.append(nao_conc_item)

  # 3. VALIDAÇÃO EM LOTE PARA CARTÕES (Sua regra: Taxa Cartão + Num. Documento)
  cartoes_ofx_pendentes = [
      x for x in cartoes_nao_conciliado if x["origem"] == "OFX"
  ]

  if cartoes_ofx_pendentes:
    total_ofx_cartoes = sum(item["item"]["valor"] for item in cartoes_ofx_pendentes)

    # Passo 1: Encontra no BD os lançamentos de "TAXA CARTAO" (negativos)
    itens_taxa_bd = []
    for item_bd in list(bd_pendentes):
      hist_bd = str(item_bd.get("historico", "")).upper()
      val_bd = item_bd.get("valor", 0)
      if "TAXA CARTAO" in hist_bd and val_bd < 0:
        itens_taxa_bd.append(item_bd)

    if itens_taxa_bd:
      # Passo 2: Para cada taxa encontrada, acha o par positivo com o mesmo NUMERODOCUMENTO
      lotes_cartao_bd = []
      docs_utilizados = set()

      for taxa in itens_taxa_bd:
        num_doc = taxa.get("numerodocumento")
        if num_doc:
          # Procura no bd_pendentes o lançamento positivo com o mesmo num_doc
          for item_bd in bd_pendentes:
            if (
                item_bd.get("numerodocumento") == num_doc
                and item_bd.get("valor", 0) > 0
                and item_bd not in lotes_cartao_bd
            ):
              lotes_cartao_bd.append(item_bd)
              lotes_cartao_bd.append(taxa)
              docs_utilizados.add(num_doc)
              break

      if lotes_cartao_bd:
        # Passo 3: Soma o líquido (positivos - negativos/taxas)
        total_bd_cartoes = sum(b["valor"] for b in lotes_cartao_bd)

        # Se o total líquido do lote bater com o total dos cartões pendentes no OFX
        if abs(total_ofx_cartoes - total_bd_cartoes) < Decimal("0.01"):
          for item_ofx_p in cartoes_ofx_pendentes:
            cartoes_nao_conciliado.remove(item_ofx_p)
            cartoes_conciliado.append({
                "ofx": item_ofx_p["item"],
                "bd": lotes_cartao_bd[0],  # Associa ao principal do lote
            })

          # Remove os itens do BD usados da lista de pendentes gerais
          for b_item in lotes_cartao_bd:
            if b_item in bd_pendentes:
              bd_pendentes.remove(b_item)

  # 4. VALIDAÇÃO EM LOTE PARA BOLETOS (Mantém a que já funcionou)
  boletos_ofx_pendentes = [
      x for x in boletos_nao_conciliado if x["origem"] == "OFX"
  ]

  if boletos_ofx_pendentes:
    total_ofx_boletos = sum(item["item"]["valor"] for item in boletos_ofx_pendentes)

    liquidacoes_bd = []
    for item_bd in list(bd_pendentes):
      hist_bd = str(item_bd["historico"]).upper()
      if "LIQUIDAÇÃO DE COBRANÇA" in hist_bd or "LIQUIDACAO DE COBRANCA" in hist_bd:
        liquidacoes_bd.append(item_bd)

    if liquidacoes_bd:
      total_bd_liquidacao = sum(b["valor"] for b in liquidacoes_bd)

      if total_ofx_boletos == total_bd_liquidacao:
        for item_ofx_p in boletos_ofx_pendentes:
          boletos_nao_conciliado.remove(item_ofx_p)
          boletos_conciliado.append({
              "ofx": item_ofx_p["item"],
              "bd": liquidacoes_bd[0],
          })

        for l_bd in liquidacoes_bd:
          if l_bd in bd_pendentes:
            bd_pendentes.remove(l_bd)

  # Tudo o que sobrou no BD vai para "outros" não conciliados
  for item_bd in bd_pendentes:
    outros_nao_conciliado.append({"origem": "BD", "item": item_bd})

  return (
      cartoes_conciliado,
      cartoes_nao_conciliado,
      boletos_conciliado,
      boletos_nao_conciliado,
      outros_conciliado,
      outros_nao_conciliado,
  )


def inserir_itens(
    banco_esperado,
    caminho_bd,
    cartoes_nao_conc,
    boletos_nao_conc,
    outros_nao_conc,
    cartoes_conc,
    boletos_conc,
    outros_conc,
):
  """Varre as listas de não conciliados (origem OFX) aplicando regras,

  insere no Firebird e migra para as respectivas listas de conciliados.
  """
  conexao = fdb.connect(
      dsn=caminho_bd,
      user="SYSDBA",
      password="masterkey",
      charset="ISO8859_1",
  )
  cursor = conexao.cursor()

  try:
    cursor.execute(
        "SELECT CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA FROM TREGRAOFX"
    )
    regras = cursor.fetchall()

    # Juntamos todos os não conciliados de origem OFX para aplicar a automação das regras
    todas_listas_nao_conc = [
        (cartoes_nao_conc, cartoes_conc, "cartoes"),
        (boletos_nao_conc, boletos_conc, "boletos"),
        (outros_nao_conc, outros_conc, "outros"),
    ]

    for lista_nao_conc, lista_conc, nome_bloco in todas_listas_nao_conc:
      itens_para_processar = list(lista_nao_conc)

      for item_nao_conc in itens_para_processar:
        if item_nao_conc["origem"] != "OFX":
          continue

        dados_item = item_nao_conc["item"]
        historico_item = str(dados_item["historico"]).upper()

        regra_encontrada = None
        for regra in regras:
          c_cfo, c_custo, hist_regra, hist_busca = regra
          if hist_busca and hist_busca.upper() in historico_item:
            regra_encontrada = {
                "CODCFO": c_cfo,
                "CCUSTO": c_custo,
                "HISTORICO": hist_regra,
            }
            break

        if regra_encontrada:
          cursor.execute("SELECT MAX(IDLAN) FROM FLAN")
          res_lan = cursor.fetchone()
          novo_idlan = (res_lan[0] or 0) + 1

          cursor.execute("SELECT MAX(IDEXTRATO) FROM FEXTRATO")
          res_ext = cursor.fetchone()
          novo_idextrato = (res_ext[0] or 0) + 1

          valor_item = dados_item["valor"]
          pagrec = "P" if valor_item < 0 else "R"
          codcaixa = "02" if str(banco_esperado) == "748" else "07"
          valor_abs = abs(Decimal(str(valor_item)))
          data_item = dados_item["data"]
          agora = datetime.now()

          sql_flan = """
                        INSERT INTO FLAN (
                            IDLAN, CODEMPRESA, CODFILIAL, CODCFO, CODTDO, NUMERODOCUMENTO, 
                            PARCELA, PAGREC, CCUSTO, DATAVENCIMENTO, DATAEMISSAO, 
                            DATABAIXA, DATAPREVBAIXA, HISTORICO, CODMOEVALORORIGINAL, 
                            CODCAIXA, VALORORIGINAL, VALORBAIXADO, STATUSLAN, 
                            DATADIGITACAO, NPARCELA, CODFORMA, HISTORICOBAIXA, DATADIGITACAOBAIXA
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
          cursor.execute(
              sql_flan,
              (
                  novo_idlan,
                  1,
                  1,
                  regra_encontrada["CODCFO"],
                  "DP",
                  "AUTOS",
                  1,
                  pagrec,
                  regra_encontrada["CCUSTO"],
                  data_item,
                  data_item,
                  data_item,
                  data_item,
                  regra_encontrada["HISTORICO"],
                  "R$",
                  codcaixa,
                  valor_abs,
                  valor_abs,
                  "B",
                  agora,
                  1,
                  "01",
                  regra_encontrada["HISTORICO"],
                  agora,
              ),
          )

          sql_fextrato = """
                        INSERT INTO FEXTRATO (
                            IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, VALOR, IDLAN, 
                            COMPENSADO, HISTORICO, NUMERODOCUMENTO, DATACOMPENSACAO, 
                            DATA, DATADIGITACAO, CCUSTO, CODFORMA, DATAVENCIMENTO, 
                            CODCFO, CONCILIADO, INTEGRADONFE
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
          cursor.execute(
              sql_fextrato,
              (
                  novo_idextrato,
                  1,
                  1,
                  codcaixa,
                  valor_item,
                  novo_idlan,
                  "T",
                  regra_encontrada["HISTORICO"],
                  "AUTOS",
                  data_item,
                  data_item,
                  agora,
                  regra_encontrada["CCUSTO"],
                  "01",
                  data_item,
                  regra_encontrada["CODCFO"],
                  "F",
                  "F",
              ),
          )

          conexao.commit()

          lista_nao_conc.remove(item_nao_conc)
          lista_conc.append({
              "ofx": dados_item,
              "bd": {
                  "data": data_item,
                  "valor": valor_item,
                  "historico": regra_encontrada["HISTORICO"],
              },
          })
          print(
              f"[{nome_bloco.upper()} - REGRA APLICADA] Data:"
              f" {data_item.strftime('%d/%m/%Y')} | '{dados_item['historico']}'"
              f" -> Inserido no FLAN/FEXTRATO (IDLAN: {novo_idlan})"
          )

  except Exception as e:
    conexao.rollback()
    print(f"[ERRO] Falha ao processar regras nos blocos: {e}")
  finally:
    cursor.close()
    conexao.close()
from datetime import datetime
from decimal import Decimal
import fdb


from datetime import datetime
from decimal import Decimal
import fdb


def processar_baixa_cartoes(
    banco_esperado, caminho_bd, cartoes_ofx_pendentes, data_ofx
):
  """Executa a validação e a baixa automática completa de cartões (Débito e Crédito)

  garantindo que TODOS os títulos em aberto do Caixa 03 sejam marcados como
  COMPENSADO = 'T'.
  """
  LIMITE_TAXA_DEBITO = Decimal("0.03")  # 3%
  LIMITE_TAXA_CREDITO = Decimal("0.15")  # 15%

  codcaixa_banco = "02" if int(banco_esperado) == 748 else "07"

  print("\n--- [DEBUG CARTÕES] Iniciando processamento de baixa ---")

  cartoes_debito_ofx = []
  cartoes_credito_ofx = []

  for item in cartoes_ofx_pendentes:
    hist = str(item["item"]["historico"]).upper()
    if "DEBITO" in hist or "DÉBITO" in hist:
      cartoes_debito_ofx.append(item["item"])
    else:
      cartoes_credito_ofx.append(item["item"])

  total_liquido_debito = sum(i["valor"] for i in cartoes_debito_ofx)
  total_liquido_credito = sum(i["valor"] for i in cartoes_credito_ofx)

  print(f"Total Líquido Débito (OFX): R$ {total_liquido_debito:,.2f}")
  print(f"Total Líquido Crédito (OFX): R$ {total_liquido_credito:,.2f}")

  conexao = fdb.connect(
      dsn=caminho_bd,
      user="SYSDBA",
      password="masterkey",
      charset="ISO8859_1",
  )
  cursor = conexao.cursor()

  def proximo_id():
    cursor.execute("SELECT MAX(IDEXTRATO) FROM FEXTRATO")
    res = cursor.fetchone()
    max_id = res[0] if res and res[0] is not None else 0
    return max_id + 1

  try:
    # --- PROCESSAMENTO DE DÉBITO ---
    if total_liquido_debito > 0:
      cursor.execute("""
                SELECT IDEXTRATO, VALOR, NUMERODOCUMENTO, HISTORICO, CODFORMA 
                FROM FEXTRATO 
                WHERE CODCAIXA = '03' AND COMPENSADO = 'F' AND CODFORMA IN ('04', '18')
            """)
      titulos_aberto = cursor.fetchall()
      print(f"[DEBUG DÉBITO] Títulos encontrados no BD: {len(titulos_aberto)}")

      if titulos_aberto:
        total_bruto_debito = sum(
            Decimal(str(t[1])) for t in titulos_aberto if t[1] is not None
        )
        num_doc = titulos_aberto[0][2]
        historico_orig = titulos_aberto[0][3]

        taxa_calculada = (
            total_bruto_debito - total_liquido_debito
        ) / total_bruto_debito

        if 0 <= taxa_calculada <= LIMITE_TAXA_DEBITO:
          print(
              f"[BAIXA AUTOMÁTICA] Débito validado! Bruto: R$"
              f" {total_bruto_debito:,.2f} | Líquido: R$"
              f" {total_liquido_debito:,.2f}"
          )

          # Marca TODOS os títulos em aberto deste lote como COMPENSADO = 'T'
          for t in titulos_aberto:
            cursor.execute(
                """
                        UPDATE FEXTRATO 
                        SET COMPENSADO = 'T', DATACOMPENSACAO = ? 
                        WHERE IDEXTRATO = ?
                    """,
                (
                    data_ofx,
                    t[0],
                ),
            )

          # Inserção 1 (Saída Caixa 03)
          novo_id_1 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, TABELA3, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, '03', 'S', ?, 'T', ?, ?, ?, ?, ?, ?, '1.01.001', '05', '2', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_1,
                  -total_bruto_debito,
                  historico_orig,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          # Inserção 2 (Entrada Banco Bruto)
          novo_id_2 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, ?, 'D', ?, 'T', ?, ?, ?, ?, ?, ?, '1.01.001', '01', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_2,
                  codcaixa_banco,
                  total_bruto_debito,
                  historico_orig,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          # Inserção 3 (Taxa do Cartão)
          valor_taxa = total_bruto_debito - total_liquido_debito
          novo_id_3 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, ETAXACARTAO, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, ?, 'S', ?, 'T', 'TAXA CARTAO DE DEBITO', ?, ?, ?, ?, ?, '3.12.007', '01', 'T', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_3,
                  codcaixa_banco,
                  -valor_taxa,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          conexao.commit()
          print("[SUCESSO] Baixa de débito efetivada no banco de dados!")
        else:
          print(
              f"[ALERTA] Taxa de Débito ({taxa_calculada * 100:.2f}%) ultrapassou"
              f" o limite de {LIMITE_TAXA_DEBITO * 100}%."
          )
      else:
        print(
            "[DEBUG DÉBITO] Nenhum título em aberto encontrado no Caixa '03' para"
            " as formas '04' ou '18'."
        )

    # --- PROCESSAMENTO DE CRÉDITO ---
    if total_liquido_credito > 0:
      cursor.execute("""
                SELECT IDEXTRATO, VALOR, NUMERODOCUMENTO, HISTORICO, CODFORMA 
                FROM FEXTRATO 
                WHERE CODCAIXA = '03' AND COMPENSADO = 'F' AND CODFORMA IN ('05', '17')
            """)
      titulos_aberto = cursor.fetchall()
      print(f"[DEBUG CRÉDITO] Títulos encontrados no BD: {len(titulos_aberto)}")

      if titulos_aberto:
        total_bruto_credito = sum(
            Decimal(str(t[1])) for t in titulos_aberto if t[1] is not None
        )
        num_doc = titulos_aberto[0][2]
        historico_orig = titulos_aberto[0][3]

        taxa_calculada = (
            total_bruto_credito - total_liquido_credito
        ) / total_bruto_credito

        print(
            f"[DEBUG CRÉDITO] Bruto BD: {total_bruto_credito} | Líquido OFX:"
            f" {total_liquido_credito}"
        )
        print(
            f"[DEBUG CRÉDITO] Taxa calculada: {taxa_calculada * 100:.2f}%"
            f" (Limite: {LIMITE_TAXA_CREDITO * 100}%)"
        )

        if 0 <= taxa_calculada <= LIMITE_TAXA_CREDITO:
          print(
              f"[BAIXA AUTOMÁTICA] Crédito validado! Bruto: R$"
              f" {total_bruto_credito:,.2f} | Líquido: R$"
              f" {total_liquido_credito:,.2f}"
          )

          # Marca TODOS os títulos em aberto deste lote como COMPENSADO = 'T'
          for t in titulos_aberto:
            cursor.execute(
                """
                        UPDATE FEXTRATO 
                        SET COMPENSADO = 'T', DATACOMPENSACAO = ? 
                        WHERE IDEXTRATO = ?
                    """,
                (
                    data_ofx,
                    t[0],
                ),
            )

          # Inserção 1 (Saída Caixa 03)
          novo_id_1 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, TABELA3, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, '03', 'S', ?, 'T', ?, ?, ?, ?, ?, ?, '1.01.001', '05', '2', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_1,
                  -total_bruto_credito,
                  historico_orig,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          # Inserção 2 (Entrada Banco Bruto)
          novo_id_2 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, ?, 'D', ?, 'T', ?, ?, ?, ?, ?, ?, '1.01.001', '01', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_2,
                  codcaixa_banco,
                  total_bruto_credito,
                  historico_orig,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          # Inserção 3 (Taxa do Cartão)
          valor_taxa = total_bruto_credito - total_liquido_credito
          novo_id_3 = proximo_id()
          cursor.execute(
                """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, ETAXACARTAO, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, ?, 'S', ?, 'T', 'TAXA CARTAO DE DEBITO', ?, ?, ?, ?, ?, '3.12.007', '01', 'T', 'Receb Cartão CARTÕES')
                """,
              (
                  novo_id_3,
                  codcaixa_banco,
                  -valor_taxa,
                  num_doc,
                  data_ofx,
                  data_ofx,
                  datetime.now(),
                  data_ofx,
              ),
          )

          conexao.commit()
          print("[SUCESSO] Baixa de crédito efetivada no banco de dados!")
        else:
          print(
              f"[ALERTA] Taxa de Crédito ({taxa_calculada * 100:.2f}%)"
              f" ultrapassou o limite de {LIMITE_TAXA_CREDITO * 100}%."
          )
      else:
        print(
            "[DEBUG CRÉDITO] Nenhum título em aberto encontrado no Caixa '03' para"
            " as formas '05' ou '17'."
        )

  except Exception as e:
    conexao.rollback()
    print(f"[ERRO CRÍTICO] Falha ao processar baixa de cartões: {e}")
  finally:
    cursor.close()
    conexao.close()
  print("--- [DEBUG CARTÕES] Fim do processamento ---\n")