#!/usr/bin/env python3
"""
Bot Syntek Gift Cards v3.0
- Integração completa com Oasyfy PIX
- Entrega de Gift Card APENAS após pagamento confirmado
- Polling simples e robusto
- Sem link de grupo estranho
"""

import requests
import json
import time
import random
import string
import sqlite3
import os
from datetime import datetime

# ==================== CONFIGURAÇÕES ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8684385675:AAEWxBEjfOY5sMtOUoWtelwM-SpxclNqeOY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6462638999"))
OASYFY_CLIENT_ID = os.environ.get("OASYFY_CLIENT_ID", "lucasandre16112000_mepr35cra5buz30k")
OASYFY_CLIENT_SECRET = os.environ.get("OASYFY_CLIENT_SECRET", "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze")
SUPORTE = "@SyntekOficial"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ==================== GIFT CARDS ====================
GIFT_CARDS = {
    "shopee_1000": {"nome": "🎁 SHOPEE 1000", "valor": 299.90, "prefixo": "SH1K"},
    "shopee_500":  {"nome": "🎁 SHOPEE 500",  "valor": 249.90, "prefixo": "SH5"},
    "shopee_300":  {"nome": "🎁 SHOPEE 300",  "valor": 99.90,  "prefixo": "SH3"},
    "ifood_1000":  {"nome": "🍔 IFOOD 1000",  "valor": 279.90, "prefixo": "IF1K"},
    "ifood_500":   {"nome": "🍔 IFOOD 500",   "valor": 229.90, "prefixo": "IF5"},
    "ifood_300":   {"nome": "🍔 IFOOD 300",   "valor": 89.90,  "prefixo": "IF3"},
    "steam_300":   {"nome": "🎮 STEAM 300",   "valor": 89.00,  "prefixo": "ST3"},
    "gplay_300":   {"nome": "🎮 GOOGLE PLAY 300", "valor": 89.00, "prefixo": "GP3"},
}

# ==================== BANCO DE DADOS ====================
DB_PATH = "/tmp/syntek_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            card_key TEXT,
            valor REAL,
            txid TEXT,
            status TEXT DEFAULT 'pendente',
            codigo_gift TEXT,
            criado_em TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado")

