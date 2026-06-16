#!/usr/bin/env python3
"""
Bot Syntek Gift Cards - VERSÃO DEFINITIVA
Webhook Flask + Oasyfy PIX + Entrega após pagamento
"""

import os
import json
import time
import random
import string
import sqlite3
import threading
import requests
from flask import Flask, request, jsonify

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8684385675:AAEWxBEjfOY5sMtOUoWtelwM-SpxclNqeOY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6462638999"))
OASYFY_PUBLIC_KEY = os.environ.get("OASYFY_CLIENT_ID", os.environ.get("OASYFY_PUBLIC_KEY", "lucasandre16112000_mepr35cra5buz30k"))
OASYFY_SECRET_KEY = os.environ.get("OASYFY_CLIENT_SECRET", os.environ.get("OASYFY_SECRET_KEY", "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze"))
_webhook_raw = os.environ.get("WEBHOOK_URL", "https://web-production-45773.up.railway.app")
# Remover /webhook do final se já estiver presente (evitar duplicação)
if _webhook_raw.endswith("/webhook"):
    WEBHOOK_URL = _webhook_raw[:-8]  # remove os 8 chars de "/webhook"
else:
    WEBHOOK_URL = _webhook_raw.rstrip("/")
PORT = int(os.environ.get("PORT", 8080))
SUPORTE = "@SyntekOficial"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================================
# GIFT CARDS
# ============================================================
GIFT_CARDS = {
    "shopee_1000": {"nome": "🎁 SHOPEE 1000", "preco": 299.90, "prefixo": "SH10"},
    "shopee_500":  {"nome": "🎁 SHOPEE 500",  "preco": 249.90, "prefixo": "SH5"},
    "shopee_300":  {"nome": "🎁 SHOPEE 300",  "preco": 99.90,  "prefixo": "SH3"},
    "ifood_1000":  {"nome": "🍔 IFOOD 1000",  "preco": 279.90, "prefixo": "IF10"},
    "ifood_500":   {"nome": "🍔 IFOOD 500",   "preco": 229.90, "prefixo": "IF5"},
    "ifood_300":   {"nome": "🍔 IFOOD 300",   "preco": 89.90,  "prefixo": "IF3"},
    "steam_300":   {"nome": "🎮 STEAM 300",   "preco": 89.00,  "prefixo": "ST3"},
    "gplay_300":   {"nome": "🎮 GOOGLE PLAY 300", "preco": 89.00, "prefixo": "GP3"},
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
            id TEXT PRIMARY KEY,
            chat_id INTEGER,
            card_key TEXT,
            valor REAL,
            status TEXT DEFAULT 'pendente',
            codigo_gift TEXT,
            criado_em REAL
        )
    """)
    conn.commit()
    conn.close()

def salvar_transacao(tx_id, chat_id, card_key, valor):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO transacoes (id, chat_id, card_key, valor, status, criado_em) VALUES (?,?,?,?,?,?)",
              (tx_id, chat_id, card_key, valor, "pendente", time.time()))
    conn.commit()
    conn.close()

def buscar_transacao(tx_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM transacoes WHERE id=?", (tx_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "chat_id": row[1], "card_key": row[2], "valor": row[3], "status": row[4], "codigo_gift": row[5]}
    return None

def atualizar_status(tx_id, status, codigo=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if codigo:
        c.execute("UPDATE transacoes SET status=?, codigo_gift=? WHERE id=?", (status, codigo, tx_id))
    else:
        c.execute("UPDATE transacoes SET status=? WHERE id=?", (status, tx_id))
    conn.commit()
    conn.close()

def buscar_pendentes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, card_key, valor FROM transacoes WHERE status='pendente' AND criado_em > ?",
              (time.time() - 3600,))
    rows = c.fetchall()
    conn.close()
    return rows

# ============================================================
# TELEGRAM API
# ============================================================
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[ERRO] send_message: {e}")
        return None

def send_photo(chat_id, photo_url, caption=None, reply_markup=None):
    payload = {"chat_id": chat_id, "photo": photo_url, "parse_mode": "HTML"}
    if caption:
        payload["caption"] = caption
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[ERRO] send_photo: {e}")
        return None

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery",
                      json={"callback_query_id": callback_id, "text": text}, timeout=5)
    except:
        pass

# ============================================================
# OASYFY - GERAR COBRANÇA PIX
# ============================================================
def gerar_cobranca_pix(valor, descricao, tx_id):
    """Gera cobrança PIX via Oasyfy"""
    url = "https://app.oasyfy.com/api/v1/gateway/pix/receive"
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "amount": int(valor * 100),  # em centavos
        "description": descricao,
        "externalId": tx_id,
        "payer": {
            "name": "Cliente Syntek",
            "document": "12345678909",  # CPF fictício válido
            "email": "cliente@syntek.com"
        }
    }
    try:
        print(f"[OASYFY] Gerando cobrança: R${valor:.2f} | ID: {tx_id}")
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"[OASYFY] Status: {r.status_code} | Resposta: {r.text[:200]}")
        if r.status_code in [200, 201]:
            data = r.json()
            return data
        else:
            print(f"[OASYFY] ERRO: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"[OASYFY] Exceção: {e}")
        return None

def verificar_pagamento_oasyfy(tx_id):
    """Verifica se o pagamento foi confirmado"""
    url = f"https://app.oasyfy.com/api/v1/gateway/pix/receive/{tx_id}"
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "").upper()
            print(f"[OASYFY] Status pagamento {tx_id}: {status}")
            return status in ["PAID", "APPROVED", "COMPLETED", "CONFIRMED"]
        return False
    except Exception as e:
        print(f"[OASYFY] Erro verificação: {e}")
        return False

# ============================================================
# GERADOR DE CÓDIGO GIFT CARD
# ============================================================
def gerar_codigo(prefixo):
    nums = ''.join(random.choices(string.digits, k=12))
    return f"{prefixo}-{nums[:4]}-{nums[4:8]}-{nums[8:12]}"

# ============================================================
# HANDLERS DO BOT
# ============================================================
def handle_start(chat_id, user_name):
    print(f"[BOT] /start de {user_name} ({chat_id})")
    texto = (
        f"👋 Olá, <b>{user_name}</b>! Bem-vindo à <b>Syntek Gift Cards</b>! 🏆\n\n"
        "🎁 Escolha um Gift Card abaixo:\n"
        "💳 Pagamento via <b>PIX</b> — entrega automática após confirmação!"
    )
    teclado = {
        "inline_keyboard": [
            [{"text": "🎁 SHOPEE 1000 - R$ 299,90", "callback_data": "comprar_shopee_1000"}],
            [{"text": "🎁 SHOPEE 500 - R$ 249,90",  "callback_data": "comprar_shopee_500"}],
            [{"text": "🎁 SHOPEE 300 - R$ 99,90",   "callback_data": "comprar_shopee_300"}],
            [{"text": "🍔 IFOOD 1000 - R$ 279,90",  "callback_data": "comprar_ifood_1000"}],
            [{"text": "🍔 IFOOD 500 - R$ 229,90",   "callback_data": "comprar_ifood_500"}],
            [{"text": "🍔 IFOOD 300 - R$ 89,90",    "callback_data": "comprar_ifood_300"}],
            [{"text": "🎮 STEAM 300 - R$ 89,00",    "callback_data": "comprar_steam_300"}],
            [{"text": "🎮 GOOGLE PLAY 300 - R$ 89,00", "callback_data": "comprar_gplay_300"}],
            [{"text": "📲 SUPORTE", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
        ]
    }
    send_message(chat_id, texto, reply_markup=teclado)

def handle_comprar(chat_id, card_key, callback_id):
    answer_callback(callback_id, "⏳ Gerando cobrança PIX...")
    
    if card_key not in GIFT_CARDS:
        send_message(chat_id, "❌ Gift Card inválido.")
        return
    
    card = GIFT_CARDS[card_key]
    tx_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    
    print(f"[BOT] Compra: {card['nome']} R${card['preco']} | TX: {tx_id} | Chat: {chat_id}")
    
    # Salvar transação
    salvar_transacao(tx_id, chat_id, card_key, card["preco"])
    
    # Gerar cobrança Oasyfy
    cobranca = gerar_cobranca_pix(card["preco"], f"Gift Card {card['nome']}", tx_id)
    
    if cobranca:
        # Extrair dados do PIX
        pix_code = (cobranca.get("pixCode") or 
                    cobranca.get("qrCode") or 
                    cobranca.get("pix", {}).get("code") or
                    cobranca.get("data", {}).get("pixCode") or "")
        qr_url = (cobranca.get("qrCodeUrl") or 
                  cobranca.get("qrCodeImage") or
                  cobranca.get("pix", {}).get("qrCodeUrl") or
                  cobranca.get("data", {}).get("qrCodeUrl") or "")
        
        print(f"[OASYFY] PIX Code: {pix_code[:50] if pix_code else 'N/A'}")
        print(f"[OASYFY] QR URL: {qr_url[:80] if qr_url else 'N/A'}")
        
        texto = (
            f"💳 <b>PAGAMENTO PIX</b>\n\n"
            f"🎁 Produto: <b>{card['nome']}</b>\n"
            f"💰 Valor: <b>R$ {card['preco']:.2f}</b>\n\n"
            f"📋 <b>Chave PIX (Copia e Cola):</b>\n"
            f"<code>{pix_code if pix_code else 'Gerando...'}</code>\n\n"
            f"⏳ Após o pagamento, o código será entregue automaticamente!\n"
            f"🔄 ID: <code>{tx_id}</code>"
        )
        
        teclado = {
            "inline_keyboard": [
                [{"text": "✅ Já paguei! Verificar", "callback_data": f"verificar_{tx_id}"}],
                [{"text": "🔄 Voltar ao Menu", "callback_data": "menu"}],
                [{"text": "📲 Suporte", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
            ]
        }
        
        if qr_url:
            send_photo(chat_id, qr_url, caption=texto, reply_markup=teclado)
        else:
            send_message(chat_id, texto, reply_markup=teclado)
    else:
        # Fallback: mostrar mensagem de erro com suporte
        texto = (
            f"⚠️ <b>Erro ao gerar PIX</b>\n\n"
            f"Não foi possível gerar a cobrança agora.\n"
            f"Entre em contato com o suporte: {SUPORTE}"
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "🔄 Tentar Novamente", "callback_data": f"comprar_{card_key}"}],
                [{"text": "📲 Suporte", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
            ]
        }
        send_message(chat_id, texto, reply_markup=teclado)

def handle_verificar(chat_id, tx_id, callback_id):
    answer_callback(callback_id, "🔍 Verificando pagamento...")
    
    tx = buscar_transacao(tx_id)
    if not tx:
        send_message(chat_id, "❌ Transação não encontrada.")
        return
    
    if tx["status"] == "pago":
        send_message(chat_id, f"✅ Pagamento já confirmado!\n\nSeu código: <code>{tx['codigo_gift']}</code>")
        return
    
    # Verificar na Oasyfy
    pago = verificar_pagamento_oasyfy(tx_id)
    
    if pago:
        card = GIFT_CARDS.get(tx["card_key"], {})
        codigo = gerar_codigo(card.get("prefixo", "GC"))
        atualizar_status(tx_id, "pago", codigo)
        
        texto = (
            f"✅ <b>PAGAMENTO CONFIRMADO!</b>\n\n"
            f"🎁 Produto: <b>{card.get('nome', 'Gift Card')}</b>\n\n"
            f"🔑 <b>Seu Código:</b>\n"
            f"<code>{codigo}</code>\n\n"
            f"✅ Basicamente é só adicionar e usar o saldo!\n"
            f"⚠️ Para outros Gift Cards, contate o suporte."
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "🔄 /START - Comprar mais", "callback_data": "menu"}],
                [{"text": "📲 Suporte", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
            ]
        }
        send_message(chat_id, texto, reply_markup=teclado)
    else:
        texto = (
            "⏳ <b>Pagamento ainda não confirmado</b>\n\n"
            "Aguarde alguns instantes e tente novamente.\n"
            "O pagamento PIX pode levar até 2 minutos para ser processado."
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "🔄 Verificar Novamente", "callback_data": f"verificar_{tx_id}"}],
                [{"text": "📲 Suporte", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
            ]
        }
        send_message(chat_id, texto, reply_markup=teclado)

# ============================================================
# VERIFICADOR AUTOMÁTICO DE PAGAMENTOS
# ============================================================
def verificar_pagamentos_loop():
    """Verifica pagamentos pendentes a cada 30 segundos"""
    while True:
        try:
            pendentes = buscar_pendentes()
            for tx_id, chat_id, card_key, valor in pendentes:
                pago = verificar_pagamento_oasyfy(tx_id)
                if pago:
                    card = GIFT_CARDS.get(card_key, {})
                    codigo = gerar_codigo(card.get("prefixo", "GC"))
                    atualizar_status(tx_id, "pago", codigo)
                    
                    texto = (
                        f"✅ <b>PAGAMENTO CONFIRMADO!</b>\n\n"
                        f"🎁 Produto: <b>{card.get('nome', 'Gift Card')}</b>\n\n"
                        f"🔑 <b>Seu Código:</b>\n"
                        f"<code>{codigo}</code>\n\n"
                        f"✅ Basicamente é só adicionar e usar o saldo!\n"
                        f"⚠️ Para outros Gift Cards, contate o suporte."
                    )
                    teclado = {
                        "inline_keyboard": [
                            [{"text": "🔄 /START - Comprar mais", "callback_data": "menu"}],
                            [{"text": "📲 Suporte", "url": f"https://t.me/{SUPORTE.replace('@','')}"}],
                        ]
                    }
                    send_message(chat_id, texto, reply_markup=teclado)
                    print(f"[AUTO] Pagamento confirmado e código entregue: {tx_id}")
        except Exception as e:
            print(f"[AUTO] Erro: {e}")
        time.sleep(30)

# ============================================================
# FLASK APP - WEBHOOK
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Syntek Gift Cards", "version": "definitiva"})

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        if not update:
            return jsonify({"ok": True})
        
        print(f"[WEBHOOK] Update recebido: {json.dumps(update)[:200]}")
        
        # Processar mensagem
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user = msg.get("from", {})
            user_name = user.get("first_name", "Cliente")
            text = msg.get("text", "")
            
            if text.startswith("/start"):
                handle_start(chat_id, user_name)
            elif text.startswith("/suporte"):
                send_message(chat_id, f"📲 Entre em contato com nosso suporte:\n{SUPORTE}")
        
        # Processar callback (botões)
        elif "callback_query" in update:
            cb = update["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            callback_id = cb["id"]
            data = cb.get("data", "")
            
            print(f"[WEBHOOK] Callback: {data} | Chat: {chat_id}")
            
            if data == "menu":
                user_name = cb.get("from", {}).get("first_name", "Cliente")
                handle_start(chat_id, user_name)
            elif data.startswith("comprar_"):
                card_key = data.replace("comprar_", "")
                handle_comprar(chat_id, card_key, callback_id)
            elif data.startswith("verificar_"):
                tx_id = data.replace("verificar_", "")
                handle_verificar(chat_id, tx_id, callback_id)
        
        return jsonify({"ok": True})
    
    except Exception as e:
        print(f"[WEBHOOK] ERRO: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": True})

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Bot Syntek Gift Cards - VERSÃO DEFINITIVA")
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🌐 Webhook: {WEBHOOK_URL}/webhook")
    print(f"💳 Oasyfy: {OASYFY_PUBLIC_KEY[:20]}...")
    print("=" * 50)
    
    # Inicializar banco de dados
    init_db()
    print("✅ Banco de dados inicializado")
    
    # Configurar webhook no Telegram
    try:
        r = requests.post(f"{TELEGRAM_API}/setWebhook",
                          json={"url": f"{WEBHOOK_URL}/webhook", "drop_pending_updates": True},
                          timeout=10)
        result = r.json()
        if result.get("ok"):
            print(f"✅ Webhook configurado: {WEBHOOK_URL}/webhook")
        else:
            print(f"⚠️ Webhook: {result.get('description')}")
    except Exception as e:
        print(f"⚠️ Erro ao configurar webhook: {e}")
    
    # Iniciar verificador automático de pagamentos em background
    t = threading.Thread(target=verificar_pagamentos_loop, daemon=True)
    t.start()
    print("✅ Verificador automático de pagamentos iniciado (30s)")
    
    print(f"🚀 Flask iniciando na porta {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
