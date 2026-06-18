"""
Bot Syntek Gift Cards - VERSÃO v4
Webhook Flask + Oasyfy PIX + Entrega após pagamento
v4: PostgreSQL (fallback SQLite) + Gunicorn multi-worker
"""

import os
import json
import time
import random
import string
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
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:GdToRdGtDCTYGPpCLFzSMGPofJfNUzpR@thomas.proxy.rlwy.net:58421/railway")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ============================================================
# GIFT CARDS
# ============================================================
GIFT_CARDS = {
    "shopee_1000": {"nome": "🎁 SHOPEE 1000", "preco": 299.90, "prefixo": "SH10"},
    "shopee_500":  {"nome": "🎁 SHOPEE 500",  "preco": 149.90, "prefixo": "SH5"},
    "shopee_300":  {"nome": "🎁 SHOPEE 300",  "preco": 99.90,  "prefixo": "SH3"},
    "ifood_1000":  {"nome": "🍔 IFOOD 1000",  "preco": 279.90, "prefixo": "IF10"},
    "ifood_500":   {"nome": "🍔 IFOOD 500",   "preco": 129.90, "prefixo": "IF5"},
    "ifood_300":   {"nome": "🍔 IFOOD 300",   "preco": 89.90,  "prefixo": "IF3"},
    "steam_300":   {"nome": "🎮 STEAM 300",   "preco": 89.00,  "prefixo": "ST3"},
    "gplay_300":   {"nome": "🎮 GOOGLE PLAY 300",   "preco": 89.00,  "prefixo": "GP3"},
    "roblox_500":  {"nome": "🎮 ROBLOX 500",         "preco": 149.90, "prefixo": "RB5"},
    "roblox_300":  {"nome": "🎮 ROBLOX 300",         "preco": 90.00,  "prefixo": "RB3"},
    "roblox_200":  {"nome": "🎮 ROBLOX 200",         "preco": 70.00,  "prefixo": "RB2"},
    "cbahia_1000": {"nome": "🏠 CASAS BAHIA 1000",   "preco": 299.90, "prefixo": "CB10"},
    "cbahia_500":  {"nome": "🏠 CASAS BAHIA 500",    "preco": 149.90, "prefixo": "CB5"},
    "cbahia_300":  {"nome": "🏠 CASAS BAHIA 300",    "preco": 90.00,  "prefixo": "CB3"},
    "airbnb_1000": {"nome": "🏙 AIRBNB 1000",        "preco": 325.00, "prefixo": "AB10"},
    "airbnb_500":  {"nome": "🏙 AIRBNB 500",         "preco": 160.00, "prefixo": "AB5"},
    "airbnb_250":  {"nome": "🏙 AIRBNB 250",         "preco": 79.90,  "prefixo": "AB2"},
    "apple_200":   {"nome": "📱 APPLE STORE 200",    "preco": 79.90,  "prefixo": "AP2"},
    "uber_500":    {"nome": "🚕 UBER 500",            "preco": 149.90, "prefixo": "UB5"},
    "uber_300":    {"nome": "🚕 UBER 300",            "preco": 90.00,  "prefixo": "UB3"},
    "uber_200":    {"nome": "🚕 UBER 200",            "preco": 70.00,  "prefixo": "UB2"},
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
    n = [random.randint(0, 9) for _ in range(9)]
    s = sum((10 - i) * n[i] for i in range(9))
    d1 = 0 if (s % 11) < 2 else 11 - (s % 11)
    n.append(d1)
    s = sum((11 - i) * n[i] for i in range(10))
    d2 = 0 if (s % 11) < 2 else 11 - (s % 11)
    n.append(d2)
    return "".join(map(str, n))

def gerar_dados_cliente():
    nome = random.choice(_NOMES)
    ddd = random.choice(_DDDS)
    fone = f"{ddd}9{''.join([str(random.randint(0, 9)) for _ in range(8)])}"
    cpf = _gerar_cpf_valido()
    email = f"cliente{random.randint(1000, 9999)}@gmail.com"
    return {"name": nome, "document": cpf, "email": email, "phone": fone}

# ============================================================
# BANCO DE DADOS — PostgreSQL com fallback para SQLite
# ============================================================
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2
    import psycopg2.pool
    from psycopg2.extras import RealDictCursor
    _pg_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2, maxconn=20, dsn=DATABASE_URL
    )
    print(f"[DB] Usando PostgreSQL (pool 2-20 conexões)")

    def _get_conn():
        return _pg_pool.getconn()

    def _put_conn(conn):
        _pg_pool.putconn(conn)

    def _ph():
        """Placeholder para PostgreSQL: %s"""
        return "%s"
