#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BOT SYNTEK GIFT CARDS - Versão TeleBotHost
Telegram Bot para venda de Gift Cards com pagamento via Pix
"""

import telebot
import sqlite3
import random
import string
import threading
import time
from datetime import datetime

# ==================== CONFIGURAÇÕES ====================

BOT_TOKEN = "8684385675:AAHimsCTILaTzMv2Ta3wG2Sz-oqeSSdEIGo"
ADMIN_ID = 6462638999

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== BANCO DE DADOS ====================

def init_db():
    """Inicializa o banco de dados"""
    conn = sqlite3.connect('syntek_bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  created_at TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  gift_card_type TEXT,
                  amount REAL,
                  status TEXT,
                  code TEXT,
                  created_at TIMESTAMP)''')
    
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name):
    """Adiciona usuário ao banco"""
    conn = sqlite3.connect('syntek_bot.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, created_at)
                    VALUES (?, ?, ?, ?)''',
                 (user_id, username, first_name, datetime.now()))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def get_all_users():
    """Retorna todos os usuários"""
    conn = sqlite3.connect('syntek_bot.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# ==================== GERADOR DE CÓDIGOS ====================

class GiftCardCodeGenerator:
    @staticmethod
    def generate_shopee():
        chars = string.ascii_uppercase + string.digits
        return "SH" + ''.join(random.choices(chars, k=16))
    
    @staticmethod
    def generate_ifood():
        chars = string.ascii_uppercase + string.digits
        return "IF0D" + ''.join(random.choices(chars, k=12))
    
    @staticmethod
    def generate_steam():
        hex_chars = string.hexdigits[:16]
        parts = [''.join(random.choices(hex_chars, k=4)).upper() for _ in range(4)]
        return "STEAM-" + "-".join(parts)
    
    @staticmethod
    def generate_google_play():
        chars = string.ascii_uppercase + string.digits
        parts = [''.join(random.choices(chars, k=4)) for _ in range(4)]
        return "GPLAY-" + "-".join(parts)
    
    @staticmethod
    def generate(gift_card_type):
        if "shopee" in gift_card_type.lower():
            return GiftCardCodeGenerator.generate_shopee()
        elif "ifood" in gift_card_type.lower():
            return GiftCardCodeGenerator.generate_ifood()
        elif "steam" in gift_card_type.lower():
            return GiftCardCodeGenerator.generate_steam()
        elif "google" in gift_card_type.lower():
            return GiftCardCodeGenerator.generate_google_play()
        return None

# ==================== DADOS DOS GIFT CARDS ====================

GIFT_CARDS = [
    {"name": "🎁 SHOPEE 1000", "value": 1000, "price": 299.90, "type": "shopee_1000"},
    {"name": "🎁 SHOPEE 500", "value": 500, "price": 249.90, "type": "shopee_500"},
    {"name": "🎁 SHOPEE 300", "value": 300, "price": 99.90, "type": "shopee_300"},
    {"name": "🍔 IFOOD 1000", "value": 1000, "price": 279.90, "type": "ifood_1000"},
    {"name": "🍔 IFOOD 500", "value": 500, "price": 229.90, "type": "ifood_500"},
    {"name": "🍔 IFOOD 300", "value": 300, "price": 89.90, "type": "ifood_300"},
    {"name": "🎮 STEAM 300", "value": 300, "price": 89.00, "type": "steam_300"},
    {"name": "🎮 GOOGLE PLAY 300", "value": 300, "price": 89.00, "type": "google_play_300"},
]

# ==================== HANDLERS ====================

@bot.message_handler(commands=['start'])
def start(message):
    """Handler para /start"""
    user = message.from_user
    add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""👋 Olá {user.first_name} Seja bem vindo ao Syntek Gift Cards.

✅ APÓS A COMPRA, VOCÊ RECEBERÁ O CÓDIGO DO GIFT CARD 
✅ BASICAMENTE É SÓ ADICIONAR E USAR O SALDO.

⚠️ PARA OUTROS GIFT CARD CONTATE O SUPORTE."""
    
    markup = telebot.types.InlineKeyboardMarkup()
    for gc in GIFT_CARDS:
        button_text = f"{gc['name']} - R$ {gc['price']:.2f}"
        markup.add(telebot.types.InlineKeyboardButton(button_text, callback_data=f"gc_{gc['type']}"))
    
    markup.add(telebot.types.InlineKeyboardButton("📲 SUPORTE", callback_data="support"))
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Handler para cliques em botões"""
    chat_id = call.message.chat.id
    callback_data = call.data
    
    # Suporte
    if callback_data == "support":
        support_text = """📲 SUPORTE

Para dúvidas ou problemas, entre em contato:

