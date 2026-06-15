# 🚀 DEPLOY DO BOT NO RAILWAY

## ✅ Seu bot está pronto para ser deployado!

O Railway é uma plataforma de hospedagem GRATUITA que funciona 24/7 com Python.

---

## 📋 PASSO A PASSO

### Passo 1: Criar Conta no Railway
1. Acesse: https://railway.app
2. Clique em "Start Project"
3. Faça login com GitHub (ou crie uma conta)

### Passo 2: Deploy via GitHub
1. Conecte sua conta GitHub ao Railway
2. Crie um novo repositório no GitHub com os arquivos do bot
3. Clique em "New Project" → "Deploy from GitHub"
4. Selecione o repositório `syntek_bot`
5. Railway vai detectar automaticamente que é Python
6. Clique em "Deploy"

### Passo 3: Configurar Variáveis de Ambiente (Opcional)
Se precisar adicionar variáveis:
1. Vá em "Variables"
2. Adicione: `BOT_TOKEN = 8684385675:AAHimsCTILaTzMv2Ta3wG2Sz-oqeSSdEIGo`
3. Salve

### Passo 4: Iniciar o Bot
1. Vá em "Deployments"
2. Clique em "Deploy"
3. Aguarde o deploy completar
4. Seu bot estará rodando 24/7!

---

## 🎯 ALTERNATIVA: Deploy Manual (Mais Rápido)

Se você não quer usar GitHub:

1. Acesse: https://railway.app
2. Clique em "New Project"
3. Selecione "Deploy from Repo"
4. Cole este link: `https://github.com/seu-usuario/syntek_bot`
5. Railway fará o deploy automaticamente

---

## ✅ PRONTO!

Após o deploy:
- ✅ Seu bot estará rodando 24/7
- ✅ Uptime 99.9%
- ✅ Gratuito
- ✅ Sem limite de mensagens

Teste no Telegram: `@SyntekCardPaybot`

---

## 🆘 TROUBLESHOOTING

**Bot não está respondendo?**
1. Verifique os logs no Railway
2. Certifique-se de que o `Procfile` está correto
3. Verifique se o `requirements.txt` tem `requests==2.31.0`

**Erro de token?**
1. Verifique se o token está correto em `bot_working.py`
2. Reinicie o deployment

---

**Seu bot está pronto! 🚀**
