from datetime import datetime
from decimal import Decimal
import fdb
from .bd import obter_proximo_id


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

    # Obter o intervalo de datas do OFX para validação em lote
    dt_inicio = extrato_ofx[0]["data"].date() if extrato_ofx and hasattr(extrato_ofx[0]["data"], "date") else (extrato_ofx[0]["data"] if extrato_ofx else None)
    dt_fim = extrato_ofx[-1]["data"].date() if extrato_ofx and hasattr(extrato_ofx[-1]["data"], "date") else (extrato_ofx[-1]["data"] if extrato_ofx else None)

    # 3. VALIDAÇÃO EM LOTE PARA CARTÕES (Considerando intervalo de datas e taxa + Num. Documento)
    cartoes_ofx_pendentes = [
        x for x in cartoes_nao_conciliado if x["origem"] == "OFX"
    ]

    if cartoes_ofx_pendentes and dt_inicio and dt_fim:
        total_ofx_cartoes = sum(item["item"]["valor"] for item in cartoes_ofx_pendentes)

        # Filtra os pendentes do BD que estão dentro do intervalo de datas do OFX
        bd_no_periodo = []
        for x in bd_pendentes:
            data_x = x.get("data")
            if data_x:
                data_x_formatada = data_x.date() if hasattr(data_x, "date") else data_x
                if dt_inicio <= data_x_formatada <= dt_fim:
                    bd_no_periodo.append(x)

        # Passo 1: Encontra no BD os lançamentos de "TAXA CARTAO" (negativos) no período
        itens_taxa_bd = [
            x for x in bd_no_periodo 
            if "TAXA CARTAO" in str(x.get("historico", "")).upper() and x.get("valor", 0) < 0
        ]

        if itens_taxa_bd:
            # Passo 2: Para cada taxa encontrada, acha o par positivo com o mesmo NUMERODOCUMENTO no período
            lotes_cartao_bd = []
            
            for taxa in itens_taxa_bd:
                num_doc = taxa.get("numerodocumento")
                if num_doc:
                    for item_bd in bd_no_periodo:
                        if (
                            item_bd.get("numerodocumento") == num_doc
                            and item_bd.get("valor", 0) > 0
                            and item_bd not in lotes_cartao_bd
                        ):
                            lotes_cartao_bd.append(item_bd)
                            lotes_cartao_bd.append(taxa)
                            break

            if lotes_cartao_bd:
                # Passo 3: Soma o líquido de todos os pares encontrados no período (positivos - taxas)
                total_bd_cartoes = sum(b["valor"] for b in lotes_cartao_bd)

                # Se o total líquido do lote no período bater com o total dos cartões pendentes no OFX
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

    # 4. VALIDAÇÃO EM LOTE PARA BOLETOS
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


