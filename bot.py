#!/usr/bin/env python3
"""
Bot Syntek Gift Cards v5.0 - WEBHOOK MODE
- Usa Flask + Webhook (mais confiável no Railway)
- Integração Oasyfy REAL
- Fluxo de pagamento PIX antes de entregar gift card
- Sem link de grupo estranho
- Botões /START e SUPORTE após compra
"""

import os
import json
import time
import random
import string
import sqlite3
import requests
import threading
import uuid
import logging
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8684385675:AAEWxBEjfOY5sMtOUoWtelwM-SpxclNqeOY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6462638999"))
OASYFY_PUBLIC_KEY = os.environ.get("OASYFY_PUBLIC_KEY", "lucasandre16112000_mepr35cra5buz30k")
OASYFY_SECRET_KEY = os.environ.get("OASYFY_SECRET_KEY", "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze")
OASYFY_BASE_URL = "https://app.oasyfy.com/api/v1"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================================
# GIFT CARDS
# ============================================================
GIFT_CARDS = {
    "shopee_1000": {"nome": "🎁 SHOPEE 1000", "valor": 299.90, "prefixo": "SH1K"},
    "shopee_500":  {"nome": "🎁 SHOPEE 500",  "valor": 249.90, "prefixo": "SH5C"},
    "shopee_300":  {"nome": "🎁 SHOPEE 300",  "valor": 99.90,  "prefixo": "SH3C"},
    "ifood_1000":  {"nome": "🍔 IFOOD 1000",  "valor": 279.90, "prefixo": "IF1K"},
    "ifood_500":   {"nome": "🍔 IFOOD 500",   "valor": 229.90, "prefixo": "IF5C"},
    "ifood_300":   {"nome": "🍔 IFOOD 300",   "valor": 89.90,  "prefixo": "IF3C"},
    "steam_300":   {"nome": "🎮 STEAM 300",   "valor": 89.00,  "prefixo": "STM"},
    "gplay_300":   {"nome": "🎮 GOOGLE PLAY 300", "valor": 89.00, "prefixo": "GPY"},
}

# ============================================================
# BANCO DE DADOS
# ============================================================
DB_PATH = "/tmp/syntek_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            transaction_id TEXT NOT NULL,
            identifier TEXT NOT NULL,
            card_key TEXT NOT NULL,
            valor REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            codigo_gift TEXT,
            criado_em INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ Banco de dados inicializado")

def salvar_transacao(chat_id, transaction_id, identifier, card_key, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO transacoes (chat_id, transaction_id, identifier, card_key, valor, status, criado_em)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
    """, (chat_id, transaction_id, identifier, card_key, valor, int(time.time())))
    conn.commit()
    conn.close()

def buscar_pendentes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, chat_id, transaction_id, card_key
        FROM transacoes
        WHERE status = 'PENDING' AND criado_em > ?
    """, (int(time.time()) - 3600,))
    rows = c.fetchall()
    conn.close()
    return rows

