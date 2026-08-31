from datetime import datetime
import sys
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from service.bd import (
    consultar_extrato,
    excluir_regra,
    inserir_regra,
    listar_regras,
    saldo_sistema,
)
from service.conciliacao import comparar_listas, inserir_itens
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

    # Frame de Formulário para Inclusão
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

    # Lista/Caixa de exibição numerada das regras atuais
    ctk.CTkLabel(
        self, text="Regras Ativas (com ID de Exclusão):", font=("Arial", 14, "bold")
    ).pack(anchor="w", padx=20, pady=(15, 5))

    self.lista_texto = ctk.CTkTextbox(
        self, font=("Consolas", 11), width=630, height=180
    )
    self.lista_texto.pack(padx=20, pady=5)

    # Frame para exclusão baseada no ID/Número da linha
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
    self.geometry("750x720")
    self.resizable(False, False)

    self.caminho_extrato = r"C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO_BANCARIA\bd_firebird\extrato.ofx"

    self.label_titulo = ctk.CTkLabel(
        self, text="Conciliação Bancária TGA", font=("Arial", 22, "bold")
    )
    self.label_titulo.pack(pady=15)

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
    self.btn_regras.pack(pady=5)

    self.frame_banco = ctk.CTkFrame(self)
    self.frame_banco.pack(pady=10, padx=20, fill="x")

    self.label_escolha = ctk.CTkLabel(
        self.frame_banco, text="Selecione o Banco:", font=("Arial", 14)
    )
    self.label_escolha.pack(side="left", padx=15, pady=15)

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
    self.btn_executar.pack(pady=15, padx=20, fill="x")

    self.caixa_texto = ctk.CTkTextbox(
        self, font=("Consolas", 12), width=700, height=310
    )
    self.caixa_texto.pack(pady=10, padx=20)
    self.caixa_texto.insert(
        "0.0",
        "Sistema pronto. Selecione o banco acima e clique em 'Executar"
        " Conciliação'.\n",
    )

  def abrir_tela_regras(self):
    JanelaGerenciarRegras(self)

  def log(self, mensagem):
    self.caixa_texto.insert("end", mensagem + "\n")
    self.caixa_texto.see("end")

  def rodar_conciliacao(self):
    banco_esperado = self.banco_var.get()
    nome_banco = "Sicredi" if banco_esperado == 748 else "Sicoob"

    self.caixa_texto.delete("0.0", "end")
    self.log(f"Processando conciliação para o {nome_banco} (Banco: {banco_esperado})...\n")
    self.update()

    try:
      lista_ofx = ler_ofx(banco_esperado, self.caminho_extrato)
      if not lista_ofx:
        self.log(
            "[AVISO] Nenhum lançamento encontrado no OFX ou falha na leitura."
        )
        return

      lista_bd = consultar_extrato(banco_esperado, self.caminho_extrato)
      saldo_banco = saldo_final(banco_esperado, self.caminho_extrato)

      conciliados, nao_conciliados = comparar_listas(lista_ofx, lista_bd)

      self.log(f"-> Total de registros no OFX: {len(lista_ofx)}")
      self.log(f"-> Total de registros no BD: {len(lista_bd)}")
      self.log(f"-> Já conciliados: {len(conciliados)}")
      self.log(f"-> Não conciliados (antes das regras): {len(nao_conciliados)}")

      if nao_conciliados:
        self.log("\nAplicando regras automáticas aos itens não conciliados...")

        class RedirecionadorPrint:

          def __init__(self, callback_log):
            self.callback_log = callback_log

          def write(self, texto):
            if texto.strip():
              self.callback_log(texto.strip())

          def flush(self):
            pass

        sys.stdout = RedirecionadorPrint(self.log)
        inserir_itens(banco_esperado, nao_conciliados, conciliados)
        sys.stdout = sys.__stdout__

      total_sistema = saldo_sistema(banco_esperado)

      self.log("\n" + "=" * 45)
      self.log(f"       RESULTADO FINAL - {nome_banco.upper()}")
      self.log("=" * 45)
      self.log(f"Total Conciliados (Final): {len(conciliados)}")
      self.log(f"Total Não Conciliados (Pendentes): {len(nao_conciliados)}")
      if saldo_banco is not None:
        self.log(f"Saldo Final do Extrato (OFX): R$ {saldo_banco:,.2f}")
      self.log(f"Saldo Final do Sistema (BD): R$ {total_sistema:,.2f}")
      self.log("=" * 45)

      if nao_conciliados:
        self.log("\n--- ITENS PENDENTES DE CONCILIAÇÃO MANUAL ---")
        for item in nao_conciliados:
          origem = item["origem"]
          reg = item["item"]
          data_formatada = (
              reg["data"].strftime("%d/%m/%Y")
              if hasattr(reg["data"], "strftime")
              else reg["data"]
          )
          self.log(
              f"[{origem}] Data: {data_formatada} | Valor: R$"
              f" {reg['valor']:,.2f} | Histórico: {reg['historico']}"
          )
        self.log("-" * 45)

      self.log("\nProcesso concluído com sucesso!")

    except Exception as e:
      sys.stdout = sys.__stdout__
      self.log(f"\n[ERRO CRÍTICO] Ocorreu um erro durante a execução: {e}")


if __name__ == "__main__":
  app = AppConciliacao()
  app.mainloop()