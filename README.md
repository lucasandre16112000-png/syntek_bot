# 🤖 BOT SYNTEK GIFT CARDS

Bot de vendas de Gift Cards no Telegram com pagamento via Pix automático.

## 📋 Funcionalidades

✅ Venda de Gift Cards (Shopee, iFood, Steam, Google Play)  
✅ Pagamento via Pix automático (Oasyfy)  
✅ Entrega automática de códigos após pagamento  
✅ Geração infinita de códigos (formato válido)  
✅ Mensagem de promoção a cada 2 horas  
✅ Sistema de suporte integrado  
✅ Banco de dados SQLite para rastrear transações  

## 🚀 Instalação

### Pré-requisitos
- Python 3.8+
- pip (gerenciador de pacotes Python)

### Passo 1: Instalar dependências

```bash
pip install -r requirements.txt
```

### Passo 2: Configurar credenciais

Abra o arquivo `config.py` e verifique se as credenciais estão corretas:

```python
BOT_TOKEN = "seu_token_aqui"
ADMIN_ID = seu_id_aqui
OASYFY_CLIENT_ID = "seu_client_id"
OASYFY_CLIENT_SECRET = "seu_client_secret"
```

### Passo 3: Executar o bot

```bash
python main.py
```

## 📱 Como usar (Usuário Final)

1. Abra o Telegram e procure por `@SyntekGiftCardsBot`
2. Clique em "Iniciar" ou envie `/start`
3. Escolha um Gift Card
4. Escaneie o QR Code Pix ou copie a chave
5. Após pagar, receba o código automaticamente

## 💰 Gift Cards Disponíveis

### SHOPEE
- 🎁 SHOPEE 1000 - R$ 299,90
- 🎁 SHOPEE 500 - R$ 249,90
- 🎁 SHOPEE 300 - R$ 99,90

### IFOOD
- 🍔 IFOOD 1000 - R$ 279,90
- 🍔 IFOOD 500 - R$ 229,90
- 🍔 IFOOD 300 - R$ 89,90

### STEAM
- 🎮 STEAM 300 - R$ 89,00

### GOOGLE PLAY
- 🎮 GOOGLE PLAY 300 - R$ 89,00

## 🔧 Estrutura do Projeto

```
syntek_bot/
├── main.py              # Arquivo principal do bot
├── config.py            # Configurações
├── requirements.txt     # Dependências
├── README.md            # Este arquivo
└── syntek_bot.db        # Banco de dados (criado automaticamente)
```

## 📊 Banco de Dados

O bot cria automaticamente um banco de dados SQLite com as seguintes tabelas:

- **users**: Armazena informações dos usuários
- **transactions**: Registra todas as transações
- **pix_payments**: Armazena dados de pagamentos Pix

## 🔐 Segurança

- ⚠️ Nunca compartilhe seu `BOT_TOKEN`
- ⚠️ Mantenha suas credenciais Oasyfy seguras
- ⚠️ Use variáveis de ambiente em produção

## 📞 Suporte

Para dúvidas ou problemas, entre em contato:
- Telegram: @SyntekOficial
- Email: lucasandre16112000@gmail.com

## 📝 Licença

Todos os direitos reservados © 2026 Syntek

---

**Desenvolvido com ❤️ por Manus**
