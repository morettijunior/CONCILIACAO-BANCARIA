from datetime import datetime
from decimal import Decimal
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from service.bd import (
    consultar_extrato,
    excluir_regra,
    inserir_regra,
    listar_regras,
    saldo_sistema,
)
from service.conciliacao import comparar_listas, inserir_itens
from service.config import carregar_config, salvar_config
from service.ofx import ler_ofx, saldo_final

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class JanelaGerenciarRegras(ctk.CTkToplevel):
  """Janela secundária para gerenciar as regras de OFX"""

  def __init__(self, parent):
    super().__init__(parent)
    self.title("Gerenciamento de Regras OFX")
    self.geometry("680x580")
    self.resizable(False, False)

    self.transient(parent)
    self.grab_set()

    lbl = ctk.CTkLabel(
        self, text="Cadastro e Manutenção de Regras", font=("Arial", 18, "bold")
    )
    lbl.pack(pady=15)

    form_frame = ctk.CTkFrame(self)
    form_frame.pack(pady=5, padx=20, fill="x")

    ctk.CTkLabel(form_frame, text="Cód. CFO:").grid(
        row=0, column=0, padx=5, pady=5, sticky="w"
    )
    self.entry_cfo = ctk.CTkEntry(form_frame, width=120)
    self.entry_cfo.grid(row=0, column=1, padx=5, pady=5)

    ctk.CTkLabel(form_frame, text="C. Custo:").grid(
        row=0, column=2, padx=5, pady=5, sticky="w"
    )
    self.entry_ccusto = ctk.CTkEntry(form_frame, width=120)
    self.entry_ccusto.grid(row=0, column=3, padx=5, pady=5)

    ctk.CTkLabel(form_frame, text="Histórico Padrão:").grid(
        row=1, column=0, padx=5, pady=5, sticky="w"
    )
    self.entry_hist = ctk.CTkEntry(form_frame, width=350)
    self.entry_hist.grid(row=1, column=1, columnspan=3, padx=5, pady=5)

    ctk.CTkLabel(form_frame, text="Texto de Busca (OFX):").grid(
        row=2, column=0, padx=5, pady=5, sticky="w"
    )
    self.entry_busca = ctk.CTkEntry(form_frame, width=350)
    self.entry_busca.grid(row=2, column=1, columnspan=3, padx=5, pady=5)

    btn_salvar = ctk.CTkButton(
        form_frame,
        text="Inserir Nova Regra",
        command=self.salvar_regra,
        fg_color="#28a745",
        hover_color="#218838",
    )
    btn_salvar.grid(row=3, column=1, columnspan=2, pady=10)

    ctk.CTkLabel(
        self, text="Regras Ativas (com ID de Exclusão):", font=("Arial", 14, "bold")
    ).pack(anchor="w", padx=20, pady=(15, 5))

    self.lista_texto = ctk.CTkTextbox(
        self, font=("Consolas", 11), width=630, height=180
    )
    self.lista_texto.pack(padx=20, pady=5)

    del_frame = ctk.CTkFrame(self)
    del_frame.pack(pady=10, padx=20, fill="x")

    ctk.CTkLabel(del_frame, text="Digite o ID/Número da regra para excluir:").pack(
        side="left", padx=5
    )
    self.entry_del_id = ctk.CTkEntry(del_frame, width=80)
    self.entry_del_id.pack(side="left", padx=5)

    btn_excluir = ctk.CTkButton(
        del_frame,
        text="Excluir por ID",
        command=self.remover_regra,
        fg_color="#dc3545",
        hover_color="#c82333",
    )
    btn_excluir.pack(side="left", padx=10)

    self.regras_cache = []
    self.atualizar_lista()

  def atualizar_lista(self):
    self.lista_texto.delete("0.0", "end")
    self.regras_cache = listar_regras()

    if not self.regras_cache:
      self.lista_texto.insert("0.0", "Nenhuma regra cadastrada.\n")
      return

    for idx, r in enumerate(self.regras_cache, start=1):
      cfo, cc, hist, busca = r
      linha = f"[{idx}] CFO: {cfo} | CC: {cc} | Busca: {busca} -> Hist: {hist}\n"
      self.lista_texto.insert("end", linha)

  def salvar_regra(self):
    cfo = self.entry_cfo.get()
    cc = self.entry_ccusto.get()
    hist = self.entry_hist.get()
    busca = self.entry_busca.get()

    if not cfo or not cc or not hist or not busca:
      messagebox.showwarning(
          "Atenção", "Todos os campos devem ser preenchidos!"
      )
      return

    sucesso = inserir_regra(cfo, cc, hist, busca)
    if sucesso:
      messagebox.showinfo("Sucesso", "Regra inserida com sucesso!")
      self.entry_cfo.delete(0, "end")
      self.entry_ccusto.delete(0, "end")
      self.entry_hist.delete(0, "end")
      self.entry_busca.delete(0, "end")
      self.atualizar_lista()
    else:
      messagebox.showerror(
          "Erro", "Falha ao inserir regra. Verifique o console."
      )

  def remover_regra(self):
    digitado = self.entry_del_id.get().strip()
    if not digitado.isdigit():
      messagebox.showwarning(
          "Atenção", "Digite um número de ID válido listado na tela."
      )
      return

    indice = int(digitado) - 1

    if indice < 0 or indice >= len(self.regras_cache):
      messagebox.showerror("Erro", "ID informado não existe na listagem.")
      return

    regra_selecionada = self.regras_cache[indice]
    busca_alvo = regra_selecionada[3]

    if messagebox.askyesno(
        "Confirmar Exclusão",
        f"Deseja realmente excluir a regra ID [{digitado}] (Busca: {busca_alvo})?",
    ):
      sucesso = excluir_regra(busca_alvo)
      if sucesso:
        messagebox.showinfo("Sucesso", "Regra excluída com sucesso!")
        self.entry_del_id.delete(0, "end")
        self.atualizar_lista()
      else:
        messagebox.showerror("Erro", "Falha ao excluir regra no banco de dados.")


