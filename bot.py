#!/usr/bin/env python3

"""
Bot Syntek Gift Cards - Versão 2.1 CORRIGIDA
Integração completa com Oasyfy para pagamento PIX
Sistema de rastreamento de transações
"""

import requests
import json
import time
import random
import string
import sqlite3
import os
from datetime import datetime, timedelta

# ==================== CONFIGURAÇÕES ====================

# Token lido de variável de ambiente (Railway) com fallback
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8684385675:AAEWxBEjfOY5sMtOUoWtelwM-SpxclNqeOY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6462638999"))
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Oasyfy API
OASYFY_CLIENT_ID = os.environ.get("OASYFY_CLIENT_ID", "lucasandre16112000_mepr35cra5buz30k")
OASYFY_CLIENT_SECRET = os.environ.get("OASYFY_CLIENT_SECRET", "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze")
OASYFY_API_URL = "https://api.oasyfy.com"

# Banco de dados
DB_FILE = "/tmp/transacoes.db"

# ==================== GIFT CARDS ====================

GIFT_CARDS = {
    "shopee_1000": {"name": "🎁 SHOPEE 1000", "price": "299.90", "code_prefix": "SHOP"},
    "shopee_500":  {"name": "🎁 SHOPEE 500",  "price": "249.90", "code_prefix": "SHOP"},
    "shopee_300":  {"name": "🎁 SHOPEE 300",  "price": "99.90",  "code_prefix": "SHOP"},
    "ifood_1000":  {"name": "🍔 IFOOD 1000",  "price": "279.90", "code_prefix": "IFOD"},
    "ifood_500":   {"name": "🍔 IFOOD 500",   "price": "229.90", "code_prefix": "IFOD"},
    "ifood_300":   {"name": "🍔 IFOOD 300",   "price": "89.90",  "code_prefix": "IFOD"},
    "steam_300":   {"name": "🎮 STEAM 300",   "price": "89.00",  "code_prefix": "STEM"},
    "google_300":  {"name": "🎮 GOOGLE PLAY 300", "price": "89.00", "code_prefix": "GPLY"},
}

# ==================== BANCO DE DADOS ====================

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            card_key TEXT NOT NULL,
            valor REAL NOT NULL,
            codigo_pagamento TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'pendente',
            gift_code TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_pagamento TIMESTAMP,
            qr_code_url TEXT,
            chave_pix TEXT,
            charge_id TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado")

# ==================== GERAÇÃO DE CÓDIGOS ====================

def gerar_codigo_gift_card(prefix):
    if prefix == "SHOP":
        return f"SH{random.randint(10000000, 99999999)}"
    elif prefix == "IFOD":
        return f"IF{random.randint(10000000, 99999999)}"
    elif prefix == "STEM":
        return f"STEAM-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
    elif prefix == "GPLY":
        return f"GPLAY-{random.randint(10000000, 99999999)}"
    return f"{prefix}-{random.randint(10000000, 99999999)}"

def gerar_codigo_pagamento():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

# ==================== TELEGRAM ====================

def enviar_mensagem(chat_id, texto, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")
        return None

def enviar_foto_qr(chat_id, qr_url, caption):
    url = f"{API_URL}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": qr_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar foto: {e}")
        return None

def responder_callback(callback_id, texto):
    url = f"{API_URL}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_id,
        "text": texto,
        "show_alert": False
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao responder callback: {e}")

def criar_teclado_gift_cards():
    botoes = []
    for key, card in GIFT_CARDS.items():
        botoes.append([{
            "text": f"{card['name']} - R$ {card['price']}",
            "callback_data": f"comprar_{key}"
        }])
    botoes.append([{"text": "📲 SUPORTE", "callback_data": "suporte"}])
    return {"inline_keyboard": botoes}

def criar_teclado_pagamento():
    return {
        "inline_keyboard": [
            [{"text": "🔄 /START - Voltar ao Menu", "callback_data": "start"}],
            [{"text": "📲 SUPORTE", "callback_data": "suporte"}]
        ]
    }

# ==================== OASYFY API ====================

def gerar_token_oasyfy():
    try:
        url = f"{OASYFY_API_URL}/auth/token"
        payload = {
            "client_id": OASYFY_CLIENT_ID,
            "client_secret": OASYFY_CLIENT_SECRET
        }
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ Token Oasyfy gerado com sucesso")
            return token
        else:
            print(f"❌ Erro ao gerar token Oasyfy: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Erro na autenticação Oasyfy: {e}")
        return None

def gerar_cobranca_pix(valor, descricao, codigo_pagamento):
    try:
        token = gerar_token_oasyfy()
        if not token:
            print("❌ Sem token Oasyfy - não foi possível gerar cobrança")
            return None

        url = f"{OASYFY_API_URL}/charges"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "amount": float(valor),
            "description": descricao,
            "reference": codigo_pagamento,
            "payment_method": "pix",
            "expire_in": 3600
        }

        print(f"📤 Enviando cobrança para Oasyfy: R$ {valor}")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"📥 Resposta Oasyfy: {response.status_code}")

        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Cobrança gerada: {data}")
            return {
                "qr_code": data.get("qr_code"),
                "qr_code_url": data.get("qr_code_url"),
                "pix_key": data.get("pix_key") or data.get("pix_copy_paste") or data.get("brcode"),
                "charge_id": data.get("id") or data.get("charge_id")
            }
        else:
            print(f"❌ Erro ao gerar cobrança: {response.status_code} - {response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ Erro ao gerar cobrança PIX: {e}")
        return None

