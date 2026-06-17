#!/usr/bin/env python3
"""
Bot Syntek Gift Cards - VERSÃO v3
Webhook Flask + Oasyfy PIX + Entrega após pagamento
Melhorias: emojis nos comandos, preços corrigidos, suporte automático,
           texto de boas-vindas melhorado, envio promocional a cada 2h
"""

import os
import json
import time
import random
import string
import sqlite3
import threading
import base64
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
if _webhook_raw.endswith("/webhook"):
    WEBHOOK_URL = _webhook_raw[:-8]
else:
    WEBHOOK_URL = _webhook_raw.rstrip("/")
PORT = int(os.environ.get("PORT", 8080))
SUPORTE = "@SyntekOficial"
SUPORTE_URL = "https://t.me/SyntekOficial"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================================
# GIFT CARDS (preços corrigidos)
# ============================================================
GIFT_CARDS = {
    "shopee_1000": {"nome": "🎁 SHOPEE 1000", "preco": 299.90, "prefixo": "SH10"},
    "shopee_500":  {"nome": "🎁 SHOPEE 500",  "preco": 149.90, "prefixo": "SH5"},   # corrigido: era 249,90
    "shopee_300":  {"nome": "🎁 SHOPEE 300",  "preco": 99.90,  "prefixo": "SH3"},
    "ifood_1000":  {"nome": "🍔 IFOOD 1000",  "preco": 279.90, "prefixo": "IF10"},
    "ifood_500":   {"nome": "🍔 IFOOD 500",   "preco": 129.90, "prefixo": "IF5"},   # corrigido: era 229,90
    "ifood_300":   {"nome": "🍔 IFOOD 300",   "preco": 89.90,  "prefixo": "IF3"},
    "steam_300":   {"nome": "🎮 STEAM 300",   "preco": 89.00,  "prefixo": "ST3"},
    "gplay_300":   {"nome": "🎮 GOOGLE PLAY 300", "preco": 89.00, "prefixo": "GP3"},
    "teste_5":     {"nome": "🧪 TESTE R$5",        "preco": 5.00,  "prefixo": "TST"},
}

# ============================================================
# GERADOR DE DADOS DE CLIENTE ALEATÓRIOS (CPF matematicamente válido)
# ============================================================
_NOMES = [
    "Carlos Silva", "Ana Souza", "Pedro Lima", "Maria Costa",
    "João Santos", "Fernanda Oliveira", "Lucas Pereira", "Julia Rocha",
    "Rafael Alves", "Beatriz Martins", "Diego Ferreira", "Camila Gomes",
    "Thiago Ribeiro", "Larissa Carvalho", "Mateus Barbosa", "Leticia Araujo",
    "Rodrigo Nascimento", "Priscila Mendes", "Felipe Castro", "Vanessa Cardoso",
]
_DDDS = ["11", "21", "31", "41", "51", "61", "71", "81", "85", "92",
         "19", "27", "47", "48", "62", "63", "65", "66", "67", "68"]

def _gerar_cpf_valido():
    """Gera CPF com dígitos verificadores matematicamente válidos."""
    n = [random.randint(0, 9) for _ in range(9)]
    s = sum((10 - i) * n[i] for i in range(9))
    d1 = 0 if (s % 11) < 2 else 11 - (s % 11)
    n.append(d1)
    s = sum((11 - i) * n[i] for i in range(10))
    d2 = 0 if (s % 11) < 2 else 11 - (s % 11)
    n.append(d2)
    return "".join(map(str, n))

def gerar_dados_cliente():
    """Gera dados fictícios aleatórios com CPF matematicamente válido para cada cobrança."""
    nome = random.choice(_NOMES)
    ddd = random.choice(_DDDS)
    fone = f"{ddd}9{''.join([str(random.randint(0, 9)) for _ in range(8)])}"
    cpf = _gerar_cpf_valido()
    email = f"cliente{random.randint(1000, 9999)}@gmail.com"
    return {"name": nome, "document": cpf, "email": email, "phone": fone}

