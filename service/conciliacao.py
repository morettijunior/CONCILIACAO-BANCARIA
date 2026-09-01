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