def verificar_pagamento_oasyfy(codigo_pagamento, charge_id=None):
    try:
        token = gerar_token_oasyfy()
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Tentar por charge_id primeiro
        if charge_id:
            url = f"{OASYFY_API_URL}/charges/{charge_id}"
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "")
                return {"status": status, "paid": status in ["paid", "approved", "completed"]}

        # Tentar por reference
        url = f"{OASYFY_API_URL}/charges"
        params = {"reference": codigo_pagamento}
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 200:
            data = response.json()
            items = data.get("data", [])
            if items:
                charge = items[0]
                status = charge.get("status", "")
                return {"status": status, "paid": status in ["paid", "approved", "completed"]}

        return None
    except Exception as e:
        print(f"❌ Erro ao verificar pagamento: {e}")
        return None

# ==================== HANDLERS ====================

def handle_start(chat_id, user_name):
    mensagem = f"""👋 <b>Bem-vindo ao Syntek Gift Cards!</b>

Olá {user_name}! 🎉

Aqui você pode comprar Gift Cards com desconto:
✅ Shopee
✅ iFood
✅ Steam
✅ Google Play

Escolha um dos cards abaixo e pague via PIX! 🎁"""

    keyboard = criar_teclado_gift_cards()
    enviar_mensagem(chat_id, mensagem, keyboard)

def handle_callback(callback_id, user_id, chat_id, data_callback):

    if data_callback == "start":
        responder_callback(callback_id, "Voltando ao menu...")
        handle_start(chat_id, "Cliente")
        return

    if data_callback == "suporte":
        responder_callback(callback_id, "Abrindo suporte...")
        mensagem_suporte = """📲 <b>Suporte Syntek</b>

Entre em contato conosco pelo Telegram:
💬 @SyntekOficial

Estamos aqui para ajudar! 💪"""
        enviar_mensagem(chat_id, mensagem_suporte)
        return

    if data_callback.startswith("comprar_"):
        card_key = data_callback.replace("comprar_", "")

        if card_key not in GIFT_CARDS:
            responder_callback(callback_id, "❌ Produto não encontrado!")
            return

        card = GIFT_CARDS[card_key]
        valor = float(card["price"].replace(",", "."))

        # Gerar código único de pagamento
        codigo_pagamento = gerar_codigo_pagamento()

        # Notificar que está gerando
        responder_callback(callback_id, "⏳ Gerando QR Code PIX...")

        # Gerar cobrança via Oasyfy
        print(f"💳 Gerando cobrança PIX para {card['name']} - R$ {valor}")
        pagamento = gerar_cobranca_pix(valor, f"Gift Card {card['name']}", codigo_pagamento)

        if not pagamento:
            # Oasyfy falhou - informar usuário
            mensagem_erro = f"""❌ <b>Erro ao gerar pagamento</b>

Não conseguimos gerar o QR Code PIX neste momento.
Por favor, tente novamente em alguns instantes.

Se o problema persistir, entre em contato: @SyntekOficial"""
            keyboard = criar_teclado_pagamento()
            enviar_mensagem(chat_id, mensagem_erro, keyboard)
            return

        # Salvar transação no banco de dados
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transacoes (user_id, chat_id, card_key, valor, codigo_pagamento, qr_code_url, chave_pix, charge_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, chat_id, card_key, valor, codigo_pagamento,
                  pagamento.get("qr_code_url"), pagamento.get("pix_key"), pagamento.get("charge_id")))
            conn.commit()
            conn.close()
            print(f"✅ Transação salva: {codigo_pagamento}")
        except Exception as e:
            print(f"❌ Erro ao salvar transação: {e}")

        # Montar mensagem de pagamento
        pix_key = pagamento.get("pix_key") or "Indisponível"
        caption = f"""💳 <b>Pagamento PIX</b>

🛒 Produto: <b>{card['name']}</b>
💰 Valor: <b>R$ {card['price']}</b>

📋 <b>Chave PIX (copie e cole):</b>
<code>{pix_key}</code>

⏱️ Válido por 1 hora
🔖 Ref: <code>{codigo_pagamento}</code>"""

        # Tentar enviar QR Code como imagem
        if pagamento.get("qr_code_url"):
            resultado = enviar_foto_qr(chat_id, pagamento["qr_code_url"], caption)
            if not resultado or not resultado.get("ok"):
                # Se falhar, enviar como texto
                enviar_mensagem(chat_id, caption)
        else:
            enviar_mensagem(chat_id, caption)

        # Mensagem de aguardando pagamento
        mensagem_aguardando = """⏳ <b>Aguardando seu pagamento...</b>

Após confirmar o pagamento, seu Gift Card será entregue automaticamente! ✅

Você será notificado assim que o pagamento for confirmado."""

        keyboard = criar_teclado_pagamento()
        enviar_mensagem(chat_id, mensagem_aguardando, keyboard)

