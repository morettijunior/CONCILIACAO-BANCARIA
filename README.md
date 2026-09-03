# Sistema de Conciliação Bancária OFX (Firebird)

Sistema automatizado desenvolvido em Python com interface gráfica (CustomTkinter) para a conciliação de arquivos de extrato bancário OFX contra o banco de dados Firebird do ERP.

## 🚀 Principais Funcionalidades

- **Processamento de Extratos OFX**: Leitura inteligente e cruzamento automático de lançamentos bancários.
- **Regras Automatizadas**:
  - Identificação de histórico por palavras-chave com mapeamento dinâmico para Centro de Custo e Cód. Fornecedor, gerando lançamentos automáticos nas tabelas próprias.
  - **Suporte a Transferências Internas**: Mapeamento direto na tabela utilizando caixas de origem e destino (`CODCAIXA_ORIGEM` e `CODCAIXA_DESTINO`).
- **Validação em Lote para Cartões (Débito e Crédito)**:
  - Agrupamento inteligente de lançamentos considerando o intervalo de datas do extrato.
  - Reconciliação líquida cruzando vendas de cartões, taxas e números de documentos.
  - Rotina de baixa automática para compensação de títulos no Caixa de Cartões.
- **Gestão de Boletos e Outros Lançamentos**: Cruzamento exato de liquidações de cobrança e conciliação 1 para 1.

---

## 🛠️ Tecnologias Utilizadas

- Python 3.x
- Firebird SQL (via conector `fdb`)
- CustomTkinter (Interface Gráfica moderna)
- Decimal (Precisão matemática financeira para valores monetários)

---

## ⚙️ Configuração do Ambiente

1. Certifique-se de ter o Python instalado junto com as dependências do projeto.
2. Configure o arquivo `config.json` na raiz do sistema apontando para o seu arquivo OFX e o caminho do banco de dados Firebird.

---

## ⚙️ Principais Desafios:
- Entender o funcionamento do ERP com o banco de dados.
- Validar a baixa automática de cartão de crédito quando o arquivo OFX não fornece dados suficientes para tal.
- Entender como o ERP incrementa automaticamente o número ID das tabelas.