class AppConciliacao(ctk.CTk):

  def __init__(self):
    super().__init__()

    self.title("Sistema de Conciliação Bancária")
    self.geometry("750x680")
    self.resizable(False, False)

    # Carrega as configurações salvas (ou padrões)
    self.config = carregar_config()

    self.label_titulo = ctk.CTkLabel(
        self, text="Conciliação Bancária TGA", font=("Arial", 22, "bold")
    )
    self.label_titulo.pack(pady=10)

    self.btn_regras = ctk.CTkButton(
        self,
        text="⚙ Gerenciar Regras OFX",
        command=self.abrir_tela_regras,
        font=("Arial", 13, "bold"),
        fg_color="#6c757d",
        hover_color="#5a6268",
        height=30,
        width=200,
    )
    self.btn_regras.pack(pady=2)

    # --- FRAME DE CONFIGURAÇÃO DE CAMINHOS ---
    self.frame_paths = ctk.CTkFrame(self)
    self.frame_paths.pack(pady=8, padx=20, fill="x")

    # Arquivo OFX
    ctk.CTkLabel(
        self.frame_paths, text="Arquivo OFX:", font=("Arial", 11, "bold")
    ).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    self.entry_ofx = ctk.CTkEntry(self.frame_paths, width=480)
    self.entry_ofx.insert(0, self.config["caminho_ofx"])
    self.entry_ofx.grid(row=0, column=1, padx=5, pady=5)
    btn_procurar_ofx = ctk.CTkButton(
        self.frame_paths,
        text="Procurar",
        width=80,
        command=self.procurar_ofx,
    )
    btn_procurar_ofx.grid(row=0, column=2, padx=5, pady=5)

    # Arquivo Banco de Dados (.fdb)
    ctk.CTkLabel(
        self.frame_paths, text="Banco Firebird:", font=("Arial", 11, "bold")
    ).grid(row=1, column=0, padx=5, pady=5, sticky="w")
    self.entry_bd = ctk.CTkEntry(self.frame_paths, width=480)
    self.entry_bd.insert(0, self.config["caminho_bd"])
    self.entry_bd.grid(row=1, column=1, padx=5, pady=5)
    btn_procurar_bd = ctk.CTkButton(
        self.frame_paths, text="Procurar", width=80, command=self.procurar_bd
    )
    btn_procurar_bd.grid(row=1, column=2, padx=5, pady=5)

    # --- FRAME DE SELEÇÃO DE BANCO ---
    self.frame_banco = ctk.CTkFrame(self)
    self.frame_banco.pack(pady=8, padx=20, fill="x")

    self.label_escolha = ctk.CTkLabel(
        self.frame_banco, text="Selecione o Banco:", font=("Arial", 14)
    )
    self.label_escolha.pack(side="left", padx=15, pady=12)

    self.banco_var = ctk.IntVar(value=748)

    self.radio_sicredi = ctk.CTkRadioButton(
        self.frame_banco,
        text="Sicredi (748)",
        variable=self.banco_var,
        value=748,
        font=("Arial", 13),
    )
    self.radio_sicredi.pack(side="left", padx=10)

    self.radio_sicoob = ctk.CTkRadioButton(
        self.frame_banco,
        text="Sicoob (756)",
        variable=self.banco_var,
        value=756,
        font=("Arial", 13),
    )
    self.radio_sicoob.pack(side="left", padx=10)

    self.btn_executar = ctk.CTkButton(
        self,
        text="Executar Conciliação",
        command=self.rodar_conciliacao,
        font=("Arial", 15, "bold"),
        fg_color="#28a745",
        hover_color="#218838",
        height=40,
    )
    self.btn_executar.pack(pady=10, padx=20, fill="x")

    self.caixa_texto = ctk.CTkTextbox(
        self, font=("Consolas", 12), width=700, height=310
    )
    self.caixa_texto.pack(pady=5, padx=20)
    self.caixa_texto.insert(
        "0.0",
        "Sistema pronto. Verifique os caminhos acima e clique em 'Executar"
        " Conciliação'.\n",
    )

  def procurar_ofx(self):
    arquivo = filedialog.askopenfilename(
        title="Selecione o arquivo OFX",
        filetypes=[("Arquivos OFX", "*.ofx"), ("Todos os arquivos", "*.*")],
    )
    if arquivo:
      self.entry_ofx.delete(0, "end")
      self.entry_ofx.insert(0, arquivo)
      self.salvar_alteracoes_config()

  def procurar_bd(self):
    arquivo = filedialog.askopenfilename(
        title="Selecione o Banco de Dados Firebird",
        filetypes=[
            ("Arquivos Firebird", "*.fdb"),
            ("Todos os arquivos", "*.*"),
        ],
    )
    if arquivo:
      self.entry_bd.delete(0, "end")
      self.entry_bd.insert(0, arquivo)
      self.salvar_alteracoes_config()

  def salvar_alteracoes_config(self):
    caminho_ofx = self.entry_ofx.get().strip()
    caminho_bd = self.entry_bd.get().strip()
    salvar_config(caminho_ofx, caminho_bd)

  def abrir_tela_regras(self):
    JanelaGerenciarRegras(self)

  def log(self, mensagem):
    self.caixa_texto.insert("end", mensagem + "\n")
    self.caixa_texto.see("end")

  def rodar_conciliacao(self):
    # Garante que qualquer alteração manual nos campos de texto seja salva
    self.salvar_alteracoes_config()

    banco_esperado = self.banco_var.get()
    nome_banco = "Sicredi" if banco_esperado == 748 else "Sicoob"
    caminho_extrato = self.entry_ofx.get().strip()
    caminho_banco = self.entry_bd.get().strip()

    self.caixa_texto.delete("0.0", "end")
    self.log(
        f"Processando conciliação para o {nome_banco} (Banco:"
        f" {banco_esperado})...\n"
    )
    self.update()

    try:
      lista_ofx = ler_ofx(banco_esperado, caminho_extrato)
      if not lista_ofx:
        self.log(
            "[AVISO] Nenhum lançamento encontrado no OFX ou falha na leitura."
        )
        return

      lista_bd = consultar_extrato(banco_esperado, caminho_extrato, caminho_banco)
      saldo_banco = saldo_final(banco_esperado, caminho_extrato)

      # Recebe as 6 listas separadas por blocos
      (
          cartoes_conc,
          cartoes_nao_conc,
          boletos_conc,
          boletos_nao_conc,
          outros_conc,
          outros_nao_conc,
      ) = comparar_listas(lista_ofx, lista_bd)

      total_conciliados = (
          len(cartoes_conc) + len(boletos_conc) + len(outros_conc)
      )
      total_nao_conciliados = (
          len(cartoes_nao_conc) + len(boletos_nao_conc) + len(outros_nao_conc)
      )

      self.log(f"-> Total de registros no OFX: {len(lista_ofx)}")
      self.log(f"-> Total de registros no BD: {len(lista_bd)}")
      self.log(f"-> Já conciliados (Total): {total_conciliados}")
      self.log(
          f"-> Não conciliados (antes das regras): {total_nao_conciliados}"
      )

      if total_nao_conciliados > 0:
        self.log(
            "\nAplicando regras automáticas aos itens não conciliados por"
            " bloco..."
        )

        class RedirecionadorPrint:

          def __init__(self, callback_log):
            self.callback_log = callback_log

          def write(self, texto):
            if texto.strip():
              self.callback_log(texto.strip())

          def flush(self):
            pass

        sys.stdout = RedirecionadorPrint(self.log)
        # Passa o caminho do BD do servidor e as 6 listas para o processador de regras
        inserir_itens(
            banco_esperado,
            caminho_banco,
            cartoes_nao_conc,
            boletos_nao_conc,
            outros_nao_conc,
            cartoes_conc,
            boletos_conc,
            outros_conc,
        )

        # NOVA ETAPA: Executa a validação e baixa automática dos cartões pendentes do OFX
        pendentes_ofx_cartoes_para_baixa = [
            x for x in cartoes_nao_conc if x["origem"] == "OFX"
        ]
        if pendentes_ofx_cartoes_para_baixa:
          from service.conciliacao import processar_baixa_cartoes

          data_ofx_base = (
              lista_ofx[0]["data"] if lista_ofx else datetime.now().date()
          )
          processar_baixa_cartoes(
              banco_esperado,
              caminho_banco,
              pendentes_ofx_cartoes_para_baixa,
              data_ofx_base,
          )

          # ATUALIZAÇÃO DA GUI: Como a baixa automática inseriu os registros no banco,
          # recarregamos a lista do BD e refazemos a comparação para a interface refletir o sucesso!
          lista_bd = consultar_extrato(banco_esperado, caminho_extrato, caminho_banco)
          (
              cartoes_conc,
              cartoes_nao_conc,
              boletos_conc,
              boletos_nao_conc,
              outros_conc,
              outros_nao_conc,
          ) = comparar_listas(lista_ofx, lista_bd)

        sys.stdout = sys.__stdout__

      # Descobre a data final com base no último item do OFX carregado para filtrar o saldo corretamente
      data_limite_ofx = None
      if lista_ofx:
        data_limite_ofx = lista_ofx[-1]["data"]

      # Pega o saldo final do sistema na tabela FEXTRATO filtrando até a data limite do OFX
      total_sistema = saldo_sistema(
          banco_esperado, caminho_banco, data_limite_ofx
      )

      total_conciliados_final = (
          len(cartoes_conc) + len(boletos_conc) + len(outros_conc)
      )

      # Filtra apenas as pendências geradas pelo OFX para a listagem
      pendentes_ofx_cartoes = [
          x for x in cartoes_nao_conc if x["origem"] == "OFX"
      ]
      pendentes_ofx_boletos = [
          x for x in boletos_nao_conc if x["origem"] == "OFX"
      ]
      pendentes_ofx_outros = [x for x in outros_nao_conc if x["origem"] == "OFX"]

      total_pendentes_ofx = (
          len(pendentes_ofx_cartoes)
          + len(pendentes_ofx_boletos)
          + len(pendentes_ofx_outros)
      )

      self.log("\n" + "=" * 45)
      self.log(f"      RESULTADO FINAL - {nome_banco.upper()}")
      self.log("=" * 45)
      self.log(f"Total Conciliados (Final): {total_conciliados_final}")
      self.log(f"  - Cartões: {len(cartoes_conc)}")
      self.log(f"  - Boletos: {len(boletos_conc)}")
      self.log(f"  - Outros:  {len(outros_conc)}")
      self.log(f"Total Pendentes do OFX: {total_pendentes_ofx}")
      self.log(f"  - Cartões Pendentes: {len(pendentes_ofx_cartoes)}")
      self.log(f"  - Boletos Pendentes: {len(pendentes_ofx_boletos)}")
      self.log(f"  - Outros Pendentes:  {len(pendentes_ofx_outros)}")
      self.log("-" * 45)

      # Exibição dos saldos para comparação
      val_saldo_ofx = saldo_banco if saldo_banco is not None else Decimal("0.00")
      val_saldo_sis = (
          total_sistema if total_sistema is not None else Decimal("0.00")
      )

      self.log(f"Saldo Final do Extrato (OFX): R$ {val_saldo_ofx:,.2f}")
      self.log(f"Saldo Final do Sistema (FEXTRATO): R$ {val_saldo_sis:,.2f}")
      self.log("=" * 45)

      # Impressão de pendências restritas ao OFX
      if total_pendentes_ofx > 0:
        self.log(
            "\n--- ITENS PENDENTES DO OFX (NÃO ENCONTRADOS NO SISTEMA) ---"
        )
        todas_pendencias_ofx = [
            ("CARTÕES", pendentes_ofx_cartoes),
            ("BOLETOS", pendentes_ofx_boletos),
            ("OUTROS", pendentes_ofx_outros),
        ]
        for nome_bloco, lista_bloco in todas_pendencias_ofx:
          if lista_bloco:
            self.log(f"\n[BLOCO: {nome_bloco}]")
            for item in lista_bloco:
              reg = item["item"]
              data_formatada = (
                  reg["data"].strftime("%d/%m/%Y")
                  if hasattr(reg["data"], "strftime")
                  else reg["data"]
              )
              self.log(
                  f"  [OFX] Data: {data_formatada} | Valor: R$"
                  f" {reg['valor']:,.2f} | Histórico: {reg['historico']}"
              )
        self.log("-" * 45)

      # Validação do status de conciliação e saldos
      saldos_batem = abs(val_saldo_ofx - val_saldo_sis) < Decimal("0.01")

      self.log("\n")
      if total_pendentes_ofx == 0 and saldos_batem:
        self.log("★" * 45)
        self.log("        BANCO CONCILIADO         ")
        self.log("★" * 45)
      else:
        self.log("✖" * 45)
        self.log("        BANCO NÃO CONCILIADO       ")
        self.log("✖" * 45)

      self.log("\nProcesso concluído com sucesso!")

    except Exception as e:
      sys.stdout = sys.__stdout__
      self.log(f"\n[ERRO CRÍTICO] Ocorreu um erro durante a execução: {e}")


if __name__ == "__main__":
  app = AppConciliacao()
  app.mainloop()