# ==================== VERIFICAÇÃO DE PAGAMENTOS ====================

def verificar_pagamentos():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, user_id, chat_id, card_key, valor, codigo_pagamento, charge_id
            FROM transacoes
            WHERE status = 'pendente'
            AND data_criacao > datetime('now', '-2 hours')
        """)

        transacoes = cursor.fetchall()

        for transacao in transacoes:
            id_trans, user_id, chat_id, card_key, valor, codigo_pagamento, charge_id = transacao

            resultado = verificar_pagamento_oasyfy(codigo_pagamento, charge_id)

            if resultado and resultado.get("paid"):
                card = GIFT_CARDS.get(card_key)
                if not card:
                    continue

                gift_code = gerar_codigo_gift_card(card["code_prefix"])

                cursor.execute("""
                    UPDATE transacoes
                    SET status = 'pago', gift_code = ?, data_pagamento = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (gift_code, id_trans))
                conn.commit()

                mensagem_sucesso = f"""✅ <b>Pagamento Confirmado!</b>

Seu Gift Card foi gerado com sucesso! 🎉

<b>{card['name']}</b>
💰 Valor: R$ {valor:.2f}

<b>📋 Seu Código:</b>
<code>{gift_code}</code>

✅ Copie o código acima e adicione ao seu perfil!
Obrigado por comprar conosco! 💝"""

                keyboard = criar_teclado_pagamento()
                enviar_mensagem(chat_id, mensagem_sucesso, keyboard)
                print(f"✅ Gift Card entregue para transação {id_trans}: {gift_code}")

        conn.close()
    except Exception as e:
        print(f"❌ Erro ao verificar pagamentos: {e}")

# ==================== LOOP PRINCIPAL ====================

def processar_atualizacoes():
    offset = 0
    ultima_verificacao = time.time()

    print("🤖 Bot iniciado e aguardando mensagens...")

    while True:
        try:
            # Verificar pagamentos a cada 30 segundos
            tempo_atual = time.time()
            if tempo_atual - ultima_verificacao >= 30:
                verificar_pagamentos()
                ultima_verificacao = tempo_atual

            # Buscar atualizações
            url = f"{API_URL}/getUpdates?offset={offset}&timeout=30"
            response = requests.get(url, timeout=35)
            data = response.json()

            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # Trata mensagens
                    if "message" in update:
                        message = update["message"]
                        chat_id = message["chat"]["id"]
                        user_id = message["from"]["id"]
                        user_name = message["chat"].get("first_name", "Cliente")
                        text = message.get("text", "")

                        if text in ["/start", "/START"]:
                            handle_start(chat_id, user_name)

                    # Trata callbacks (botões)
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        callback_id = callback["id"]
                        user_id = callback["from"]["id"]
                        chat_id = callback["message"]["chat"]["id"]
                        data_callback = callback.get("data", "")

                        handle_callback(callback_id, user_id, chat_id, data_callback)

        except Exception as e:
            print(f"❌ Erro no loop: {e}")
            time.sleep(5)

# ==================== MAIN ====================

if __name__ == "__main__":
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🔑 Oasyfy Client ID: {OASYFY_CLIENT_ID}")
    init_database()
    print("✅ Bot Syntek Gift Cards v2.1 iniciado!")
    print("✅ Integração com Oasyfy ativada")
    print("✅ Verificação de pagamentos ativa (a cada 30s)")
    print("✅ Sistema de rastreamento de transações ativo")
    print("=" * 50)
    processar_atualizacoes()