def atualizar_status(transaction_id, status, codigo=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE transacoes SET status = ?, codigo_gift = ? WHERE transaction_id = ?
    """, (status, codigo, transaction_id))
    conn.commit()
    conn.close()

def buscar_card_key(transaction_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT card_key FROM transacoes WHERE transaction_id = ?", (transaction_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# ============================================================
# FUNÇÕES TELEGRAM
# ============================================================
def enviar_mensagem(chat_id, texto, teclado=None, parse_mode="Markdown"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": parse_mode
    }
    if teclado:
        payload["reply_markup"] = json.dumps(teclado)
    try:
        r = requests.post(url, json=payload, timeout=15)
        result = r.json()
        if not result.get("ok"):
            logger.error(f"Erro Telegram sendMessage: {result}")
        return result
    except Exception as e:
        logger.error(f"Exceção ao enviar mensagem: {e}")
        return None

def responder_callback(callback_query_id, texto=""):
    url = f"{TELEGRAM_API}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_query_id, "text": texto}, timeout=10)
    except Exception as e:
        logger.error(f"Erro ao responder callback: {e}")

# ============================================================
# FUNÇÕES OASYFY
# ============================================================
def criar_cobranca_pix(chat_id, card_key, valor, nome_card):
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    identifier = f"syntek_{chat_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    payload = {
        "identifier": identifier,
        "amount": valor,
        "client": {
            "name": f"Cliente {chat_id}",
            "email": f"cliente{chat_id}@syntek.bot",
            "phone": "11999999999",
            "document": "529.982.247-25"
        },
        "products": [
            {
                "id": card_key,
                "name": nome_card,
                "quantity": 1,
                "price": valor
            }
        ]
    }
    try:
        r = requests.post(
            f"{OASYFY_BASE_URL}/gateway/pix/receive",
            headers=headers,
            json=payload,
            timeout=20
        )
        logger.info(f"Oasyfy PIX: {r.status_code} - {r.text[:400]}")
        if r.status_code in [200, 201]:
            data = r.json()
            pix_data = data.get("pix", {})
            return {
                "transaction_id": data.get("transactionId") or data.get("id"),
                "identifier": identifier,
                "pix_code": pix_data.get("code") or pix_data.get("qrCode") or pix_data.get("copyPaste"),
                "pix_url": pix_data.get("url"),
                "status": data.get("status")
            }
        else:
            logger.error(f"Erro Oasyfy {r.status_code}: {r.text}")
            return None
    except Exception as e:
        logger.error(f"Exceção Oasyfy: {e}")
        return None

def verificar_pagamento(transaction_id):
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY
    }
    try:
        r = requests.get(
            f"{OASYFY_BASE_URL}/transactions/{transaction_id}",
            headers=headers,
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("status")
        return None
    except Exception as e:
        logger.error(f"Erro verificar pagamento: {e}")
        return None

# ============================================================
# GERAÇÃO DE CÓDIGOS
# ============================================================
def gerar_codigo(prefixo):
    p1 = ''.join(random.choices(string.digits, k=4))
    p2 = ''.join(random.choices(string.digits, k=4))
    p3 = ''.join(random.choices(string.digits, k=4))
    return f"{prefixo}-{p1}-{p2}-{p3}"

# ============================================================
# TECLADOS
# ============================================================
def teclado_menu():
    botoes = []
    for key, card in GIFT_CARDS.items():
        botoes.append([{"text": f"{card['nome']} - R$ {card['valor']:.2f}", "callback_data": f"comprar_{key}"}])
    botoes.append([{"text": "📲 SUPORTE", "callback_data": "suporte"}])
    return {"inline_keyboard": botoes}

def teclado_pos_compra():
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 /START - Voltar ao Menu", "callback_data": "start"},
                {"text": "📲 SUPORTE", "callback_data": "suporte"}
            ]
        ]
    }

def teclado_aguardando(transaction_id):
    return {
        "inline_keyboard": [
            [{"text": "✅ Já paguei - Verificar", "callback_data": f"verificar_{transaction_id}"}],
            [{"text": "❌ Cancelar", "callback_data": "cancelar"}],
            [{"text": "📲 SUPORTE", "callback_data": "suporte"}]
        ]
    }

# ============================================================
# HANDLERS
# ============================================================
def handle_start(chat_id, nome=""):
    texto = (
        f"💰 *Bem-vindo ao Syntek Gift Cards!*\n\n"
        f"Olá {nome}! 👋\n\n"
        f"🎁 *CÓDIGO DO GIFT CARD*\n"
        f"✅ Basicamente é só adicionar e usar o saldo.\n\n"
        f"⚠️ *PARA OUTROS GIFT CARDS CONTATE O SUPORTE.*\n\n"
        f"Escolha seu Gift Card abaixo:"
    )
    enviar_mensagem(chat_id, texto, teclado=teclado_menu())
    logger.info(f"✅ /start → chat_id={chat_id}")

def handle_comprar(chat_id, card_key, cq_id):
    responder_callback(cq_id, "⏳ Gerando cobrança PIX...")
    if card_key not in GIFT_CARDS:
        enviar_mensagem(chat_id, "❌ Gift Card não encontrado.")
        return
    card = GIFT_CARDS[card_key]
    resultado = criar_cobranca_pix(chat_id, card_key, card["valor"], card["nome"])
    if not resultado or not resultado.get("transaction_id"):
        enviar_mensagem(
            chat_id,
            "❌ *Erro ao gerar cobrança PIX*\n\nTente novamente ou contate o suporte.\n📲 @SyntekOficial",
            teclado=teclado_pos_compra()
        )
        return
    transaction_id = resultado["transaction_id"]
    pix_code = resultado.get("pix_code", "Código não disponível")
    salvar_transacao(chat_id, transaction_id, resultado["identifier"], card_key, card["valor"])
    texto = (
        f"💳 *Pagamento via PIX*\n\n"
        f"🎁 *Produto:* {card['nome']}\n"
        f"💰 *Valor:* R$ {card['valor']:.2f}\n\n"
        f"📋 *Chave PIX (Copia e Cola):*\n"
        f"`{pix_code}`\n\n"
        f"⏰ *Prazo:* 30 minutos\n\n"
        f"✅ Após pagar, clique em *'Já paguei - Verificar'*"
    )
    enviar_mensagem(chat_id, texto, teclado=teclado_aguardando(transaction_id))
    logger.info(f"✅ PIX gerado: transaction_id={transaction_id}")

def handle_verificar(chat_id, transaction_id, cq_id):
    responder_callback(cq_id, "🔍 Verificando...")
    status = verificar_pagamento(transaction_id)
    logger.info(f"Status pagamento {transaction_id}: {status}")
    if status == "OK":
        card_key = buscar_card_key(transaction_id)
        card = GIFT_CARDS.get(card_key, {})
        codigo = gerar_codigo(card.get("prefixo", "GC"))
        atualizar_status(transaction_id, "PAID", codigo)
        enviar_mensagem(
            chat_id,
            f"✅ *PAGAMENTO APROVADO!*\n\n"
            f"🎁 *Gift Card:* {card.get('nome','')}\n\n"
            f"🔑 *Código:*\n`{codigo}`\n\n"
            f"✅ Adicione e use o saldo!\n⚠️ Para outros Gift Cards, contate o suporte.",
            teclado=teclado_pos_compra()
        )
    elif status == "PENDING":
        enviar_mensagem(chat_id, "⏳ *Pagamento ainda não confirmado*\n\nAguarde e tente novamente.", teclado=teclado_aguardando(transaction_id))
    else:
        enviar_mensagem(chat_id, f"❌ *Pagamento não encontrado*\n\nStatus: {status}\n\nContate o suporte.", teclado=teclado_pos_compra())

def handle_suporte(chat_id, cq_id):
    responder_callback(cq_id)
    enviar_mensagem(chat_id, "📲 *SUPORTE SYNTEK*\n\n👤 @SyntekOficial\n\nHorário: 24/7")

def handle_cancelar(chat_id, cq_id):
    responder_callback(cq_id, "❌ Cancelado")
    enviar_mensagem(chat_id, "❌ Pedido cancelado.\n\nVolte quando quiser!", teclado=teclado_menu())

# ============================================================
# VERIFICADOR AUTOMÁTICO
# ============================================================
def verificador_automatico():
    while True:
        try:
            for row in buscar_pendentes():
                _, chat_id, transaction_id, card_key = row
                status = verificar_pagamento(transaction_id)
                if status == "OK":
                    card = GIFT_CARDS.get(card_key, {})
                    codigo = gerar_codigo(card.get("prefixo", "GC"))
                    atualizar_status(transaction_id, "PAID", codigo)
                    enviar_mensagem(
                        chat_id,
                        f"✅ *PAGAMENTO APROVADO!*\n\n"
                        f"🎁 *Gift Card:* {card.get('nome','')}\n\n"
                        f"🔑 *Código:*\n`{codigo}`\n\n"
                        f"✅ Adicione e use o saldo!",
                        teclado=teclado_pos_compra()
                    )
                    logger.info(f"✅ Auto-entrega: chat_id={chat_id}")
                elif status in ["FAILED", "CANCELED"]:
                    atualizar_status(transaction_id, status)
        except Exception as e:
            logger.error(f"Erro verificador: {e}")
        time.sleep(30)

# ============================================================
# WEBHOOK FLASK
# ============================================================
@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        logger.info(f"📨 Update recebido: {json.dumps(update)[:200]}")
        processar_update(update)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return jsonify({"ok": False}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Syntek Gift Cards v5.0"})

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "running", "version": "5.0"})

def processar_update(update):
    try:
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            texto = msg.get("text", "")
            nome = msg.get("from", {}).get("first_name", "")
            logger.info(f"📨 Mensagem: chat_id={chat_id}, texto='{texto}'")
            if texto in ["/start", "/Start", "start"]:
                handle_start(chat_id, nome)
            elif texto == "/suporte":
                enviar_mensagem(chat_id, "📲 *SUPORTE SYNTEK*\n\n👤 @SyntekOficial")
        elif "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            data = cq.get("data", "")
            cq_id = cq["id"]
            nome = cq.get("from", {}).get("first_name", "")
            logger.info(f"🔘 Callback: chat_id={chat_id}, data='{data}'")
            if data == "start":
                responder_callback(cq_id)
                handle_start(chat_id, nome)
            elif data.startswith("comprar_"):
                handle_comprar(chat_id, data.replace("comprar_", ""), cq_id)
            elif data.startswith("verificar_"):
                handle_verificar(chat_id, data.replace("verificar_", ""), cq_id)
            elif data == "suporte":
                handle_suporte(chat_id, cq_id)
            elif data == "cancelar":
                handle_cancelar(chat_id, cq_id)
    except Exception as e:
        logger.error(f"Erro processar_update: {e}", exc_info=True)

# ============================================================
# CONFIGURAR WEBHOOK
# ============================================================
def configurar_webhook():
    if not WEBHOOK_URL:
        logger.warning("⚠️ WEBHOOK_URL não configurada! Usando polling como fallback...")
        return False
    url = f"{TELEGRAM_API}/setWebhook"
    webhook_endpoint = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
    try:
        r = requests.post(url, json={"url": webhook_endpoint}, timeout=15)
        result = r.json()
        if result.get("ok"):
            logger.info(f"✅ Webhook configurado: {webhook_endpoint}")
            return True
        else:
            logger.error(f"❌ Erro ao configurar webhook: {result}")
            return False
    except Exception as e:
        logger.error(f"Exceção ao configurar webhook: {e}")
        return False

# ============================================================
# POLLING FALLBACK (caso não tenha WEBHOOK_URL)
# ============================================================
def polling_loop():
    logger.info("🔄 Iniciando polling mode...")
    requests.get(f"{TELEGRAM_API}/deleteWebhook", timeout=10)
    offset = 0
    while True:
        try:
            r = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": offset, "timeout": 10, "limit": 10},
                timeout=20
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        processar_update(update)
            elif r.status_code == 409:
                logger.warning("⚠️ Conflito de instância. Aguardando...")
                time.sleep(10)
            else:
                time.sleep(3)
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            logger.error(f"Erro polling: {e}")
            time.sleep(3)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    init_db()
    logger.info("✅ Bot Syntek Gift Cards v5.0 iniciado!")
    logger.info(f"✅ Token: {BOT_TOKEN[:20]}...")
    logger.info(f"✅ Oasyfy: {OASYFY_PUBLIC_KEY[:20]}...")
    logger.info(f"✅ PORT: {PORT}")
    logger.info(f"✅ WEBHOOK_URL: {WEBHOOK_URL or 'NÃO CONFIGURADA'}")

    # Iniciar verificador automático
    t = threading.Thread(target=verificador_automatico, daemon=True)
    t.start()
    logger.info("✅ Verificador automático iniciado (30s)")

    # Configurar webhook ou usar polling
    webhook_ok = configurar_webhook()
    
    if webhook_ok:
        logger.info(f"🌐 Iniciando servidor Flask na porta {PORT}...")
        app.run(host="0.0.0.0", port=PORT, debug=False)
    else:
        # Polling em thread separada + Flask para health check
        logger.info("🔄 Modo polling ativo...")
        poll_thread = threading.Thread(target=polling_loop, daemon=True)
        poll_thread.start()
        # Flask para health check do Railway
        app.run(host="0.0.0.0", port=PORT, debug=False)
