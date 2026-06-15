#!/usr/bin/env python3
"""
Bot Syntek Gift Cards - Versão Funcional
Usa a API do Telegram diretamente com polling
"""

import requests
import json
import time
import random
import string
from datetime import datetime

# Configurações
BOT_TOKEN = "8684385675:AAHimsCTILaTzMv2Ta3wG2Sz-oqeSSdEIGo"
ADMIN_ID = 6462638999
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Dados dos Gift Cards
GIFT_CARDS = {
    "shopee_1000": {"name": "🎁 SHOPEE 1000", "price": "299.90", "code_prefix": "SHOP"},
    "shopee_500": {"name": "🎁 SHOPEE 500", "price": "249.90", "code_prefix": "SHOP"},
    "shopee_300": {"name": "🎁 SHOPEE 300", "price": "99.90", "code_prefix": "SHOP"},
    "ifood_1000": {"name": "🍔 IFOOD 1000", "price": "279.90", "code_prefix": "IFOD"},
    "ifood_500": {"name": "🍔 IFOOD 500", "price": "229.90", "code_prefix": "IFOD"},
    "ifood_300": {"name": "🍔 IFOOD 300", "price": "89.90", "code_prefix": "IFOD"},
    "steam_300": {"name": "🎮 STEAM 300", "price": "89.00", "code_prefix": "STEM"},
    "google_300": {"name": "🎮 GOOGLE PLAY 300", "price": "89.00", "code_prefix": "GPLY"},
}

def gerar_codigo_gift_card(prefix):
    """Gera um código de gift card no formato correto"""
    if prefix == "SHOP":  # Shopee
        return f"SH{random.randint(10000000, 99999999)}"
    elif prefix == "IFOD":  # iFood
        return f"IF{random.randint(10000000, 99999999)}"
    elif prefix == "STEM":  # Steam
        return f"STEAM-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
    elif prefix == "GPLY":  # Google Play
        return f"GPLAY-{random.randint(10000000, 99999999)}"
    return f"{prefix}-{random.randint(10000000, 99999999)}"

def enviar_mensagem(chat_id, texto, reply_markup=None):
    """Envia uma mensagem via API do Telegram"""
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    response = requests.post(url, json=payload)
    return response.json()

def criar_teclado_gift_cards():
    """Cria o teclado com os botões de gift cards"""
    botoes = []
    for key, card in GIFT_CARDS.items():
        botoes.append([{
            "text": f"{card['name']} - R$ {card['price']}",
            "callback_data": f"comprar_{key}"
        }])
    
    botoes.append([{"text": "📲 SUPORTE", "callback_data": "suporte"}])
    
    return {
        "inline_keyboard": botoes
    }

def handle_start(chat_id, user_name=""):
    """Trata o comando /start"""
    mensagem = f"""👋 Olá {user_name} Seja bem vindo ao Syntek Gift Cards.

✅ APÓS A COMPRA, VOCÊ RECEBERÁ O CÓDIGO DO GIFT CARD
✅ BASICAMENTE É SÓ ADICIONAR E USAR O SALDO.

⚠️ PARA OUTROS GIFT CARD CONTATE O SUPORTE."""
    
    teclado = criar_teclado_gift_cards()
    enviar_mensagem(chat_id, mensagem, teclado)

def handle_callback(callback_query_id, chat_id, data):
    """Trata callbacks dos botões"""
    if data == "suporte":
        mensagem = "📲 Entre em contato com nosso suporte:\n\n@SyntekOficial"
        enviar_mensagem(chat_id, mensagem)
    
    elif data.startswith("comprar_"):
        card_key = data.replace("comprar_", "")
        if card_key in GIFT_CARDS:
            card = GIFT_CARDS[card_key]
            codigo = gerar_codigo_gift_card(card["code_prefix"])
            
            # Mensagem de pagamento aprovado
            mensagem_aprovado = f"""✅ Pagamento aprovado

Seu código do gift card:

<b>{codigo}</b>

Adicione o gift card no seu perfil e use o saldo!"""
            
            enviar_mensagem(chat_id, mensagem_aprovado)

def processar_atualizacoes():
    """Processa as atualizações do bot"""
    offset = 0
    
    while True:
        try:
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
                        user_name = message["chat"].get("first_name", "")
                        text = message.get("text", "")
                        
                        if text == "/start":
                            handle_start(chat_id, user_name)
                    
                    # Trata callbacks
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        callback_id = callback["id"]
                        chat_id = callback["message"]["chat"]["id"]
                        data = callback.get("data", "")
                        
                        handle_callback(callback_id, chat_id, data)
        
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(5)

if __name__ == "__main__":
    print("🤖 Bot Syntek Gift Cards iniciado!")
    print("Aguardando mensagens...")
    processar_atualizacoes()