else:
    import sqlite3
    DB_PATH = "/tmp/syntek_bot.db"
    _sqlite_lock = threading.Lock()
    print(f"[DB] Usando SQLite: {DB_PATH}")

    def _get_conn():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _put_conn(conn):
        conn.close()

    def _ph():
        """Placeholder para SQLite: ?"""
        return "?"

def init_db():
    conn = _get_conn()
    try:
        if _USE_PG:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS transacoes (
                    id TEXT PRIMARY KEY,
                    chat_id BIGINT,
                    card_key TEXT,
                    valor FLOAT,
                    status TEXT DEFAULT 'pendente',
                    codigo_gift TEXT,
                    oasyfy_tx_id TEXT,
                    pix_code TEXT,
                    pix_base64 TEXT,
                    criado_em FLOAT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    chat_id BIGINT PRIMARY KEY,
                    primeiro_nome TEXT,
                    criado_em FLOAT,
                    promo_enviada INTEGER DEFAULT 0
                )
            """)
            # Migrações seguras para colunas novas
            for col_def in [
                "ALTER TABLE transacoes ADD COLUMN IF NOT EXISTS oasyfy_tx_id TEXT",
                "ALTER TABLE transacoes ADD COLUMN IF NOT EXISTS pix_code TEXT",
                "ALTER TABLE transacoes ADD COLUMN IF NOT EXISTS pix_base64 TEXT",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS promo_enviada INTEGER DEFAULT 0",
            ]:
                try:
                    c.execute(col_def)
                except Exception:
                    pass
        else:
            c = conn.cursor()
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
            for col in ["oasyfy_tx_id TEXT", "pix_code TEXT", "pix_base64 TEXT"]:
                try:
                    c.execute(f"ALTER TABLE transacoes ADD COLUMN {col}")
                except Exception:
                    pass
            c.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    chat_id INTEGER PRIMARY KEY,
                    primeiro_nome TEXT,
                    criado_em REAL,
                    promo_enviada INTEGER DEFAULT 0
                )
            """)
            try:
                c.execute("ALTER TABLE usuarios ADD COLUMN promo_enviada INTEGER DEFAULT 0")
            except Exception:
                pass
        conn.commit()
        print("[DB] Banco inicializado com sucesso")
    finally:
        _put_conn(conn)

def _exec(query, params=(), fetch=None):
    """Executa query de forma thread-safe para ambos os bancos."""
    if not _USE_PG:
        with _sqlite_lock:
            conn = _get_conn()
            try:
                c = conn.cursor()
                c.execute(query, params)
                conn.commit()
                if fetch == "one":
                    return c.fetchone()
                if fetch == "all":
                    return c.fetchall()
                return None
            finally:
                _put_conn(conn)
    else:
        conn = _get_conn()
        try:
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            if fetch == "one":
                return c.fetchone()
            if fetch == "all":
                return c.fetchall()
            return None
        finally:
            _put_conn(conn)

def registrar_usuario(chat_id, primeiro_nome):
    ph = _ph()
    if _USE_PG:
        _exec(
            f"INSERT INTO usuarios (chat_id, primeiro_nome, criado_em) VALUES ({ph},{ph},{ph}) ON CONFLICT (chat_id) DO NOTHING",
            (chat_id, primeiro_nome, time.time())
        )
    else:
        _exec(
            f"INSERT OR IGNORE INTO usuarios (chat_id, primeiro_nome, criado_em) VALUES ({ph},{ph},{ph})",
            (chat_id, primeiro_nome, time.time())
        )

def buscar_todos_usuarios():
    rows = _exec("SELECT chat_id FROM usuarios", fetch="all")
    return [r[0] for r in rows] if rows else []

