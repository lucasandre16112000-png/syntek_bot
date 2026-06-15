#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BOT SYNTEK GIFT CARDS
Telegram Bot para venda de Gift Cards com pagamento via Pix
"""

import logging
import sqlite3
import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import requests
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)
from telegram.error import TelegramError

# ==================== CONFIGURAÇÕES ====================

# Tokens e IDs
BOT_TOKEN = "8684385675:AAHimsCTILaTzMv2Ta3wG2Sz-oqeSSdEIGo"
ADMIN_ID = 6462638999

# Oasyfy API
OASYFY_CLIENT_ID = "lucasandre16112000_mepr35cra5buz30k"
OASYFY_CLIENT_SECRET = "76zh1cvrxisjub8u0txh5tygb65unatj2rmdppeohdnbfxmu8yy0idimycw3n0ze"
OASYFY_API_URL = "https://api.oasyfy.com"

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== BANCO DE DADOS ====================

class Database:
    def __init__(self, db_name='syntek_bot.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """Inicializa o banco de dados"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Tabela de usuários
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      username TEXT,
                      first_name TEXT,
                      created_at TIMESTAMP)''')
        
        # Tabela de transações
        c.execute('''CREATE TABLE IF NOT EXISTS transactions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      gift_card_type TEXT,
                      amount REAL,
                      status TEXT,
                      code TEXT,
                      created_at TIMESTAMP,
                      paid_at TIMESTAMP)''')
        
        # Tabela de pagamentos Pix
        c.execute('''CREATE TABLE IF NOT EXISTS pix_payments
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      transaction_id INTEGER,
                      pix_key TEXT,
                      qr_code TEXT,
                      amount REAL,
                      status TEXT,
                      created_at TIMESTAMP,
                      expires_at TIMESTAMP)''')
        
        conn.commit()
        conn.close()

    def add_user(self, user_id, username, first_name):
        """Adiciona novo usuário ao banco"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        try:
            c.execute('''INSERT OR IGNORE INTO users (user_id, username, first_name, created_at)
                        VALUES (?, ?, ?, ?)''',
                     (user_id, username, first_name, datetime.now()))
            conn.commit()
        except Exception as e:
            logger.error(f"Erro ao adicionar usuário: {e}")
        finally:
            conn.close()

    def get_all_users(self):
        """Retorna todos os usuários"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('SELECT user_id FROM users')
        users = [row[0] for row in c.fetchall()]
        conn.close()
        return users

    def add_transaction(self, user_id, gift_card_type, amount):
        """Adiciona transação"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''INSERT INTO transactions (user_id, gift_card_type, amount, status, created_at)
                    VALUES (?, ?, ?, ?, ?)''',
                 (user_id, gift_card_type, amount, 'pending', datetime.now()))
        conn.commit()
        transaction_id = c.lastrowid
        conn.close()
        return transaction_id

    def update_transaction(self, transaction_id, status, code=None, paid_at=None):
        """Atualiza status da transação"""
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        if code:
            c.execute('''UPDATE transactions SET status=?, code=?, paid_at=? WHERE id=?''',
                     (status, code, paid_at or datetime.now(), transaction_id))
        else:
            c.execute('''UPDATE transactions SET status=?, paid_at=? WHERE id=?''',
                     (status, paid_at or datetime.now(), transaction_id))
        conn.commit()
        conn.close()

db = Database()

# ==================== GERADOR DE CÓDIGOS ====================