# ============================================================
# BANCO DE DADOS
# ============================================================
DB_PATH = "/tmp/syntek_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabela de transações
    c.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id TEXT PRIMARY KEY,
            chat_id INTEGER,
            card_key TEXT,
            valor REAL,
            status TEXT DEFAULT 'pendente',
            codigo_gift TEXT,
            oasyfy_tx_id TEXT,
            criado_em REAL
        )
    """)
    # Migrações seguras
    for col in ["oasyfy_tx_id TEXT", "pix_code TEXT", "pix_base64 TEXT"]:
        try:
            c.execute(f"ALTER TABLE transacoes ADD COLUMN {col}")
        except Exception:
            pass
    # Tabela de usuários (para envio automático de promoções)
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            chat_id INTEGER PRIMARY KEY,
            primeiro_nome TEXT,
            criado_em REAL,
            promo_enviada INTEGER DEFAULT 0
        )
    """)
    # Migração segura: coluna promo_enviada
    try:
        c.execute("ALTER TABLE usuarios ADD COLUMN promo_enviada INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()

def registrar_usuario(chat_id, primeiro_nome):
    """Registra ou atualiza um usuário no banco."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO usuarios (chat_id, primeiro_nome, criado_em) VALUES (?,?,?)",
        (chat_id, primeiro_nome, time.time())
    )
    conn.commit()
    conn.close()

def buscar_todos_usuarios():
    """Retorna lista de todos os chat_ids cadastrados."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM usuarios")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def buscar_novos_usuarios_para_promo():
    """Retorna usuários que se cadastraram há mais de 5 minutos e ainda não receberam a primeira promoção."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT chat_id FROM usuarios WHERE promo_enviada=0 AND criado_em <= ?",
        (time.time() - 300,)  # 300 segundos = 5 minutos
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def marcar_promo_enviada(chat_id):
    """Marca que o usuário já recebeu a primeira promoção."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE usuarios SET promo_enviada=1 WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

def salvar_transacao(tx_id, chat_id, card_key, valor, oasyfy_tx_id=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO transacoes (id, chat_id, card_key, valor, status, oasyfy_tx_id, criado_em) VALUES (?,?,?,?,?,?,?)",
        (tx_id, chat_id, card_key, valor, "pendente", oasyfy_tx_id, time.time())
    )
    conn.commit()
    conn.close()