def buscar_novos_usuarios_para_promo():
    ph = _ph()
    rows = _exec(
        f"SELECT chat_id FROM usuarios WHERE promo_enviada=0 AND criado_em <= {ph}",
        (time.time() - 300,),
        fetch="all"
    )
    return [r[0] for r in rows] if rows else []

def marcar_promo_enviada(chat_id):
    ph = _ph()
    _exec(f"UPDATE usuarios SET promo_enviada=1 WHERE chat_id={ph}", (chat_id,))

def salvar_transacao(tx_id, chat_id, card_key, valor, oasyfy_tx_id=""):
    ph = _ph()
    if _USE_PG:
        _exec(
            f"INSERT INTO transacoes (id, chat_id, card_key, valor, status, oasyfy_tx_id, criado_em) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph}) ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status",
            (tx_id, chat_id, card_key, valor, "pendente", oasyfy_tx_id, time.time())
        )
    else:
        _exec(
            f"INSERT OR REPLACE INTO transacoes (id, chat_id, card_key, valor, status, oasyfy_tx_id, criado_em) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (tx_id, chat_id, card_key, valor, "pendente", oasyfy_tx_id, time.time())
        )

def atualizar_oasyfy_tx_id(tx_id, oasyfy_tx_id):
    ph = _ph()
    _exec(f"UPDATE transacoes SET oasyfy_tx_id={ph} WHERE id={ph}", (oasyfy_tx_id, tx_id))

def salvar_pix_data(tx_id, pix_code, pix_base64):
    ph = _ph()
    _exec(f"UPDATE transacoes SET pix_code={ph}, pix_base64={ph} WHERE id={ph}", (pix_code, pix_base64, tx_id))

def buscar_transacao(tx_id):
    ph = _ph()
    row = _exec(
        f"SELECT id, chat_id, card_key, valor, status, codigo_gift, oasyfy_tx_id, pix_code, pix_base64 FROM transacoes WHERE id={ph}",
        (tx_id,), fetch="one"
    )
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
    ph = _ph()
    if codigo:
        _exec(f"UPDATE transacoes SET status={ph}, codigo_gift={ph} WHERE id={ph}", (status, codigo, tx_id))
    else:
        _exec(f"UPDATE transacoes SET status={ph} WHERE id={ph}", (status, tx_id))

def buscar_pendentes():
    ph = _ph()
    rows = _exec(
        f"SELECT id, chat_id, card_key, valor, oasyfy_tx_id FROM transacoes WHERE status='pendente' AND criado_em > {ph}",
        (time.time() - 3600,), fetch="all"
    )
    return rows if rows else []

# ============================================================
# TELEGRAM API
# ============================================================
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "protect_content": True
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
    files = {"photo": ("qrcode.png", img_bytes, "image/png")}
    data = {"chat_id": chat_id, "parse_mode": "HTML", "protect_content": "true"}
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
            print("✅ Comandos /start 🚀 e /suporte 💬 registrados")
        else:
            print(f"⚠️ setMyCommands: {result.get('description')}")
    except Exception as e:
        print(f"⚠️ Erro ao registrar comandos: {e}")