def inserir_transferencia_fextrato(cursor, codcaixa_origem, codcaixa_destino, valor, data_item, historico, cod_empresa=1):
    """Insere um par de lançamentos de transferência diretamente na tabela FEXTRATO 
    (um débito na origem e um crédito no destino), sem criar FLAN.
    """
    valor_dec = Decimal(str(valor))
    valor_negativo = -abs(valor_dec)
    valor_positivo = abs(valor_dec)
    agora = datetime.now()

    # Obtém IDs para os dois extratos usando o GAUTOINC padronizado
    id_origem = obter_proximo_id(cursor, "FEXTRATO", "IDEXTRATO", cod_empresa)
    id_destino = obter_proximo_id(cursor, "FEXTRATO", "IDEXTRATO", cod_empresa)

    sql_fextrato = """
        INSERT INTO FEXTRATO (
            IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, IDLAN, 
            COMPENSADO, HISTORICO, DATACOMPENSACAO, DATA, DATADIGITACAO, 
            DATAVENCIMENTO, CONCILIADO, INTEGRADONFE, CODCAIXATRANSF, IDEXTTRANSF
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'T', 'F', ?, ?)
    """

    # 1. Lançamento de saída (Débito/Transferência na conta de origem)
    cursor.execute(
        sql_fextrato,
        (
            id_origem,
            cod_empresa,
            1,
            str(codcaixa_origem),
            'S',
            valor_negativo,
            'T',
            historico,
            data_item,
            data_item,
            agora,
            data_item,
            str(codcaixa_destino),
            id_destino,
        ),
    )

    # 2. Lançamento de entrada (Crédito na conta de destino)
    cursor.execute(
        sql_fextrato,
        (
            id_destino,
            cod_empresa,
            1,
            str(codcaixa_destino),
            'D',
            valor_positivo,
            'T',
            historico,
            data_item,
            data_item,
            agora,
            data_item,
            str(codcaixa_origem),
            id_origem,
        ),
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
    insere no Firebird (suportando regras normais ou transferência direta) e migra para as respectivas listas de conciliados.
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
            "SELECT CODCFO, CCUSTO, HISTORICO, HISTORICO_BUSCA, CODCAIXA_ORIGEM, CODCAIXA_DESTINO FROM TREGRAOFX"
        )
        regras = cursor.fetchall()

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
                    c_cfo, c_custo, hist_regra, hist_busca, cx_origem, cx_destino = regra
                    if hist_busca and hist_busca.upper() in historico_item:
                        regra_encontrada = {
                            "CODCFO": c_cfo,
                            "CCUSTO": c_custo,
                            "HISTORICO": hist_regra,
                            "CODCAIXA_ORIGEM": cx_origem,
                            "CODCAIXA_DESTINO": cx_destino,
                        }
                        break

                if regra_encontrada:
                    valor_item = dados_item["valor"]
                    data_item = dados_item["data"]
                    historico_final = regra_encontrada["HISTORICO"] or dados_item["historico"]

                    # SE A REGRA POSSUI CAIXA DE ORIGEM E DESTINO, É UMA TRANSFERÊNCIA
                    if regra_encontrada.get("CODCAIXA_ORIGEM") and regra_encontrada.get("CODCAIXA_DESTINO"):
                        inserir_transferencia_fextrato(
                            cursor,
                            regra_encontrada["CODCAIXA_ORIGEM"],
                            regra_encontrada["CODCAIXA_DESTINO"],
                            valor_item,
                            data_item,
                            historico_final
                        )
                        conexao.commit()

                        lista_nao_conc.remove(item_nao_conc)
                        lista_conc.append({
                            "ofx": dados_item,
                            "bd": {
                                "data": data_item,
                                "valor": valor_item,
                                "historico": historico_final,
                            },
                        })
                        print(
                            f"[{nome_bloco.upper()} - REGRA TRANSFERÊNCIA APLICADA] Data: {data_item.strftime('%d/%m/%Y')} | "
                            f"De: {regra_encontrada['CODCAIXA_ORIGEM']} Para: {regra_encontrada['CODCAIXA_DESTINO']}"
                        )

                    else:
                        # FLUXO NORMAL (Gera FLAN e FEXTRATO)
                        novo_idlan = obter_proximo_id(cursor, "FLAN", "IDLAN", 1)
                        novo_idextrato = obter_proximo_id(cursor, "FEXTRATO", "IDEXTRATO", 1)

                        pagrec = "P" if valor_item < 0 else "R"
                        codcaixa = "02" if str(banco_esperado) == "748" else "07"
                        valor_abs = abs(Decimal(str(valor_item)))
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
                                historico_final,
                                "R$",
                                codcaixa,
                                valor_abs,
                                valor_abs,
                                "B",
                                agora,
                                1,
                                "01",
                                historico_final,
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
                                historico_final,
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
                                "historico": historico_final,
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
                    novo_id_1 = obter_proximo_id(cursor, "FEXTRATO")
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
                    novo_id_2 = obter_proximo_id(cursor, "FEXTRATO")
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
                    novo_id_3 = obter_proximo_id(cursor, "FEXTRATO")
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

                if 0 <= taxa_calculada <= LIMITE_TAXA_CREDITO:
                    print(
                        f"[BAIXA AUTOMÁTICA] Crédito validado! Bruto: R$"
                        f" {total_bruto_credito:,.2f} | Líquido: R$"
                        f" {total_liquido_credito:,.2f}"
                    )

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
                    novo_id_1 = obter_proximo_id(cursor, "FEXTRATO")
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
                    novo_id_2 = obter_proximo_id(cursor, "FEXTRATO")
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
                    novo_id_3 = obter_proximo_id(cursor, "FEXTRATO")
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