def atualizar_oasyfy_tx_id(tx_id, oasyfy_tx_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE transacoes SET oasyfy_tx_id=? WHERE id=?", (oasyfy_tx_id, tx_id))
    conn.commit()
    conn.close()

def salvar_pix_data(tx_id, pix_code, pix_base64):
    """Salva o código PIX e o QR code base64 da transação."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE transacoes SET pix_code=?, pix_base64=? WHERE id=?", (pix_code, pix_base64, tx_id))
    conn.commit()
    conn.close()

def buscar_transacao(tx_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, chat_id, card_key, valor, status, codigo_gift, oasyfy_tx_id, pix_code, pix_base64 FROM transacoes WHERE id=?", (tx_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "chat_id": row[1], "card_key": row[2],
            "valor": row[3], "status": row[4], "codigo_gift": row[5],
            "oasyfy_tx_id": row[6] or "",
            "pix_code": row[7] or "",
            "pix_base64": row[8] or ""
        }
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
    c.execute(
        "SELECT id, chat_id, card_key, valor, oasyfy_tx_id FROM transacoes WHERE status='pendente' AND criado_em > ?",
        (time.time() - 3600,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

# ============================================================
# TELEGRAM API
# ============================================================
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "protect_content": True  # Bloqueia prints e encaminhamento
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"[ERRO] send_message: {e}")
        return None

def send_photo_bytes(chat_id, img_bytes, caption=None, reply_markup=None):
    """Envia foto como bytes (para QR code em base64)."""
    files = {"photo": ("qrcode.png", img_bytes, "image/png")}
    data = {
        "chat_id": chat_id,
        "parse_mode": "HTML",
        "protect_content": "true"  # Bloqueia prints e encaminhamento
    }
    if caption:
        data["caption"] = caption
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{TELEGRAM_API}/sendPhoto", files=files, data=data, timeout=15)
        return r.json()
    except Exception as e:
        print(f"[ERRO] send_photo_bytes: {e}")
        return None

def answer_callback(callback_id, text=""):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery",
                      json={"callback_query_id": callback_id, "text": text}, timeout=5)
    except Exception:
        pass

def registrar_comandos():
    """Registra os comandos /start e /suporte com emojis no BotFather via setMyCommands."""
    try:
        r = requests.post(
            f"{TELEGRAM_API}/setMyCommands",
            json={"commands": [
                {"command": "start",   "description": "🚀 Abrir loja de Gift Cards"},
                {"command": "suporte", "description": "💬 Falar com suporte"}
            ]},
            timeout=10
        )
        result = r.json()
        if result.get("ok"):
            print("✅ Comandos /start 🚀 e /suporte 💬 registrados no Telegram")
        else:
            print(f"⚠️ setMyCommands: {result.get('description')}")
    except Exception as e:
        print(f"⚠️ Erro ao registrar comandos: {e}")

# ============================================================
# OASYFY — GERAR COBRANÇA PIX
# ============================================================
def gerar_cobranca_pix(valor, descricao, tx_id):
    """Gera cobrança PIX via Oasyfy com payload correto."""
    url = "https://app.oasyfy.com/api/v1/gateway/pix/receive"
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY,
        "Content-Type": "application/json"
    }
    cliente = gerar_dados_cliente()
    payload = {
        "amount": float(valor),
        "identifier": tx_id,
        "description": descricao,
        "client": {
            "name": cliente["name"],
            "document": cliente["document"],
            "email": cliente["email"],
            "phone": cliente["phone"]
        }
    }
    try:
        print(f"[OASYFY] Gerando cobrança: R${valor:.2f} | ID: {tx_id} | Cliente: {cliente['name']}")
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"[OASYFY] Status: {r.status_code} | Resposta: {r.text[:300]}")
        if r.status_code in [200, 201]:
            return r.json()
        else:
            print(f"[OASYFY] ERRO: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"[OASYFY] Exceção: {e}")
        return None

# ============================================================
# OASYFY — VERIFICAR PAGAMENTO
# ============================================================
def verificar_pagamento_oasyfy(oasyfy_tx_id):
    """Verifica se o pagamento foi confirmado usando o transactionId da Oasyfy.
    Endpoint correto: GET /transactions?id={transactionId}
    Status de pagamento confirmado: PAID
    """
    if not oasyfy_tx_id:
        print("[OASYFY] oasyfy_tx_id vazio — não é possível verificar")
        return False
    url = "https://app.oasyfy.com/api/v1/gateway/transactions"
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY
    }
    try:
        # Parâmetro correto é 'id', não 'transactionId'
        r = requests.get(url, params={"id": oasyfy_tx_id}, headers=headers, timeout=10)
        print(f"[OASYFY] Verificação status: {r.status_code} | Resposta: {r.text[:300]}")
        if r.status_code == 200:
            data = r.json()
            # Resposta é um objeto direto (não lista)
            if isinstance(data, dict):
                status = data.get("status", "").upper()
            elif isinstance(data, list) and len(data) > 0:
                status = data[0].get("status", "").upper()
            else:
                print(f"[OASYFY] Resposta inesperada: {data}")
                return False
            print(f"[OASYFY] Status pagamento {oasyfy_tx_id}: {status}")
            return status in ["PAID", "APPROVED", "COMPLETED", "CONFIRMED", "COMPLETE"]
        return False
    except Exception as e:
        print(f"[OASYFY] Erro verificação: {e}")
        return False

# ============================================================
# GERADOR DE CÓDIGO GIFT CARD — FORMATO REAL POR PRODUTO
# ============================================================
import string as _string

def gerar_codigo(prefixo):
    """Gera código no formato real de cada gift card com base no prefixo."""
    letras = _string.ascii_uppercase
    digitos = _string.digits
    alfanum = letras + digitos

    def bloco(n, chars=alfanum):
        return ''.join(random.choices(chars, k=n))

    # Shopee: 16 dígitos numéricos
    if prefixo in ("SH10", "SH5", "SH3"):
        return bloco(16, digitos)

    # iFood: XXXX-XXXX-XXXX-XXXX (letras maiúsculas + números)
    elif prefixo in ("IF10", "IF5", "IF3"):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

    # Google Play: XXXX-XXXX-XXXX-XXXX (letras maiúsculas + números)
    elif prefixo in ("GP3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

    # Steam: XXXXX-XXXXX-XXXXX (letras maiúsculas + números)
    elif prefixo in ("ST3",):
        return f"{bloco(5)}-{bloco(5)}-{bloco(5)}"

    # Roblox: XXXX-XXXX-XXXX-XXXX
    elif prefixo in ("RB3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

    # Casas Bahia: 16 dígitos numéricos
    elif prefixo in ("CB3",):
        return bloco(16, digitos)

    # Zé Delivery: XXXX-XXXX-XXXX-XXXX
    elif prefixo in ("ZD3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

    # Airbnb: 10 letras+números
    elif prefixo in ("AB3",):
        return bloco(10)

    # Apple Store: XXXX-XXXX-XXXX-XXXX (letras maiúsculas + números)
    elif prefixo in ("AP3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

    # Uber: XXXXXXXXXX (10 letras+números)
    elif prefixo in ("UB3",):
        return bloco(10)

    # Teste / genérico
    else:
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

# ============================================================
# TECLADO PADRÃO DE GIFT CARDS
# ============================================================
def teclado_gift_cards():
    """Retorna o inline keyboard com todos os gift cards e botão de suporte."""
    return {
        "inline_keyboard": [
            [{"text": "🎁 SHOPEE 1000 - R$ 299,90", "callback_data": "comprar_shopee_1000"}],
            [{"text": "🎁 SHOPEE 500 - R$ 149,90",  "callback_data": "comprar_shopee_500"}],
            [{"text": "🎁 SHOPEE 300 - R$ 99,90",   "callback_data": "comprar_shopee_300"}],
            [{"text": "🍔 IFOOD 1000 - R$ 279,90",  "callback_data": "comprar_ifood_1000"}],
            [{"text": "🍔 IFOOD 500 - R$ 129,90",   "callback_data": "comprar_ifood_500"}],
            [{"text": "🍔 IFOOD 300 - R$ 89,90",    "callback_data": "comprar_ifood_300"}],
            [{"text": "🎮 STEAM 300 - R$ 89,00",    "callback_data": "comprar_steam_300"}],
            [{"text": "🎮 GOOGLE PLAY 300 - R$ 89,00", "callback_data": "comprar_gplay_300"}],
            [{"text": "🧪 TESTE R$5 (apenas para teste)", "callback_data": "comprar_teste_5"}],
            [{"text": "📲 Suporte", "url": SUPORTE_URL}],
        ]
    }

# ============================================================
# HANDLERS DO BOT
# ============================================================
def handle_start(chat_id, user_name):
    print(f"[BOT] /start de {user_name} ({chat_id})")
    registrar_usuario(chat_id, user_name)
    texto = (
        f"👋 Olá, <b>{user_name}</b>! Bem-vindo à <b>Syntek Gift Cards</b>! 🏆\n\n"
        "🎁 Escolha um Gift Card abaixo:\n"
        "💳 Pagamento via <b>PIX</b> — entrega automática após confirmação!\n\n"
        "✅ <b>APÓS A COMPRA, VOCÊ RECEBERÁ O CÓDIGO DO GIFT CARD</b>\n"
        "✅ <b>BASICAMENTE É SÓ ADICIONAR E USAR O SALDO.</b>\n\n"
        "⚠️ PARA OUTROS GIFT CARDS CONTATE O SUPORTE."
    )
    send_message(chat_id, texto, reply_markup=teclado_gift_cards())

def handle_suporte(chat_id):
    """Envia mensagem de suporte com redirecionamento automático para o chat."""
    texto = (
        f"💬 <b>SUPORTE SYNTEK</b>\n\n"
        f"Clique abaixo para falar diretamente com nosso suporte:\n"
        f"👉 {SUPORTE}"
    )
    teclado = {
        "inline_keyboard": [
            [{"text": "💬 Falar com Suporte Agora", "url": SUPORTE_URL}],
            [{"text": "🔄 Voltar ao Menu", "callback_data": "menu"}],
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
    salvar_transacao(tx_id, chat_id, card_key, card["preco"])

    cobranca = gerar_cobranca_pix(card["preco"], f"Gift Card {card['nome']}", tx_id)

    # O teclado será montado depois que tivermos o pix_code
    # pois o botão copy_text precisa do código PIX real
    teclado_sem_pix = {
        "inline_keyboard": [
            [{"text": "📷 Ver QR Code", "callback_data": f"ver_qr_{tx_id}"}],
            [{"text": "✅ Já paguei! Verificar", "callback_data": f"verificar_{tx_id}"}],
            [{"text": "🔄 Voltar ao Menu", "callback_data": "menu"}],
            [{"text": "💬 Suporte", "url": SUPORTE_URL}],
        ]
    }

    if cobranca:
        pix_code     = cobranca.get("pix", {}).get("code", "")
        pix_base64   = cobranca.get("pix", {}).get("base64", "")
        oasyfy_tx_id = cobranca.get("transactionId", "")

        if oasyfy_tx_id:
            atualizar_oasyfy_tx_id(tx_id, oasyfy_tx_id)
            print(f"[OASYFY] transactionId salvo: {oasyfy_tx_id}")
        # Salvar código PIX e base64 no banco para uso posterior (copiar/ver QR)
        if pix_code or pix_base64:
            salvar_pix_data(tx_id, pix_code, pix_base64)

        # Montar teclado com botão copy_text nativo do Telegram (copia sem enviar mensagem)
        if pix_code:
            teclado = {
                "inline_keyboard": [
                    [{"text": "📋 Copiar Código PIX", "copy_text": {"text": pix_code}}],
                    [{"text": "📷 Ver QR Code", "callback_data": f"ver_qr_{tx_id}"}],
                    [{"text": "✅ Já paguei! Verificar", "callback_data": f"verificar_{tx_id}"}],
                    [{"text": "🔄 Voltar ao Menu", "callback_data": "menu"}],
                    [{"text": "💬 Suporte", "url": SUPORTE_URL}],
                ]
            }
        else:
            teclado = teclado_sem_pix

        caption = (
            f"📷 <b>Escaneie o QR code para Pagar:</b>\n\n"
            f"🎁 Produto: <b>{card['nome']}</b>\n"
            f"💰 Valor: <b>R$ {card['preco']:.2f}</b>\n\n"
            f"✅ <b>Como realizar o pagamento:</b>\n"
            f"1. Abra o aplicativo do seu banco.\n"
            f"2. Selecione a opção <b>\"Pagar\"</b> ou <b>\"PIX\"</b>.\n"
            f"3. Escolha <b>\"PIX Copia e Cola\"</b>.\n"
            f"4. Cole a chave que está abaixo e finalize o pagamento com segurança.\n\n"
            f"📋 <b>Copie o código abaixo:</b>\n"
            f"<code>{pix_code if pix_code else 'Aguardando...'}</code>\n\n"
            f"⏳ Após o pagamento, o código do Gift Card será entregue automaticamente!\n"
            f"🔄 ID: <code>{tx_id}</code>"
        )

        enviado = False
        if pix_base64:
            try:
                b64_data = pix_base64.split(",")[-1]
                img_bytes = base64.b64decode(b64_data)
                result = send_photo_bytes(chat_id, img_bytes, caption=caption, reply_markup=teclado)
                if result and result.get("ok"):
                    enviado = True
                    print(f"[BOT] QR code enviado como imagem para chat {chat_id}")
            except Exception as e:
                print(f"[BOT] Erro ao decodificar base64: {e}")

        if not enviado:
            send_message(chat_id, caption, reply_markup=teclado)
    else:
        texto = (
            f"⚠️ <b>Erro ao gerar PIX</b>\n\n"
            f"Não foi possível gerar a cobrança agora.\n"
            f"Entre em contato com o suporte: {SUPORTE}"
        )
        teclado_erro = {
            "inline_keyboard": [
                [{"text": "🔄 Tentar Novamente", "callback_data": f"comprar_{card_key}"}],
                [{"text": "💬 Suporte", "url": SUPORTE_URL}],
            ]
        }
        send_message(chat_id, texto, reply_markup=teclado_erro)

def handle_verificar(chat_id, tx_id, callback_id):
    answer_callback(callback_id, "🔍 Verificando pagamento...")
    tx = buscar_transacao(tx_id)
    if not tx:
        send_message(chat_id, "❌ Transação não encontrada.")
        return
    if tx["status"] == "pago":
        send_message(chat_id, f"✅ Pagamento já confirmado!\n\nSeu código: <code>{tx['codigo_gift']}</code>")
        return

    oasyfy_tx_id = tx.get("oasyfy_tx_id", "")
    pago = verificar_pagamento_oasyfy(oasyfy_tx_id)

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
                [{"text": "💬 Suporte", "url": SUPORTE_URL}],
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
                [{"text": "💬 Suporte", "url": SUPORTE_URL}],
            ]
        }
        send_message(chat_id, texto, reply_markup=teclado)

# ============================================================
# VERIFICADOR AUTOMÁTICO DE PAGAMENTOS
# ============================================================
def verificar_pagamentos_loop():
    """Verifica pagamentos pendentes a cada 30 segundos."""
    while True:
        try:
            pendentes = buscar_pendentes()
            for tx_id, chat_id, card_key, valor, oasyfy_tx_id in pendentes:
                if not oasyfy_tx_id:
                    continue
                pago = verificar_pagamento_oasyfy(oasyfy_tx_id)
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
                            [{"text": "💬 Suporte", "url": SUPORTE_URL}],
                        ]
                    }
                    send_message(chat_id, texto, reply_markup=teclado)
                    print(f"[AUTO] Pagamento confirmado e código entregue: {tx_id}")
        except Exception as e:
            print(f"[AUTO] Erro verificação pagamentos: {e}")
        time.sleep(30)

# ============================================================
# ENVIO AUTOMÁTICO DE PROMOÇÃO A CADA 2 HORAS
# ============================================================
INTERVALO_PROMO = 3600  # segundos entre cada envio recorrente (3600 = 1 hora)
PRIMEIRO_ENVIO_DELAY = 300  # segundos após cadastro para o primeiro envio (300 = 5 minutos)

def _texto_e_teclado_promo():
    """Retorna o texto e teclado da mensagem promocional."""
    texto = (
        "✅ <b>PROMOÇÃO</b>\n\n"
        "🔹SHOPEE  🔹IFOOD  🔹GOOGLE PLAY\n"
        "🔹CASAS BAHIA  🔹ROBLOX  🔹STEAM\n"
        "🔹ZÉ DELIVERY  🔹AIRBNB\n"
        "🔹APPLE STORE  🔹UBER\n\n"
        "Outros Gift Cards? Chame o Suporte.\n\n"
        "❖ <b>1000 DE SALDO</b> — R$ 299,90\n"
        "❖ <b>500 DE SALDO</b> — R$ 139,90\n"
        "❖ <b>300 DE SALDO</b> — R$ 89,90\n\n"
        "⚠️ É SÓ ADICIONAR E REALIZAR AS COMPRAS, NÃO TEM SEGREDO. ✅🦅🚀"
    )
    teclado = {
        "inline_keyboard": [
            [{"text": "🚀 /GIFT CARDS — Ver todos", "callback_data": "menu"}],
            [{"text": "📲 Suporte", "url": SUPORTE_URL}],
        ]
    }
    return texto, teclado

def enviar_promocao_loop():
    """Loop principal de promoções:
    - Verifica a cada 60s se há novos usuários que esperaram 5 minutos (primeiro envio)
    - Envia para todos os usuários a cada 1 hora (envios recorrentes)
    """
    ultimo_envio_geral = 0  # timestamp do último envio para todos

    while True:
        try:
            agora = time.time()

            # --- PRIMEIRO ENVIO: novos usuários que aguardaram 5 minutos ---
            novos = buscar_novos_usuarios_para_promo()
            if novos:
                texto, teclado = _texto_e_teclado_promo()
                print(f"[PROMO] Primeiro envio para {len(novos)} novo(s) usuário(s)...")
                for chat_id in novos:
                    result = send_message(chat_id, texto, reply_markup=teclado)
                    if result and result.get("ok"):
                        marcar_promo_enviada(chat_id)
                        print(f"[PROMO] Primeiro envio OK: {chat_id}")
                    else:
                        print(f"[PROMO] Erro primeiro envio: {chat_id}")
                    time.sleep(0.05)

            # --- ENVIO RECORRENTE: todos os usuários a cada 1 hora ---
            if agora - ultimo_envio_geral >= INTERVALO_PROMO:
                usuarios = buscar_todos_usuarios()
                if usuarios:
                    texto, teclado = _texto_e_teclado_promo()
                    print(f"[PROMO] Envio recorrente para {len(usuarios)} usuários...")
                    enviados = 0
                    erros = 0
                    for chat_id in usuarios:
                        result = send_message(chat_id, texto, reply_markup=teclado)
                        if result and result.get("ok"):
                            enviados += 1
                        else:
                            erros += 1
                        time.sleep(0.05)
                    print(f"[PROMO] Recorrente: {enviados} enviados | {erros} erros")
                    ultimo_envio_geral = agora
                else:
                    print("[PROMO] Nenhum usuário cadastrado ainda.")
                    ultimo_envio_geral = agora  # evitar spam de log

        except Exception as e:
            print(f"[PROMO] Erro no loop: {e}")

        time.sleep(60)  # verificar a cada 60 segundos

# ============================================================
# FLASK APP - WEBHOOK
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Syntek Gift Cards", "version": "v3"})

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        if not update:
            return jsonify({"ok": True})
        print(f"[WEBHOOK] Update recebido: {json.dumps(update)[:200]}")
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user = msg.get("from", {})
            user_name = user.get("first_name", "Cliente")
            text = msg.get("text", "")
            if text.startswith("/start"):
                handle_start(chat_id, user_name)
            elif text.startswith("/suporte"):
                registrar_usuario(chat_id, user_name)
                handle_suporte(chat_id)
            else:
                # Qualquer outra mensagem: registrar usuário e mostrar menu
                registrar_usuario(chat_id, user_name)
        elif "callback_query" in update:
            cb = update["callback_query"]
            chat_id = cb["message"]["chat"]["id"]
            callback_id = cb["id"]
            data = cb.get("data", "")
            user_name = cb.get("from", {}).get("first_name", "Cliente")
            print(f"[WEBHOOK] Callback: {data} | Chat: {chat_id}")
            registrar_usuario(chat_id, user_name)
            if data == "menu":
                handle_start(chat_id, user_name)
            elif data.startswith("comprar_"):
                card_key = data.replace("comprar_", "")
                handle_comprar(chat_id, card_key, callback_id)
            elif data.startswith("verificar_"):
                tx_id = data.replace("verificar_", "")
                handle_verificar(chat_id, tx_id, callback_id)
            elif data.startswith("copiar_pix_"):
                tx_id = data.replace("copiar_pix_", "")
                tx = buscar_transacao(tx_id)
                if tx and tx.get("pix_code"):
                    # Envia o código PIX SEM protect_content para que o cliente consiga tocar e copiar
                    try:
                        payload_pix = {
                            "chat_id": chat_id,
                            "text": f"<code>{tx['pix_code']}</code>",
                            "parse_mode": "HTML",
                            "protect_content": False  # Precisa estar False para permitir copia
                        }
                        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload_pix, timeout=10)
                        requests.post(
                            f"{TELEGRAM_API}/answerCallbackQuery",
                            json={"callback_query_id": callback_id, "text": "📋 Toque no código para copiar!"},
                            timeout=5
                        )
                    except Exception as e:
                        print(f"[BOT] Erro ao enviar código PIX: {e}")
                else:
                    try:
                        requests.post(
                            f"{TELEGRAM_API}/answerCallbackQuery",
                            json={"callback_query_id": callback_id, "text": "❌ Código PIX não encontrado.", "show_alert": True},
                            timeout=5
                        )
                    except Exception:
                        pass
            elif data.startswith("ver_qr_"):
                tx_id = data.replace("ver_qr_", "")
                answer_callback(callback_id, "📷 Carregando QR Code...")
                tx = buscar_transacao(tx_id)
                if tx and tx.get("pix_base64"):
                    try:
                        b64_data = tx["pix_base64"].split(",")[-1]
                        img_bytes = base64.b64decode(b64_data)
                        # Botão copy_text nativo se tiver o código PIX
                        if tx.get("pix_code"):
                            teclado_qr = {
                                "inline_keyboard": [
                                    [{"text": "📋 Copiar Código PIX", "copy_text": {"text": tx["pix_code"]}}],
                                    [{"text": "✅ Já paguei! Verificar", "callback_data": f"verificar_{tx_id}"}],
                                    [{"text": "💬 Suporte", "url": SUPORTE_URL}],
                                ]
                            }
                        else:
                            teclado_qr = {
                                "inline_keyboard": [
                                    [{"text": "✅ Já paguei! Verificar", "callback_data": f"verificar_{tx_id}"}],
                                    [{"text": "💬 Suporte", "url": SUPORTE_URL}],
                                ]
                            }
                        send_photo_bytes(chat_id, img_bytes,
                            caption=f"📷 <b>QR Code para pagamento</b>\n📋 Toque em <b>Copiar Código PIX</b> abaixo para pagar via Copia e Cola.",
                            reply_markup=teclado_qr
                        )
                    except Exception as e:
                        print(f"[BOT] Erro ao enviar QR: {e}")
                        send_message(chat_id, "❌ Erro ao carregar QR Code. Use o código Copia e Cola.")
                else:
                    send_message(chat_id, "❌ QR Code não disponível. Gere uma nova cobrança.")
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
    print("🤖 Bot Syntek Gift Cards - v3")
    print(f"🔑 Token: {BOT_TOKEN[:20]}...")
    print(f"🌐 Webhook: {WEBHOOK_URL}/webhook")
    print(f"💳 Oasyfy: {OASYFY_PUBLIC_KEY[:20]}...")
    print("=" * 50)

    init_db()
    print("✅ Banco de dados inicializado")

    # Configurar webhook do Telegram
    try:
        r = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": f"{WEBHOOK_URL}/webhook", "drop_pending_updates": True},
            timeout=10
        )
        result = r.json()
        if result.get("ok"):
            print(f"✅ Webhook configurado: {WEBHOOK_URL}/webhook")
        else:
            print(f"⚠️ Webhook: {result.get('description')}")
    except Exception as e:
        print(f"⚠️ Erro ao configurar webhook: {e}")

    # Registrar comandos /start 🚀 e /suporte 💬 no Telegram
    registrar_comandos()

    # Iniciar verificador automático de pagamentos (thread)
    t1 = threading.Thread(target=verificar_pagamentos_loop, daemon=True)
    t1.start()
    print("✅ Verificador automático de pagamentos iniciado (30s)")

    # Iniciar loop de envio promocional a cada 2 horas (thread)
    t2 = threading.Thread(target=enviar_promocao_loop, daemon=True)
    t2.start()
    print("✅ Loop de promoção automática iniciado (a cada 2h)")

    print(f"🚀 Flask iniciando na porta {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