@SyntekOficial"""
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🏠 VOLTAR AO MENU", callback_data="menu"))
        bot.edit_message_text(support_text, chat_id, call.message.message_id, reply_markup=markup)
        return
    
    # Voltar ao menu
    if callback_data == "menu":
        welcome_text = "Escolha um Gift Card:"
        markup = telebot.types.InlineKeyboardMarkup()
        for gc in GIFT_CARDS:
            button_text = f"{gc['name']} - R$ {gc['price']:.2f}"
            markup.add(telebot.types.InlineKeyboardButton(button_text, callback_data=f"gc_{gc['type']}"))
        markup.add(telebot.types.InlineKeyboardButton("📲 SUPORTE", callback_data="support"))
        bot.edit_message_text(welcome_text, chat_id, call.message.message_id, reply_markup=markup)
        return
    
    # Gift card selecionado
    if callback_data.startswith("gc_"):
        gc_type = callback_data.replace("gc_", "")
        
        selected_gc = None
        for gc in GIFT_CARDS:
            if gc['type'] == gc_type:
                selected_gc = gc
                break
        
        if not selected_gc:
            bot.send_message(chat_id, "❌ Gift Card não encontrado!")
            return
        
        # Mensagem de pagamento
        payment_text = f"""💳 PAGAMENTO - {selected_gc['name'].upper()}

Valor: R$ {selected_gc['price']:.2f}

Escaneie o QR Code abaixo ou copie a chave Pix:

[QR CODE AQUI - Será gerado via Oasyfy]

Chave Pix: 00020126580014br.gov.bcb.pix0136lucasandre16112000_mepr35cra5buz30k520400005303986540510.005802BR5913SYNTEK6009SAO PAULO62410503***63041D3D

⏱️ Este QR Code expira em 30 minutos"""
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"confirm_{gc_type}"))
        markup.add(telebot.types.InlineKeyboardButton("❌ CANCELAR", callback_data="menu"))
        
        bot.edit_message_text(payment_text, chat_id, call.message.message_id, reply_markup=markup)
        return
    
    # Confirmar pagamento
    if callback_data.startswith("confirm_"):
        gc_type = callback_data.replace("confirm_", "")
        
        selected_gc = None
        for gc in GIFT_CARDS:
            if gc['type'] == gc_type:
                selected_gc = gc
                break
        
        if not selected_gc:
            return
        
        # Gera código
        code = GiftCardCodeGenerator.generate(gc_type)
        
        # Mensagem de sucesso
        success_text = "✅ Pagamento aprovado"
        bot.edit_message_text(success_text, chat_id, call.message.message_id)
        
        # Entrega do código
        if "shopee" in gc_type.lower():
            delivery_text = f"""Adicione o gift card no seu perfil em CUPONS

GIFT: {code}"""
        elif "ifood" in gc_type.lower():
            delivery_text = f"""Seu código IFOOD:

GIFT: {code}"""
        elif "steam" in gc_type.lower():
            delivery_text = f"""Seu código STEAM:

GIFT: {code}"""
        elif "google" in gc_type.lower():
            delivery_text = f"""Seu código GOOGLE PLAY:

GIFT: {code}"""
        else:
            delivery_text = f"""Seu código:

GIFT: {code}"""
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🏠 VOLTAR AO MENU", callback_data="menu"))
        markup.add(telebot.types.InlineKeyboardButton("💱 COMPRAR OUTRO", callback_data="menu"))
        
        bot.send_message(chat_id, delivery_text, reply_markup=markup)

def send_promotion():
    """Envia promoção a cada 2 horas"""
    promotion_text = """✅ PROMOÇÃO
🔹 SHOPEE
🔹 IFOOD
🔹 GOOGLE PLAY
🔹 CASAS BAHIA
🔹 ROBLOX
🔹 STEAM
🔹 ZÉ DELIVERY
🔹 AIRBNB
🔹 APPLE STORE
🔹 UBER

Outros Gift Chame o Suporte.

❖ 1000 DE SALDO PAGA 299.90R$
❖ 500 DE SALDO PAGA 249,90R$
❖ 300 DE SALDO PAGA R$ 99.90

⚠️ É SÓ ADICIONAR E REALIZAR AS COMPRAS, NÃO TEM SEGREDO.✅🦅🚀"""
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📲 SUPORTE", callback_data="support"))
    markup.add(telebot.types.InlineKeyboardButton("💱 GIFT CARDS", callback_data="menu"))
    
    users = get_all_users()
    for user_id in users:
        try:
            bot.send_message(user_id, promotion_text, reply_markup=markup)
        except:
            pass

def promotion_thread():
    """Thread para enviar promoção a cada 2 horas"""
    while True:
        time.sleep(7200)  # 2 horas
        send_promotion()

# ==================== MAIN ====================

if __name__ == '__main__':
    init_db()
    
    # Inicia thread de promoção
    promo_thread = threading.Thread(target=promotion_thread, daemon=True)
    promo_thread.start()
    
    print("🤖 Bot iniciado!")
    bot.infinity_polling()