class GiftCardCodeGenerator:
    """Gera códigos de gift cards no formato correto"""
    
    @staticmethod
    def generate_shopee():
        """Gera código Shopee: SH + 16 caracteres"""
        chars = string.ascii_uppercase + string.digits
        code = "SH" + ''.join(random.choices(chars, k=16))
        return code
    
    @staticmethod
    def generate_ifood():
        """Gera código iFood: IF0D + 12 caracteres"""
        chars = string.ascii_uppercase + string.digits
        code = "IF0D" + ''.join(random.choices(chars, k=12))
        return code
    
    @staticmethod
    def generate_steam():
        """Gera código Steam: STEAM-XXXX-XXXX-XXXX-XXXX"""
        hex_chars = string.hexdigits[:16]  # 0-9, A-F
        parts = [
            ''.join(random.choices(hex_chars, k=4)).upper(),
            ''.join(random.choices(hex_chars, k=4)).upper(),
            ''.join(random.choices(hex_chars, k=4)).upper(),
            ''.join(random.choices(hex_chars, k=4)).upper(),
        ]
        code = "STEAM-" + "-".join(parts)
        return code
    
    @staticmethod
    def generate_google_play():
        """Gera código Google Play: GPLAY-XXXX-XXXX-XXXX-XXXX"""
        chars = string.ascii_uppercase + string.digits
        parts = [
            ''.join(random.choices(chars, k=4)),
            ''.join(random.choices(chars, k=4)),
            ''.join(random.choices(chars, k=4)),
            ''.join(random.choices(chars, k=4)),
        ]
        code = "GPLAY-" + "-".join(parts)
        return code
    
    @staticmethod
    def generate(gift_card_type):
        """Gera código baseado no tipo de gift card"""
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
    # SHOPEE (Ordem: 1000 > 500 > 300)
    {"name": "🎁 SHOPEE 1000", "value": 1000, "price": 299.90, "type": "shopee_1000"},
    {"name": "🎁 SHOPEE 500", "value": 500, "price": 249.90, "type": "shopee_500"},
    {"name": "🎁 SHOPEE 300", "value": 300, "price": 99.90, "type": "shopee_300"},
    
    # IFOOD (Ordem: 1000 > 500 > 300)
    {"name": "🍔 IFOOD 1000", "value": 1000, "price": 279.90, "type": "ifood_1000"},
    {"name": "🍔 IFOOD 500", "value": 500, "price": 229.90, "type": "ifood_500"},
    {"name": "🍔 IFOOD 300", "value": 300, "price": 89.90, "type": "ifood_300"},
    
    # STEAM e GOOGLE PLAY
    {"name": "🎮 STEAM 300", "value": 300, "price": 89.00, "type": "steam_300"},
    {"name": "🎮 GOOGLE PLAY 300", "value": 300, "price": 89.00, "type": "google_play_300"},
]

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /start"""
    user = update.effective_user
    
    # Adiciona usuário ao banco de dados
    db.add_user(user.id, user.username, user.first_name)
    
    # Mensagem de boas-vindas
    welcome_text = f"""👋 Olá {user.first_name} Seja bem vindo ao Syntek Gift Cards.

✅ APÓS A COMPRA, VOCÊ RECEBERÁ O CÓDIGO DO GIFT CARD 
✅ BASICAMENTE É SÓ ADICIONAR E USAR O SALDO.

⚠️ PARA OUTROS GIFT CARD CONTATE O SUPORTE."""
    
    # Cria teclado com gift cards
    keyboard = []
    for gc in GIFT_CARDS:
        button_text = f"{gc['name']} - R$ {gc['price']:.2f}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"gc_{gc['type']}")])
    
    # Adiciona botão de suporte
    keyboard.append([InlineKeyboardButton("📲 SUPORTE", callback_data="support")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para cliques em botões"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Suporte
    if callback_data == "support":
        support_text = """📲 SUPORTE

Para dúvidas ou problemas, entre em contato:

