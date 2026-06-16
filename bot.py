#!/usr/bin/env python3
"""
Bot Syntek Gift Cards v4.0
- Integração Oasyfy REAL com endpoint correto
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8684385675:AAEWxBEjfOY5sMtOUoWtelwM-SpxclNqeOY")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6462638999"))
OASYFY_PUBLIC_KEY = os.environ.get("OASYFY_PUBLIC_KEY", "lucasandre16112000_mepr35cra5buz30k")
OASYFY_SECRET_KEY = os.environ.get("OASYFY_SECRET_KEY", "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze")
OASYFY_BASE_URL = "https://app.oasyfy.com/api/v1"

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
def init_db():
    conn = sqlite3.connect("/tmp/syntek_bot.db")
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
    conn = sqlite3.connect("/tmp/syntek_bot.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO transacoes (chat_id, transaction_id, identifier, card_key, valor, status, criado_em)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
    """, (chat_id, transaction_id, identifier, card_key, valor, int(time.time())))
    conn.commit()
    conn.close()

def buscar_pendentes():
    conn = sqlite3.connect("/tmp/syntek_bot.db")
    c = conn.cursor()
    c.execute("""
        SELECT id, chat_id, transaction_id, card_key
        FROM transacoes
        WHERE status = 'PENDING' AND criado_em > ?
    """, (int(time.time()) - 3600,))  # últimas 1 hora
    rows = c.fetchall()
    conn.close()
    return rows

def atualizar_status(transaction_id, status, codigo=None):
    conn = sqlite3.connect("/tmp/syntek_bot.db")
    c = conn.cursor()
    c.execute("""
        UPDATE transacoes SET status = ?, codigo_gift = ? WHERE transaction_id = ?
    """, (status, codigo, transaction_id))
    conn.commit()
    conn.close()

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
        return r.json()
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        return None