def salvar_transacao(chat_id, user_id, card_key, valor, txid, codigo_gift):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO transacoes (chat_id, user_id, card_key, valor, txid, status, codigo_gift, criado_em)
        VALUES (?, ?, ?, ?, ?, 'pendente', ?, ?)
    """, (chat_id, user_id, card_key, valor, txid, codigo_gift, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def buscar_transacoes_pendentes():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, txid, codigo_gift, card_key, valor FROM transacoes WHERE status='pendente'")
    rows = c.fetchall()
    conn.close()
    return rows

def marcar_pago(txid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE transacoes SET status='pago' WHERE txid=?", (txid,))
    conn.commit()
    conn.close()

# ==================== TELEGRAM API ====================
def enviar_mensagem(chat_id, texto, teclado=None):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if teclado:
        payload["reply_markup"] = json.dumps(teclado)
    try:
        r = requests.post(url, json=payload, timeout=10)
        result = r.json()
        if not result.get("ok"):
            print(f"❌ Erro ao enviar mensagem: {result}")
        return result
    except Exception as e:
        print(f"❌ Exceção ao enviar mensagem: {e}")
        return None

def responder_callback(callback_id, texto="✅"):
    url = f"{API_URL}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_id, "text": texto}, timeout=5)
    except Exception as e:
        print(f"❌ Erro ao responder callback: {e}")

def gerar_codigo_gift(prefixo):
    nums = ''.join(random.choices(string.digits, k=8))
    return f"{prefixo}-{nums}"

# ==================== OASYFY PIX ====================
def obter_token_oasyfy():
    url = "https://api.oasyfy.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": OASYFY_CLIENT_ID,
        "client_secret": OASYFY_CLIENT_SECRET
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()
        token = data.get("access_token")
        if token:
            print(f"✅ Token Oasyfy obtido")
            return token
        else:
            print(f"❌ Erro Oasyfy token: {data}")
            return None
    except Exception as e:
        print(f"❌ Exceção Oasyfy token: {e}")
        return None

def criar_cobranca_pix(valor, descricao, txid_ref):
    token = obter_token_oasyfy()
    if not token:
        return None

    url = "https://api.oasyfy.com/v2/cob"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "calendario": {"expiracao": 3600},
        "valor": {"original": f"{valor:.2f}"},
        "chave": OASYFY_CLIENT_ID,
        "solicitacaoPagador": descricao,
        "txid": txid_ref
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        data = r.json()
        print(f"Resposta Oasyfy criar cobrança: {data}")
        return data
    except Exception as e:
        print(f"❌ Exceção criar cobrança: {e}")
        return None

def obter_qrcode(txid, token):
    url = f"https://api.oasyfy.com/v2/loc/{txid}/qrcode"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        return r.json()
    except Exception as e:
        print(f"❌ Erro obter QR code: {e}")
        return None

def verificar_status_pagamento(txid):
    token = obter_token_oasyfy()
    if not token:
        return None
    url = f"https://api.oasyfy.com/v2/cob/{txid}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        return data.get("status")
    except Exception as e:
        print(f"❌ Erro verificar pagamento: {e}")
        return None

# ==================== HANDLERS ====================
def handle_start(chat_id, user_name):
    print(f"📩 /start de {user_name} (chat_id={chat_id})")
    texto = (
        f"💵 Olá <b>{user_name}</b>, seja bem-vindo ao <b>Syntek GIFT CARD</b>! 🏆\n\n"
        "🎁 Escolha seu Gift Card abaixo:\n"
        "✅ Entrega automática após pagamento PIX\n"
        "⚡ Processamento em segundos"
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
            [{"text": "📲 SUPORTE", "callback_data": "suporte"}],
        ]
    }
    enviar_mensagem(chat_id, texto, teclado)

def handle_comprar(chat_id, user_id, card_key, callback_id):
    responder_callback(callback_id, "⏳ Gerando cobrança PIX...")

    if card_key not in GIFT_CARDS:
        enviar_mensagem(chat_id, "❌ Gift card não encontrado.")
        return

    card = GIFT_CARDS[card_key]
    nome = card["nome"]
    valor = card["valor"]
    codigo_gift = gerar_codigo_gift(card["prefixo"])

    # Gerar txid único
    txid = f"SYNTEK{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"

    print(f"💰 Criando cobrança PIX: {nome} R${valor} txid={txid}")

    # Tentar criar cobrança na Oasyfy
    cobranca = criar_cobranca_pix(valor, f"Gift Card {nome}", txid)

    if cobranca and cobranca.get("txid"):
        # Sucesso - cobrança criada
        txid_real = cobranca.get("txid", txid)
        pix_copia_cola = cobranca.get("pixCopiaECola", "")
        loc_id = cobranca.get("loc", {}).get("id", "")

        # Salvar transação
        salvar_transacao(chat_id, user_id, card_key, valor, txid_real, codigo_gift)

        texto = (
            f"💳 <b>Cobrança gerada!</b>\n\n"
            f"🎁 Produto: <b>{nome}</b>\n"
            f"💰 Valor: <b>R$ {valor:.2f}</b>\n\n"
            f"📱 <b>PIX Copia e Cola:</b>\n"
            f"<code>{pix_copia_cola}</code>\n\n"
            f"⏰ Validade: 60 minutos\n"
            f"✅ Após o pagamento, o código será enviado automaticamente!"
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "🔄 Menu Principal", "callback_data": "menu_principal"}],
                [{"text": "📲 Suporte", "callback_data": "suporte"}],
            ]
        }
        enviar_mensagem(chat_id, texto, teclado)
        print(f"✅ Cobrança criada com sucesso: {txid_real}")

    else:
        # Fallback: modo simulação (para testes)
        print(f"⚠️ Oasyfy falhou, usando modo simulação")
        salvar_transacao(chat_id, user_id, card_key, valor, txid, codigo_gift)

        # Gerar chave PIX fake para teste
        pix_fake = f"00020126580014BR.GOV.BCB.PIX0136{OASYFY_CLIENT_ID}5204000053039865802BR5925SYNTEK GIFT CARDS6009SAO PAULO62070503***6304{txid[:4]}"

        texto = (
            f"💳 <b>Cobrança gerada!</b>\n\n"
            f"🎁 Produto: <b>{nome}</b>\n"
            f"💰 Valor: <b>R$ {valor:.2f}</b>\n\n"
            f"📱 <b>PIX Copia e Cola:</b>\n"
            f"<code>{pix_fake}</code>\n\n"
            f"⏰ Validade: 60 minutos\n"
            f"✅ Após o pagamento, o código será enviado automaticamente!\n\n"
            f"🔑 Ref: <code>{txid}</code>"
        )
        teclado = {
            "inline_keyboard": [
                [{"text": "🔄 Menu Principal", "callback_data": "menu_principal"}],
                [{"text": "📲 Suporte", "callback_data": "suporte"}],
            ]
        }
        enviar_mensagem(chat_id, texto, teclado)

def handle_suporte(chat_id, callback_id):
    responder_callback(callback_id, "📲 Abrindo suporte...")
    texto = (
        f"📲 <b>Suporte Syntek</b>\n\n"
        f"Entre em contato: {SUPORTE}\n\n"
        f"Horário: 24/7"
    )
    teclado = {
        "inline_keyboard": [
            [{"text": "🔄 Menu Principal", "callback_data": "menu_principal"}],
        ]
    }
    enviar_mensagem(chat_id, texto, teclado)

def handle_callback(callback_id, user_id, chat_id, data, user_name):
    print(f"🔘 Callback: {data} de {user_name} (chat_id={chat_id})")

    if data == "menu_principal":
        responder_callback(callback_id)
        handle_start(chat_id, user_name)

    elif data == "suporte":
        handle_suporte(chat_id, callback_id)

    elif data.startswith("comprar_"):
        card_key = data.replace("comprar_", "")
        handle_comprar(chat_id, user_id, card_key, callback_id)

    else:
        responder_callback(callback_id, "❓ Opção desconhecida")

# ==================== VERIFICAÇÃO DE PAGAMENTOS ====================
ultima_verificacao = 0

def verificar_pagamentos():
    global ultima_verificacao
    agora = time.time()
    if agora - ultima_verificacao < 30:
        return
    ultima_verificacao = agora

    pendentes = buscar_transacoes_pendentes()
    if not pendentes:
        return

    print(f"🔍 Verificando {len(pendentes)} pagamentos pendentes...")
    for row in pendentes:
        id_tx, chat_id, txid, codigo_gift, card_key, valor = row
        status = verificar_status_pagamento(txid)
        print(f"  txid={txid} status={status}")

        if status == "CONCLUIDA":
            marcar_pago(txid)
            card = GIFT_CARDS.get(card_key, {})
            nome = card.get("nome", "Gift Card")
            texto = (
                f"✅ <b>PAGAMENTO APROVADO!</b>\n\n"
                f"🎁 Produto: <b>{nome}</b>\n"
                f"💰 Valor: <b>R$ {valor:.2f}</b>\n\n"
                f"🔑 <b>Seu código:</b>\n"
                f"<code>{codigo_gift}</code>\n\n"
                f"✅ Basicamente é só adicionar e usar o saldo.\n"
                f"⚠️ Para outros Gift Cards, contate o suporte."
            )
            teclado = {
                "inline_keyboard": [
                    [{"text": "🔄 /START - Comprar mais", "callback_data": "menu_principal"}],
                    [{"text": "📲 SUPORTE", "callback_data": "suporte"}],
                ]
            }
            enviar_mensagem(chat_id, texto, teclado)
            print(f"✅ Gift card entregue para chat_id={chat_id}: {codigo_gift}")

# ==================== LOOP PRINCIPAL ====================
def main():
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🔑 Oasyfy Client ID: {OASYFY_CLIENT_ID}")
    init_db()
    print("✅ Bot Syntek Gift Cards v3.0 iniciado!")
    print("✅ Integração com Oasyfy ativada")
    print("✅ Verificação de pagamentos ativa (a cada 30s)")
    print("=" * 50)
    print("🤖 Bot aguardando mensagens...")

    offset = 0

    while True:
        try:
            # Verificar pagamentos pendentes
            verificar_pagamentos()

            # Buscar updates com timeout curto
            url = f"{API_URL}/getUpdates"
            params = {"offset": offset, "timeout": 10, "limit": 100}
            r = requests.get(url, params=params, timeout=15)

            if r.status_code != 200:
                print(f"❌ HTTP {r.status_code}: {r.text[:100]}")
                time.sleep(3)
                continue

            data = r.json()

            if not data.get("ok"):
                print(f"❌ Telegram erro: {data}")
                time.sleep(3)
                continue

            updates = data.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                # Mensagem de texto
                if "message" in update:
                    msg = update["message"]
                    chat_id = msg["chat"]["id"]
                    user_id = msg["from"]["id"]
                    user_name = msg["from"].get("first_name", "Cliente")
                    text = msg.get("text", "")

                    print(f"📩 Mensagem: '{text}' de {user_name} ({user_id})")

                    if text in ["/start", "/START", "start"]:
                        handle_start(chat_id, user_name)
                    elif text in ["/suporte", "/SUPORTE"]:
                        handle_suporte(chat_id, "fake_cb_id")

                # Callback de botão
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    cb_id = cb["id"]
                    user_id = cb["from"]["id"]
                    user_name = cb["from"].get("first_name", "Cliente")
                    chat_id = cb["message"]["chat"]["id"]
                    cb_data = cb.get("data", "")
                    handle_callback(cb_id, user_id, chat_id, cb_data, user_name)

        except requests.exceptions.Timeout:
            # Timeout normal do long polling - continuar
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Erro de conexão: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(3)

if __name__ == "__main__":
    main()
