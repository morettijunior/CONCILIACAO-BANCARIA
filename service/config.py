import json
import os

CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config.json"
)


def carregar_config():
  """Lê as configurações salvas ou retorna os padrões caso não existam."""
  padroes = {
      "caminho_ofx": r"C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO_BANCARIA\bd_firebird\extrato.ofx",
      "caminho_bd": r"C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb",
  }
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)
        return {**padroes, **dados}
    except Exception:
      return padroes
  return padroes
import json
import os

def obter_pasta_documentos_config():
    """Retorna e garante o caminho fixo na pasta Documentos do usuário: Documentos/ConciliacaoBancaria"""
    home_dir = os.path.expanduser("~")
    documentos_path = os.path.join(home_dir, "Documents")
    if not os.path.exists(documentos_path):
        documentos_path = os.path.join(home_dir, "Documentos") # fallback para pt-br

    pasta_base = os.path.join(documentos_path, "ConciliacaoBancaria")
    if not os.path.exists(pasta_base):
        os.makedirs(pasta_base, exist_ok=True)
        
    return pasta_base

# Arquivo de configuração centralizado na pasta Documentos/ConciliacaoBancaria
CONFIG_FILE = os.path.join(obter_pasta_documentos_config(), "config.json")


def carregar_config():
    """Lê as configurações salvas ou retorna os padrões caso não existam."""
    padroes = {
        "caminho_ofx": r"C:\Users\rondo\Dropbox\JUNIOR\PYTHON\PROJETOS\CONCILIACAO_BANCARIA\bd_firebird\extrato.ofx",
        "caminho_bd": r"C:\Users\rondo\Desktop\Phyton\BD FIREBIRD\tga.fdb",
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return {**padroes, **dados}
        except Exception:
            return padroes
    return padroes


def salvar_config(caminho_ofx, caminho_bd):
    """Salva os caminhos atuais no arquivo de configuração."""
    dados = {"caminho_ofx": caminho_ofx, "caminho_bd": caminho_bd}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERRO] Falha ao salvar configurações: {e}")

def salvar_config(caminho_ofx, caminho_bd):
  """Salva os caminhos atuais no arquivo de configuração."""
  dados = {"caminho_ofx": caminho_ofx, "caminho_bd": caminho_bd}
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(dados, f, indent=4, ensure_ascii=False)
  except Exception as e:
    print(f"[ERRO] Falha ao salvar configurações: {e}")