@SyntekOficial"""
        keyboard = [[InlineKeyboardButton("🏠 VOLTAR AO MENU", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(support_text, reply_markup=reply_markup)
        return
    
    # Voltar ao menu
    if callback_data == "menu":
        welcome_text = "Escolha um Gift Card:"
        keyboard = []
        for gc in GIFT_CARDS:
            button_text = f"{gc['name']} - R$ {gc['price']:.2f}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"gc_{gc['type']}")])
        keyboard.append([InlineKeyboardButton("📲 SUPORTE", callback_data="support")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(welcome_text, reply_markup=reply_markup)
        return
    
    # Gift card selecionado
    if callback_data.startswith("gc_"):
        gc_type = callback_data.replace("gc_", "")
        
        # Encontra o gift card
        selected_gc = None
        for gc in GIFT_CARDS:
            if gc['type'] == gc_type:
                selected_gc = gc
                break
        
        if not selected_gc:
            await query.edit_message_text("❌ Gift Card não encontrado!")
            return
        
        # Cria transação
        transaction_id = db.add_transaction(user_id, gc_type, selected_gc['price'])
        context.user_data['current_transaction'] = transaction_id
        context.user_data['current_gc'] = selected_gc
        
        # Gera QR Code Pix (simulado por enquanto)
        payment_text = f"""💳 PAGAMENTO - {selected_gc['name'].upper()}

Valor: R$ {selected_gc['price']:.2f}

Escaneie o QR Code abaixo ou copie a chave Pix:

[QR CODE AQUI - Será gerado via Oasyfy]

Chave Pix: 00020126580014br.gov.bcb.pix0136{OASYFY_CLIENT_ID}520400005303986540510.005802BR5913SYNTEK6009SAO PAULO62410503***63041D3D

⏱️ Este QR Code expira em 30 minutos"""
        
        keyboard = [
            [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"confirm_payment_{transaction_id}")],
            [InlineKeyboardButton("❌ CANCELAR", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(payment_text, reply_markup=reply_markup)
        return
    
    # Confirmar pagamento
    if callback_data.startswith("confirm_payment_"):
        transaction_id = int(callback_data.replace("confirm_payment_", ""))
        
        # Gera código do gift card
        gc_type = context.user_data.get('current_gc', {}).get('type')
        code = GiftCardCodeGenerator.generate(gc_type)
        
        # Atualiza transação
        db.update_transaction(transaction_id, 'completed', code)
        
        # Mensagem de sucesso
        success_text = "✅ Pagamento aprovado"
        await query.edit_message_text(success_text)
        
        # Entrega do código
        gc = context.user_data.get('current_gc')
        if gc:
            if "shopee" in gc['type'].lower():
                delivery_text = f"""Adicione o gift card no seu perfil em CUPONS

GIFT: {code}"""
            elif "ifood" in gc['type'].lower():
                delivery_text = f"""Seu código IFOOD:

GIFT: {code}"""
            elif "steam" in gc['type'].lower():
                delivery_text = f"""Seu código STEAM:

GIFT: {code}"""
            elif "google" in gc['type'].lower():
                delivery_text = f"""Seu código GOOGLE PLAY:

GIFT: {code}"""
            else:
                delivery_text = f"""Seu código:

GIFT: {code}"""
            
            keyboard = [
                [InlineKeyboardButton("🏠 VOLTAR AO MENU", callback_data="menu")],
                [InlineKeyboardButton("💱 COMPRAR OUTRO", callback_data="menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(delivery_text, reply_markup=reply_markup)

async def send_promotion(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia mensagem de promoção a cada 2 horas"""
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
    
    keyboard = [
        [InlineKeyboardButton("📲 SUPORTE", callback_data="support")],
        [InlineKeyboardButton("💱 GIFT CARDS", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia para todos os usuários
    users = db.get_all_users()
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=promotion_text,
                reply_markup=reply_markup
            )
        except TelegramError as e:
            logger.error(f"Erro ao enviar promoção para {user_id}: {e}")

# ==================== MAIN ====================

def main():
    """Função principal"""
    # Cria aplicação
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Job para enviar promoção a cada 2 horas
    app.job_queue.run_repeating(send_promotion, interval=7200, first=10)
    
    # Inicia o bot
    logger.info("Bot iniciado!")
    app.run_polling()

if __name__ == '__main__':
    main()