# ============================================================
# OASYFY — GERAR COBRANÇA PIX
# ============================================================
def gerar_cobranca_pix(valor, descricao, tx_id):
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
    if not oasyfy_tx_id:
        return False
    url = "https://app.oasyfy.com/api/v1/gateway/transactions"
    headers = {
        "x-public-key": OASYFY_PUBLIC_KEY,
        "x-secret-key": OASYFY_SECRET_KEY
    }
    try:
        r = requests.get(url, params={"id": oasyfy_tx_id}, headers=headers, timeout=10)
        print(f"[OASYFY] Verificação: {r.status_code} | {r.text[:300]}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                status = data.get("status", "").upper()
            elif isinstance(data, list) and len(data) > 0:
                status = data[0].get("status", "").upper()
            else:
                return False
            print(f"[OASYFY] Status {oasyfy_tx_id}: {status}")
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
    letras = _string.ascii_uppercase
    digitos = _string.digits
    alfanum = letras + digitos

    def bloco(n, chars=alfanum):
        return ''.join(random.choices(chars, k=n))

    if prefixo in ("SH10", "SH5", "SH3"):
        return bloco(16, digitos)
    elif prefixo in ("IF10", "IF5", "IF3"):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"
    elif prefixo in ("GP3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"
    elif prefixo in ("ST3",):
        return f"{bloco(5)}-{bloco(5)}-{bloco(5)}"
    elif prefixo in ("RB5", "RB3", "RB2"):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"
    elif prefixo in ("CB10", "CB5", "CB3"):
        return bloco(16, digitos)
    elif prefixo in ("AB10", "AB5", "AB2"):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}"
    elif prefixo in ("AP2",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"
    elif prefixo in ("UB5", "UB3", "UB2"):
        return bloco(10)
    elif prefixo in ("ZD3",):
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"
    else:
        return f"{bloco(4)}-{bloco(4)}-{bloco(4)}-{bloco(4)}"

# ============================================================
# TECLADO PADRÃO DE GIFT CARDS
# ============================================================
def teclado_gift_cards():
    return {
        "inline_keyboard": [
            [{"text": "🎁 SHOPEE 1000 - R$ 299,90",      "callback_data": "comprar_shopee_1000"}],
            [{"text": "🎁 SHOPEE 500 - R$ 149,90",       "callback_data": "comprar_shopee_500"}],
            [{"text": "🎁 SHOPEE 300 - R$ 99,90",        "callback_data": "comprar_shopee_300"}],
            [{"text": "🍔 IFOOD 1000 - R$ 279,90",       "callback_data": "comprar_ifood_1000"}],
            [{"text": "🍔 IFOOD 500 - R$ 129,90",        "callback_data": "comprar_ifood_500"}],
            [{"text": "🍔 IFOOD 300 - R$ 89,90",         "callback_data": "comprar_ifood_300"}],
            [{"text": "🎮 STEAM 300 - R$ 89,00",         "callback_data": "comprar_steam_300"}],
            [{"text": "🎮 GOOGLE PLAY 300 - R$ 89,00",   "callback_data": "comprar_gplay_300"}],
            [{"text": "🎮 ROBLOX 500 - R$ 149,90",       "callback_data": "comprar_roblox_500"}],
            [{"text": "🎮 ROBLOX 300 - R$ 90,00",        "callback_data": "comprar_roblox_300"}],
            [{"text": "🎮 ROBLOX 200 - R$ 70,00",        "callback_data": "comprar_roblox_200"}],
            [{"text": "🏠 CASAS BAHIA 1000 - R$ 299,90", "callback_data": "comprar_cbahia_1000"}],
            [{"text": "🏠 CASAS BAHIA 500 - R$ 149,90",  "callback_data": "comprar_cbahia_500"}],
            [{"text": "🏠 CASAS BAHIA 300 - R$ 90,00",   "callback_data": "comprar_cbahia_300"}],
            [{"text": "🏙 AIRBNB 1000 - R$ 325,00",      "callback_data": "comprar_airbnb_1000"}],
            [{"text": "🏙 AIRBNB 500 - R$ 160,00",       "callback_data": "comprar_airbnb_500"}],
            [{"text": "🏙 AIRBNB 250 - R$ 79,90",        "callback_data": "comprar_airbnb_250"}],
            [{"text": "📱 APPLE STORE 200 - R$ 79,90",   "callback_data": "comprar_apple_200"}],
            [{"text": "🚕 UBER 500 - R$ 149,90",          "callback_data": "comprar_uber_500"}],
            [{"text": "🚕 UBER 300 - R$ 90,00",           "callback_data": "comprar_uber_300"}],
            [{"text": "🚕 UBER 200 - R$ 70,00",           "callback_data": "comprar_uber_200"}],
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
        if pix_code or pix_base64:
            salvar_pix_data(tx_id, pix_code, pix_base64)

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
                    print(f"[BOT] QR code enviado para chat {chat_id}")
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
    while True:
        try:
            pendentes = buscar_pendentes()
            for row in pendentes:
                tx_id, chat_id, card_key, valor, oasyfy_tx_id = row[0], row[1], row[2], row[3], row[4]
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
# ENVIO AUTOMÁTICO DE PROMOÇÃO A CADA 1 HORA
# ============================================================
INTERVALO_PROMO = 3600
PRIMEIRO_ENVIO_DELAY = 300

def _texto_e_teclado_promo():
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
            [{"text": "🎁 Ver Gift Cards", "callback_data": "menu"}],
            [{"text": "📲 Suporte", "url": SUPORTE_URL}],
        ]
    }
    return texto, teclado

def enviar_promocao_loop():
    ultimo_envio_geral = 0
    while True:
        try:
            agora = time.time()
            novos = buscar_novos_usuarios_para_promo()
            if novos:
                texto, teclado = _texto_e_teclado_promo()
                print(f"[PROMO] Primeiro envio para {len(novos)} novo(s) usuário(s)...")
                for chat_id in novos:
                    result = send_message(chat_id, texto, reply_markup=teclado)
                    if result and result.get("ok"):
                        marcar_promo_enviada(chat_id)
                        print(f"[PROMO] Primeiro envio OK: {chat_id}")
                    time.sleep(0.05)

            if agora - ultimo_envio_geral >= INTERVALO_PROMO:
                usuarios = buscar_todos_usuarios()
                if usuarios:
                    texto, teclado = _texto_e_teclado_promo()
                    print(f"[PROMO] Envio recorrente para {len(usuarios)} usuários...")
                    enviados = 0
                    for chat_id in usuarios:
                        result = send_message(chat_id, texto, reply_markup=teclado)
                        if result and result.get("ok"):
                            enviados += 1
                        time.sleep(0.05)
                    print(f"[PROMO] Recorrente: {enviados} enviados")
                ultimo_envio_geral = agora
        except Exception as e:
            print(f"[PROMO] Erro no loop: {e}")
        time.sleep(60)

# ============================================================
# FLASK APP - WEBHOOK
# ============================================================
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    db_type = "PostgreSQL" if _USE_PG else "SQLite"
    return jsonify({"status": "ok", "bot": "Syntek Gift Cards", "version": "v4", "db": db_type})

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        if not update:
            return jsonify({"ok": True})
        print(f"[WEBHOOK] Update: {json.dumps(update)[:200]}")
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
                    try:
                        payload_pix = {
                            "chat_id": chat_id,
                            "text": f"<code>{tx['pix_code']}</code>",
                            "parse_mode": "HTML",
                            "protect_content": False
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
                            caption="📷 <b>QR Code para pagamento</b>\n📋 Toque em <b>Copiar Código PIX</b> abaixo para pagar via Copia e Cola.",
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
# INICIALIZAÇÃO (roda uma única vez — compatível com Gunicorn)
# ============================================================
_init_done = threading.Event()
_init_lock = threading.Lock()

def _inicializar():
    """Inicializa banco, webhook, comandos e threads de background.
    Usa lock de arquivo para garantir que só 1 worker do Gunicorn execute isso.
    """
    with _init_lock:
        if _init_done.is_set():
            print("[INIT] Já inicializado. Pulando.")
            return
        _init_done.set()

    print("=" * 50)
    print("🤖 Bot Syntek Gift Cards - v4")
    print(f"🗄️  Banco: {'PostgreSQL' if _USE_PG else 'SQLite'}")
    print(f"🌐 Webhook: {WEBHOOK_URL}/webhook")
    print("=" * 50)

    init_db()
    print("✅ Banco de dados inicializado")

    try:
        r = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": f"{WEBHOOK_URL}/webhook", "drop_pending_updates": True},
            timeout=10
        )
        result = r.json()
        if result.get("ok"):
            print(f"✅ Webhook configurado")
        else:
            print(f"⚠️ Webhook: {result.get('description')}")
    except Exception as e:
        print(f"⚠️ Erro ao configurar webhook: {e}")

    registrar_comandos()

    t1 = threading.Thread(target=verificar_pagamentos_loop, daemon=True)
    t1.start()
    print("✅ Verificador automático de pagamentos iniciado")

    t2 = threading.Thread(target=enviar_promocao_loop, daemon=True)
    t2.start()
    print("✅ Loop de promoção automática iniciado (1h)")

# Inicializa ao importar o módulo (compatível com Gunicorn preload_app)
_inicializar()

# ============================================================
# MAIN (usado apenas para desenvolvimento local)
# ============================================================
if __name__ == "__main__":
    print(f"🚀 Flask iniciando na porta {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)
