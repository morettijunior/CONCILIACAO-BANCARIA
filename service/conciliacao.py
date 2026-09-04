from datetime import datetime
from decimal import Decimal
import json
import os
import fdb
from .bd import obter_proximo_id
from datetime import datetime, timedelta

# Pasta onde os arquivos JSON de controle de cartões conciliados serão salvos
PASTA_CONTROLE_JSON = "controle_cartoes"

def garantir_pasta_json():
    if not os.path.exists(PASTA_CONTROLE_JSON):
        os.makedirs(PASTA_CONTROLE_JSON)

def carregar_json_conciliado(data_str, tipo):
    """Passo 3: Verifica se já existe JSON registrando a conciliação desse grupo/data."""
    garantir_pasta_json()
    caminho_arquivo = os.path.join(PASTA_CONTROLE_JSON, f"cartoes_{tipo}_{data_str}.json")
    if os.path.exists(caminho_arquivo):
        try:
            with open(caminho_arquivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def salvar_json_conciliado(data_str, tipo, dados):
    """Passo 5: Salva o grupo conciliado em arquivo JSON após sucesso no BD."""
    garantir_pasta_json()
    caminho_arquivo = os.path.join(PASTA_CONTROLE_JSON, f"cartoes_{tipo}_{data_str}.json")
    try:
        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[ERRO JSON] Falha ao salvar controle para {tipo} em {data_str}: {e}")


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

    # 2. Cruzamento 1 para 1 normal (Apenas para Boletos e Outros)
    ofx_pendentes = list(extrato_ofx)

    for item_ofx in ofx_pendentes:
        if item_ofx["bloco"] == "cartoes":
            cartoes_nao_conciliado.append({"origem": "OFX", "item": item_ofx})
            continue

        encontrado = False
        for item_bd in bd_pendentes:
            if (
                item_ofx["data"] == item_bd["data"]
                and item_ofx["valor"] == item_bd["valor"]
            ):
                par = {"ofx": item_ofx, "bd": item_bd}
                if item_ofx["bloco"] == "boletos":
                    boletos_conciliado.append(par)
                else:
                    outros_conciliado.append(par)

                bd_pendentes.remove(item_bd)
                encontrado = True
                break

        if not encontrado:
            nao_conc_item = {"origem": "OFX", "item": item_ofx}
            if item_ofx["bloco"] == "boletos":
                boletos_nao_conciliado.append(nao_conc_item)
            else:
                outros_nao_conciliado.append(nao_conc_item)

    # =========================================================================
    # PASSO 1, 2 e 3 (Cache JSON) APLICADOS NA CONCILIAÇÃO DE CARTÕES
    # =========================================================================
    cartoes_ofx_pendentes = [
        x for x in cartoes_nao_conciliado if x["origem"] == "OFX"
    ]

    if cartoes_ofx_pendentes:
        for item_wrapper in cartoes_ofx_pendentes:
            item_ofx = item_wrapper["item"]
            hist = str(item_ofx.get("historico", "")).upper()
            tipo = "debito" if ("DEBITO" in hist or "DÉBITO" in hist) else "credito"
            
            dt = item_ofx.get("data")
            dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]

            # PASSO 3: Conferência dos grupos OFX com o JSON
            registro_json = carregar_json_conciliado(dt_str, tipo)
            if registro_json:
                # Já foi conciliado anteriormente via arquivo JSON
                cartoes_nao_conciliado.remove(item_wrapper)
                cartoes_conciliado.append({
                    "ofx": item_ofx,
                    "bd": registro_json.get("bd_referencia", {})
                })

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
    valor_dec = Decimal(str(valor))
    valor_negativo = -abs(valor_dec)
    valor_positivo = abs(valor_dec)
    agora = datetime.now()

    id_origem = obter_proximo_id(cursor, "FEXTRATO", "IDEXTRATO", cod_empresa)
    id_destino = obter_proximo_id(cursor, "FEXTRATO", "IDEXTRATO", cod_empresa)

    sql_fextrato = """
        INSERT INTO FEXTRATO (
            IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, IDLAN, 
            COMPENSADO, HISTORICO, DATACOMPENSACAO, DATA, DATADIGITACAO, 
            DATAVENCIMENTO, CONCILIADO, INTEGRADONFE, CODCAIXATRANSF, IDEXTTRANSF
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'T', 'F', ?, ?)
    """

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
                    else:
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
    seguindo os Passos 1, 2, 4 e 5 (com controle de JSON por grupo/data).
    """
    LIMITE_TAXA_DEBITO = Decimal("0.03")  # 3%
    LIMITE_TAXA_CREDITO = Decimal("0.15") # 15%

    codcaixa_banco = "02" if int(banco_esperado) == 748 else "07"

    print("\n--- [DEBUG CARTÕES] Iniciando processamento e baixa por grupos ---")

    # PASSO 1: Receber do OFX e dividir em 02 listas (Crédito e Débito)
    lista_credito_ofx = []
    lista_debito_ofx = []

    for item_obj in cartoes_ofx_pendentes:
        item = item_obj["item"] if isinstance(item_obj, dict) and "item" in item_obj else item_obj
        hist = str(item.get("historico", "")).upper()
        if "DEBITO" in hist or "DÉBITO" in hist:
            lista_debito_ofx.append(item)
        else:
            lista_credito_ofx.append(item)

    # PASSO 2: Dividir as listas Crédito/Débito em grupos por data
    grupos_por_data = {}

    def agrupar_por_data(itens, tipo):
        for item in itens:
            dt = item.get("data")
            dt_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            chave = f"{tipo}_{dt_str}"
            if chave not in grupos_por_data:
                grupos_por_data[chave] = {
                    "tipo": tipo,
                    "data_str": dt_str,
                    "data_obj": dt,
                    "itens": []
                }
            grupos_por_data[chave]["itens"].append(item)

    agrupar_por_data(lista_credito_ofx, "credito")
    agrupar_por_data(lista_debito_ofx, "debito")

    conexao = fdb.connect(
        dsn=caminho_bd,
        user="SYSDBA",
        password="masterkey",
        charset="ISO8859_1",
    )
    cursor = conexao.cursor()

    try:
        for chave_grupo, grupo in grupos_por_data.items():
            tipo = grupo["tipo"]
            dt_str = grupo["data_str"]
            dt_obj = grupo["data_obj"]
            itens_grupo = grupo["itens"]

            total_liquido_grupo = sum(i["valor"] for i in itens_grupo)

            # PASSO 3: Conferência com o JSON (se já foi salvo, pula o banco)
            if carregar_json_conciliado(dt_str, tipo):
                print(f"[CACHE JSON] Grupo {chave_grupo} já conciliado anteriormente. Ignorando baixa duplicada.")
                continue

            # PASSO 4: Inserção no BD utilizando as regras de % de taxas
            print(f"[PROCESSAMENTO] Avaliando grupo {chave_grupo} | Total Líquido: R$ {total_liquido_grupo:,.2f}")

            formas_busca = ('04', '18') if tipo == "debito" else ('05', '17')
            limite_taxa = LIMITE_TAXA_DEBITO if tipo == "debito" else LIMITE_TAXA_CREDITO

            data_limite_bd = dt_obj - timedelta(days=1)
            cursor.execute("""
                SELECT IDEXTRATO, VALOR, NUMERODOCUMENTO, HISTORICO, CODFORMA 
                FROM FEXTRATO 
                WHERE CODCAIXA = '03' AND COMPENSADO = 'F' AND CODFORMA IN (?, ?) AND DATA <= ?
            """, (formas_busca[0], formas_busca[1], data_limite_bd))
            titulos_aberto = cursor.fetchall()

            if not titulos_aberto:
                print(f"[ALERTA] Nenhum título em aberto no Caixa 03 para o grupo {chave_grupo}.")
                continue

            total_bruto = sum(Decimal(str(t[1])) for t in titulos_aberto if t[1] is not None)
            num_doc = titulos_aberto[0][2]
            historico_orig = titulos_aberto[0][3]

            taxa_calculada = (total_bruto - total_liquido_grupo) / total_bruto

            if 0 <= taxa_calculada <= limite_taxa:
                print(f"[VALIDADO] Grupo {chave_grupo} aprovado! Bruto: R$ {total_bruto:,.2f} | Taxa: {taxa_calculada*100:.2f}%")

                for t in titulos_aberto:
                    cursor.execute(
                        "UPDATE FEXTRATO SET COMPENSADO = 'T', DATACOMPENSACAO = ? WHERE IDEXTRATO = ?",
                        (dt_obj, t[0])
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
                    (novo_id_1, -total_bruto, historico_orig, num_doc, dt_obj, dt_obj, datetime.now(), dt_obj),
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
                    (novo_id_2, codcaixa_banco, total_bruto, historico_orig, num_doc, dt_obj, dt_obj, datetime.now(), dt_obj),
                )

                # Inserção 3 (Taxa do Cartão)
                valor_taxa = total_bruto - total_liquido_grupo
                novo_id_3 = obter_proximo_id(cursor, "FEXTRATO")
                nome_historico_taxa = "TAXA CARTAO DE DEBITO" if tipo == "debito" else "TAXA CARTAO DE CREDITO"
                cursor.execute(
                    """
                    INSERT INTO FEXTRATO (
                        IDEXTRATO, CODEMPRESA, CODFILIAL, CODCAIXA, TIPO, VALOR, COMPENSADO, 
                        HISTORICO, NUMERODOCUMENTO, DATA, DATACOMPENSACAO, DATADIGITACAO, 
                        DATAVENCIMENTO, CCUSTO, CODFORMA, ETAXACARTAO, HISTCOMPESACAO
                    )
                    VALUES (?, 1, 1, ?, 'S', ?, 'T', ?, ?, ?, ?, ?, ?, '3.12.007', '01', 'T', 'Receb Cartão CARTÕES')
                    """,
                    (novo_id_3, codcaixa_banco, -valor_taxa, nome_historico_taxa, num_doc, dt_obj, dt_obj, datetime.now(), dt_obj),
                )

                conexao.commit()
                print(f"[SUCESSO BD] Grupo {chave_grupo} baixado com sucesso!")

                # PASSO 5: Salvar a lista em um arquivo JSON após sucesso no BD
                dados_para_json = {
                    "data": dt_str,
                    "tipo": tipo,
                    "total_liquido": str(total_liquido_grupo),
                    "total_bruto": str(total_bruto),
                    "bd_referencia": {
                        "data": dt_str,
                        "valor": str(total_liquido_grupo),
                        "historico": historico_orig
                    }
                }
                salvar_json_conciliado(dt_str, tipo, dados_para_json)
            else:
                print(f"[ALERTA TAXA] Taxa calculada ({taxa_calculada*100:.2f}%) fora do limite para o grupo {chave_grupo}.")

    except Exception as e:
        conexao.rollback()
        print(f"[ERRO CRÍTICO CARTÕES] {e}")
    finally:
        cursor.close()
        conexao.close()
    print("--- [DEBUG CARTÕES] Fim do processamento ---\n")