def enviar_foto(chat_id, foto_url, caption=None, teclado=None):
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": foto_url,
    }
    if caption:
        payload["caption"] = caption
        payload["parse_mode"] = "Markdown"
    if teclado:
        payload["reply_markup"] = json.dumps(teclado)
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        logger.error(f"Erro ao enviar foto: {e}")
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
    """Cria uma cobrança PIX na Oasyfy e retorna os dados"""
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
            "name": f"Cliente Telegram {chat_id}",
            "email": f"cliente{chat_id}@syntek.bot",
            "phone": "11999999999",
            "document": "529.982.247-25"  # CPF fictício válido
        },
        "products": [
            {
                "id": card_key,
                "name": nome_card,
                "quantity": 1,
                "price": valor
            }
        ],
        "metadata": {
            "chat_id": str(chat_id),
            "card_key": card_key,
            "bot": "SyntekCardPaybot"
        }
    }
    try:
        r = requests.post(
            f"{OASYFY_BASE_URL}/gateway/pix/receive",
            headers=headers,
            json=payload,
            timeout=20
        )
        logger.info(f"Oasyfy PIX response: {r.status_code} - {r.text[:300]}")
        if r.status_code in [200, 201]:
            data = r.json()
            return {
                "transaction_id": data.get("transactionId"),
                "identifier": identifier,
                "pix_code": data.get("pix", {}).get("code") or data.get("pix", {}).get("qrCode"),
                "pix_url": data.get("pix", {}).get("url"),
                "status": data.get("status")
            }
        else:
            logger.error(f"Erro Oasyfy: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        logger.error(f"Exceção ao criar cobrança PIX: {e}")
        return None

def verificar_pagamento(transaction_id):
    """Verifica o status de um pagamento na Oasyfy"""
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
        logger.error(f"Erro ao verificar pagamento: {e}")
        return None

# ============================================================
# GERAÇÃO DE CÓDIGOS GIFT CARD
# ============================================================
def gerar_codigo(prefixo):
    parte1 = ''.join(random.choices(string.digits, k=4))
    parte2 = ''.join(random.choices(string.digits, k=4))
    parte3 = ''.join(random.choices(string.digits, k=4))
    return f"{prefixo}-{parte1}-{parte2}-{parte3}"

# ============================================================
# TECLADOS
# ============================================================
def teclado_menu():
    botoes = []
    cards = list(GIFT_CARDS.items())
    for i in range(0, len(cards), 1):
        key, card = cards[i]
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
def handle_start(chat_id, nome_usuario=""):
    texto = (
        f"💰 *Bem-vindo ao Syntek Gift Cards!*\n\n"
        f"Olá {nome_usuario}! 👋\n\n"
        f"🎁 *CÓDIGO DO GIFT CARD*\n"
        f"✅ Basicamente é só adicionar e usar o saldo.\n\n"
        f"⚠️ *PARA OUTROS GIFT CARDS CONTATE O SUPORTE.*\n\n"
        f"Escolha seu Gift Card abaixo:"
    )
    enviar_mensagem(chat_id, texto, teclado=teclado_menu())
    logger.info(f"✅ /start processado para chat_id={chat_id}")

def handle_comprar(chat_id, card_key, callback_query_id):
    responder_callback(callback_query_id, "⏳ Gerando cobrança PIX...")
    
    if card_key not in GIFT_CARDS:
        enviar_mensagem(chat_id, "❌ Gift Card não encontrado.")
        return
    
    card = GIFT_CARDS[card_key]
    valor = card["valor"]
    nome = card["nome"]
    
    logger.info(f"Criando cobrança PIX para chat_id={chat_id}, card={card_key}, valor={valor}")
    
    # Criar cobrança na Oasyfy
    resultado = criar_cobranca_pix(chat_id, card_key, valor, nome)
    
    if not resultado or not resultado.get("transaction_id"):
        logger.error(f"Falha ao criar cobrança para chat_id={chat_id}")
        enviar_mensagem(
            chat_id,
            f"❌ *Erro ao gerar cobrança*\n\n"
            f"Não foi possível gerar o QR Code no momento.\n"
            f"Por favor, tente novamente ou contate o suporte.\n\n"
            f"📲 Suporte: @SyntekOficial",
            teclado=teclado_pos_compra()
        )
        return
    
    transaction_id = resultado["transaction_id"]
    pix_code = resultado.get("pix_code", "")
    
    # Salvar no banco de dados
    salvar_transacao(chat_id, transaction_id, resultado["identifier"], card_key, valor)
    
    # Enviar mensagem com PIX
    texto_pix = (
        f"💳 *Pagamento via PIX*\n\n"
        f"🎁 *Produto:* {nome}\n"
        f"💰 *Valor:* R$ {valor:.2f}\n\n"
        f"📋 *Chave PIX (Copia e Cola):*\n"
        f"`{pix_code}`\n\n"
        f"⏰ *Prazo:* 30 minutos\n\n"
        f"✅ Após o pagamento, clique em *'Já paguei - Verificar'*\n"
        f"O código do Gift Card será entregue automaticamente!"
    )
    
    enviar_mensagem(
        chat_id,
        texto_pix,
        teclado=teclado_aguardando(transaction_id)
    )
    logger.info(f"✅ Cobrança PIX criada: transaction_id={transaction_id}")

def handle_verificar(chat_id, transaction_id, callback_query_id):
    responder_callback(callback_query_id, "🔍 Verificando pagamento...")
    
    status = verificar_pagamento(transaction_id)
    logger.info(f"Status pagamento {transaction_id}: {status}")
    
    if status == "OK":
        # Buscar card_key do banco
        conn = sqlite3.connect("/tmp/syntek_bot.db")
        c = conn.cursor()
        c.execute("SELECT card_key FROM transacoes WHERE transaction_id = ?", (transaction_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            card_key = row[0]
            card = GIFT_CARDS.get(card_key, {})
            prefixo = card.get("prefixo", "GC")
            codigo = gerar_codigo(prefixo)
            atualizar_status(transaction_id, "PAID", codigo)
            
            texto_entrega = (
                f"✅ *PAGAMENTO APROVADO!*\n\n"
                f"🎁 *Seu Gift Card:* {card.get('nome', '')}\n\n"
                f"🔑 *Código:*\n"
                f"`{codigo}`\n\n"
                f"✅ Basicamente é só adicionar e usar o saldo.\n\n"
                f"⚠️ Para outros Gift Cards, contate o suporte."
            )
            enviar_mensagem(chat_id, texto_entrega, teclado=teclado_pos_compra())
            logger.info(f"✅ Gift card entregue para chat_id={chat_id}: {codigo}")
    elif status == "PENDING":
        enviar_mensagem(
            chat_id,
            "⏳ *Pagamento ainda não confirmado*\n\nAguarde alguns instantes e tente novamente.",
            teclado=teclado_aguardando(transaction_id)
        )
    else:
        enviar_mensagem(
            chat_id,
            f"❌ *Pagamento não encontrado ou expirado*\n\nStatus: {status}\n\nContate o suporte se precisar de ajuda.",
            teclado=teclado_pos_compra()
        )

def handle_suporte(chat_id, callback_query_id):
    responder_callback(callback_query_id)
    enviar_mensagem(
        chat_id,
        "📲 *SUPORTE SYNTEK*\n\nEntre em contato com nossa equipe:\n👤 @SyntekOficial\n\nHorário: 24/7"
    )

def handle_cancelar(chat_id, callback_query_id):
    responder_callback(callback_query_id, "❌ Pedido cancelado")
    enviar_mensagem(chat_id, "❌ Pedido cancelado.\n\nVolte quando quiser!", teclado=teclado_menu())

# ============================================================
# VERIFICADOR AUTOMÁTICO DE PAGAMENTOS
# ============================================================
def verificador_automatico():
    """Verifica pagamentos pendentes a cada 30 segundos"""
    while True:
        try:
            pendentes = buscar_pendentes()
            for row in pendentes:
                db_id, chat_id, transaction_id, card_key = row
                status = verificar_pagamento(transaction_id)
                logger.info(f"Auto-verificação: transaction={transaction_id}, status={status}")
                
                if status == "OK":
                    card = GIFT_CARDS.get(card_key, {})
                    prefixo = card.get("prefixo", "GC")
                    codigo = gerar_codigo(prefixo)
                    atualizar_status(transaction_id, "PAID", codigo)
                    
                    texto_entrega = (
                        f"✅ *PAGAMENTO APROVADO AUTOMATICAMENTE!*\n\n"
                        f"🎁 *Seu Gift Card:* {card.get('nome', '')}\n\n"
                        f"🔑 *Código:*\n"
                        f"`{codigo}`\n\n"
                        f"✅ Basicamente é só adicionar e usar o saldo.\n\n"
                        f"⚠️ Para outros Gift Cards, contate o suporte."
                    )
                    enviar_mensagem(chat_id, texto_entrega, teclado=teclado_pos_compra())
                    logger.info(f"✅ Auto-entrega: chat_id={chat_id}, codigo={codigo}")
                    
                elif status in ["FAILED", "CANCELED", "REJECTED"]:
                    atualizar_status(transaction_id, status)
        except Exception as e:
            logger.error(f"Erro no verificador automático: {e}")
        
        time.sleep(30)

# ============================================================
# PROCESSAMENTO DE UPDATES
# ============================================================
def processar_update(update):
    try:
        # Mensagem de texto
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            texto = msg.get("text", "")
            nome = msg.get("from", {}).get("first_name", "")
            
            logger.info(f"📨 Mensagem recebida: chat_id={chat_id}, texto='{texto}'")
            
            if texto in ["/start", "/Start", "start"]:
                handle_start(chat_id, nome)
            elif texto == "/suporte":
                enviar_mensagem(chat_id, "📲 *SUPORTE SYNTEK*\n\nEntre em contato:\n👤 @SyntekOficial")
        
        # Callback de botão
        elif "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            data = cq.get("data", "")
            cq_id = cq["id"]
            
            logger.info(f"🔘 Callback recebido: chat_id={chat_id}, data='{data}'")
            
            if data == "start":
                responder_callback(cq_id)
                nome = cq.get("from", {}).get("first_name", "")
                handle_start(chat_id, nome)
            elif data.startswith("comprar_"):
                card_key = data.replace("comprar_", "")
                handle_comprar(chat_id, card_key, cq_id)
            elif data.startswith("verificar_"):
                transaction_id = data.replace("verificar_", "")
                handle_verificar(chat_id, transaction_id, cq_id)
            elif data == "suporte":
                handle_suporte(chat_id, cq_id)
            elif data == "cancelar":
                handle_cancelar(chat_id, cq_id)
    
    except Exception as e:
        logger.error(f"Erro ao processar update: {e}", exc_info=True)

# ============================================================
# LOOP PRINCIPAL
# ============================================================
def main():
    init_db()
    logger.info("✅ Bot Syntek Gift Cards v4.0 iniciado!")
    logger.info(f"✅ Token: {BOT_TOKEN[:20]}...")
    logger.info(f"✅ Oasyfy: {OASYFY_PUBLIC_KEY[:20]}...")
    logger.info("✅ Verificador automático de pagamentos ativo (30s)")
    
    # Iniciar verificador automático em thread separada
    t = threading.Thread(target=verificador_automatico, daemon=True)
    t.start()
    
    # Limpar webhook
    requests.get(f"{TELEGRAM_API}/deleteWebhook", timeout=10)
    
    offset = 0
    logger.info("🤖 Bot aguardando mensagens...")
    
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
                    updates = data.get("result", [])
                    for update in updates:
                        update_id = update["update_id"]
                        offset = update_id + 1
                        processar_update(update)
            elif r.status_code == 409:
                logger.warning("⚠️ Conflito de instância detectado. Aguardando 5s...")
                time.sleep(5)
            else:
                logger.error(f"Erro getUpdates: {r.status_code} - {r.text[:100]}")
                time.sleep(3)
                
        except requests.exceptions.Timeout:
            pass  # Normal para long polling
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
