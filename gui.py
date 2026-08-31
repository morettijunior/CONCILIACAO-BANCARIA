from datetime import datetime
import sys
import tkinter as tk
import customtkinter as ctk
from service.bd import consultar_extrato, saldo_sistema
from service.conciliacao import comparar_listas, inserir_itens
from service.ofx import ler_ofx, saldo_final

# Configuração inicial do tema da janela
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class AppConciliacao(ctk.CTk):

  def __init__(self):
    super().__init__()

    self.title("Sistema de Conciliação Bancária")
    self.geometry("750x680")
    self.resizable(False, False)

    self.caminho_extrato = r"C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO_BANCARIA\bd_firebird\extrato.ofx"

    self.label_titulo = ctk.CTkLabel(
        self, text="Conciliação Bancária TGA", font=("Arial", 22, "bold")
    )
    self.label_titulo.pack(pady=20)

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
        self, font=("Consolas", 12), width=700, height=330
    )
    self.caixa_texto.pack(pady=10, padx=20)
    self.caixa_texto.insert(
        "0.0",
        "Sistema pronto. Selecione o banco acima e clique em 'Executar"
        " Conciliação'.\n",
    )

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