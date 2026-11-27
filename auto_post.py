import os
import re
import html
import time
import requests
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:
    MADRID = timezone.utc

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@CholloOficial")
CG_API_KEY = os.environ.get("COINGECKO_API_KEY")
POST_TYPE = os.environ.get("POST_TYPE", "alert")  # digest | tip | alert
SLOT = os.environ.get("POST_SLOT", "apertura")   # apertura | seguimiento | conversion | cierre

# ---------- Botones (desactivados por ahora) ----------
BOT_URL = "https://t.me/ChollooOficial_bot"
SHOW_COINGECKO_BUTTON = False
SHOW_BOT_BUTTON = False


def keyboard(rows):
    clean = [[b for b in row if b] for row in rows]
    clean = [row for row in clean if row]
    if not clean:
        return None
    return {"inline_keyboard": [[{"text": t, "url": u} for t, u in row] for row in clean]}


def chart_button(coin_id, label="📈 Ver en CoinGecko"):
    if not SHOW_COINGECKO_BUTTON:
        return None
    return (label, f"https://www.coingecko.com/es/monedas/{coin_id}")


def bot_button():
    return ("🛒 Chollos de hoy", BOT_URL) if SHOW_BOT_BUTTON else None


# ---------- Telegram ----------
def send_text(text, buttons=None, silent=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": silent,
        "link_preview_options": {"is_disabled": True},
    }
    if buttons:
        payload["reply_markup"] = buttons
    r = requests.post(url, json=payload, timeout=30)
    print("Texto enviado." if r.status_code == 200 else f"Error: {r.text}")


def send_to_telegram(text, image_url=None, buttons=None, silent=False):
    """Foto + texto. Si falla la foto, se envía solo el texto."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN no está configurado.")
        return
    if not image_url:
        return send_text(text, buttons, silent)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": image_url,
        "caption": text,
        "parse_mode": "HTML",
        "disable_notification": silent,
    }
    if buttons:
        payload["reply_markup"] = buttons
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            print("Publicado con foto.")
            return
        print(f"Error con foto: {r.text}")
    except Exception as e:
        print(f"Error con foto: {e}")
    send_text(text, buttons, silent)


# ---------- Datos ----------
def cg_get(path, params=None):
    headers = {"x-cg-demo-api-key": CG_API_KEY} if CG_API_KEY else {}
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/{path}",
            params=params,
            headers=headers,
            timeout=30,
        )
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"Error CoinGecko ({path}): {e}")
        return None


def get_market_data():
    return cg_get(
        "coins/markets",
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h",
        },
    )


FNG_ES = {
    "Extreme Fear": "Miedo extremo",
    "Fear": "Miedo",
    "Neutral": "Neutral",
    "Greed": "Codicia",
    "Extreme Greed": "Codicia extrema",
}


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20)
        d = r.json()["data"][0]
        return int(d["value"]), FNG_ES.get(d["value_classification"], d["value_classification"])
    except Exception as e:
        print(f"Error Fear & Greed: {e}")
        return None


# ---------- Formato y plantilla unificada ----------
def esc(x):
    return html.escape(str(x))


def tag(symbol):
    return "#" + re.sub(r"[^A-Za-z0-9_]", "", symbol.upper())


def pct(v):
    return f"{v:+.2f}%"


def price(p):
    if p is None:
        return "—"
    if p >= 1:
        return f"${p:,.2f}"
    return "$" + f"{p:.6f}".rstrip("0").rstrip(".")


def compact(n):
    if n is None:
        return "—"
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= limit:
            return f"${n / limit:.2f}{suffix}"
    return f"${n:,.0f}"


SLOT_CONFIG = {
    "apertura": (
        "Resumen · Apertura",
        "💡 Revisa precios y spreads antes de operar.",
    ),
    "seguimiento": (
        "Resumen · Seguimiento",
        "💡 Sigue los movimientos clave antes de actuar.",
    ),
    "conversion": (
        "Resumen · Conversión",
        "💡 Compara el momento y coste al convertir.",
    ),
    "cierre": (
        "Resumen · Cierre",
        "💡 Cierra el día con calma; evita impulsos.",
    ),
}


def format_unified_post(badge, title, box_lines, tip_line, hashtags):
    """قالب موحّد مختصر ومنسق بدون تاريخ."""
    parts = [f"{badge} <b>{esc(title)}</b>"]
    if box_lines:
        parts += ["", "<blockquote>" + "\n".join(box_lines) + "</blockquote>"]
    if tip_line:
        parts += ["", esc(tip_line)]
    parts += ["", hashtags]
    return "\n".join(parts)


# ---------- 1) Resumen diario (4 franjas) ----------
def generate_digest(data):
    glob = (cg_get("global") or {}).get("data") or {}
    fng = get_fear_greed()
    trending = cg_get("search/trending") or {}

    btc = next((c for c in data if c["symbol"] == "btc"), None)
    eth = next((c for c in data if c["symbol"] == "eth"), None)
    movers = [c for c in data if c.get("price_change_percentage_24h") is not None]

    slot_title, tip_line = SLOT_CONFIG.get(SLOT, SLOT_CONFIG["apertura"])

    box_lines = []
    cap = (glob.get("total_market_cap") or {}).get("usd")
    chg = glob.get("market_cap_change_percentage_24h_usd")
    if cap:
        arrow = "" if chg is None else f" ({'▲' if chg >= 0 else '▼'} {abs(chg):.1f}%)"
        box_lines.append(f"🌍 Mercado: <b>{compact(cap)}</b>{arrow}")
    dom = (glob.get("market_cap_percentage") or {}).get("btc")
    if dom is not None:
        box_lines.append(f"₿ Dom. BTC: <b>{dom:.1f}%</b>")
    if fng:
        icon = "😨" if fng[0] <= 45 else ("😐" if fng[0] <= 55 else "🤑")
        box_lines.append(f"{icon} Sentimiento: <b>{fng[0]}/100</b> · {esc(fng[1])}")

    if btc:
        box_lines.append(f"₿ BTC: <b>{price(btc['current_price'])}</b> ({pct(btc['price_change_percentage_24h'])})")
    if eth:
        box_lines.append(f"Ξ ETH: <b>{price(eth['current_price'])}</b> ({pct(eth['price_change_percentage_24h'])})")

    trend = [c["item"]["symbol"].upper() for c in (trending.get("coins") or [])[:3]]
    if trend:
        box_lines.append(f"🔥 Top 3: <b>{esc(', '.join(trend))}</b>")
    if movers:
        best = max(movers, key=lambda c: c["price_change_percentage_24h"])
        worst = min(movers, key=lambda c: c["price_change_percentage_24h"])
        box_lines.append(f"🏆 Top 24h: <b>{esc(best['symbol'].upper())} {pct(best['price_change_percentage_24h'])}</b>")
        box_lines.append(f"📉 Peor 24h: <b>{esc(worst['symbol'].upper())} {pct(worst['price_change_percentage_24h'])}</b>")

    text = format_unified_post(
        badge="📰",
        title=slot_title,
        box_lines=box_lines,
        tip_line=tip_line,
        hashtags="#Cripto #Bitcoin #Chollo",
    )

    if fng:
        image = f"https://alternative.me/crypto/fear-and-greed-index.png?t={int(time.time())}"
    else:
        image = btc.get("image") if btc else None
    return text, image, None


# ---------- 2) «Cripto en 30 segundos» ----------
TIPS = [
    ("¿Qué es una cartera (wallet)?",
     "Guarda tus claves privadas, no tus monedas. Las monedas viven en la blockchain; la clave te da acceso."),
    ("La frase semilla",
     "12 o 24 palabras que restauran tu cartera. Quien las tenga controla tus fondos; no las guardes en fotos o nube."),
    ("Cartera caliente vs. fría",
     "La caliente está conectada a internet; la fría guarda claves sin conexión y es más segura para montos mayores."),
    ("Exchange centralizado vs. descentralizado",
     "En un CEX custodias en la plataforma; en un DEX operas desde tu cartera. Cada modelo tiene riesgos propios."),
    ("«Not your keys, not your coins»",
     "Si tus claves están en un exchange, el acceso depende de él. Revisa dónde custodias tus fondos."),
    ("Capitalización de mercado",
     "Precio × oferta en circulación. Compara la capitalización, no solo el precio unitario de la moneda."),
    ("Volumen de trading",
     "Valor negociado en 24h. Poco volumen significa mayor facilidad para mover el precio con pocas órdenes."),
    ("Volatilidad",
     "Movimientos bruscos en poco tiempo son habituales. Opera con gestión de riesgo y sin comprometer lo necesario."),
    ("DCA: comprar poco a poco",
     "Compras periódicas de un monto fijo suavizan el punto de entrada, aunque no eliminan el riesgo de mercado."),
    ("Stop loss",
     "Orden automática para limitar pérdidas si el precio cae a un nivel definido, sujeta a deslizamiento en picos rápidos."),
    ("FOMO",
     "Comprar por miedo a quedarte fuera tras una subida rápida suele llevar a malas entradas. Sigue un plan."),
    ("FUD",
     "Miedo, incertidumbre y duda por rumores. Verifica en fuentes oficiales antes de reaccionar."),
    ("El halving de Bitcoin",
     "Reduce a la mitad la recompensa de bloque aproximadamente cada cuatro años, limitando la nueva emisión."),
    ("Stablecoins",
     "Buscan mantener paridad (por ejemplo 1 USD). Útiles para mover liquidez; revisa siempre su respaldo."),
    ("Comisiones de red (gas)",
     "Coste para procesar la transacción en la red. Varía según congestión; revisa antes de confirmar."),
    ("Estafas de «duplica tu dinero»",
     "Nadie legítimo garantiza rentabilidades ni pide enviar fondos para desbloquear premios. Desconfía."),
    ("Phishing",
     "Enlace o web falsa que imita servicios reales para robar claves. Usa marcadores y nunca compartas tu semilla."),
    ("Verifica la dirección y la red",
     "Las transferencias en blockchain son irreversibles. Confirma dirección y red; haz una prueba pequeña si dudas."),
    ("Diversificación",
     "Repartir exposición reduce el impacto de un fallo aislado, siempre con criterio y sin sobreexposición."),
    ("¿Qué es una altcoin?",
     "Cualquier cripto distinta de Bitcoin; suele presentar mayor volatilidad y riesgo."),
    ("Dominancia de Bitcoin",
     "Porcentaje del mercado total que ocupa BTC. Ayuda a leer si el capital se concentra en BTC o rota a altcoins."),
    ("Índice de miedo y codicia",
     "Mide el sentimiento de 0 a 100. Es una referencia del entorno, no una señal automática de compra o venta."),
    ("Capitalización baja = más riesgo",
     "Tokens de baja capitalización pueden moverse con fuerza en ambos sentidos y tener menor liquidez."),
    ("Rug pull",
     "Abandono de un proyecto retirando su liquidez. Cuidado con promesas irreales, falta de transparencia y prisas."),
    ("Staking",
     "Bloquear fondos para apoyar una red a cambio de recompensas, con posibles periodos de bloqueo y riesgo asociado."),
    ("¿Qué es un NFT?",
     "Token único ligado a un activo digital; su liquidez y valor dependen por completo de la demanda."),
    ("¿Qué es la blockchain?",
     "Registro distribuido y encadenado donde las operaciones quedan registradas de forma verificable."),
    ("Impuestos y criptomonedas",
     "Vender o permutar cripto puede tener implicaciones fiscales según tu país. Lleva un registro claro de tus movimientos."),
    ("Liquidez",
     "Facilidad para entrar o salir sin alterar demasiado el precio. Baja liquidez implica mayor coste de ejecución."),
    ("Ten un plan antes de operar",
     "Define entrada, invalidación y objetivo antes de ejecutar. Reduce decisiones guiadas por la emoción."),
]


def generate_tip():
    today = datetime.now(MADRID).date()
    n = today.toordinal() % len(TIPS)
    title, body = TIPS[n]
    text = format_unified_post(
        badge="💡",
        title=f"30s · {title}",
        box_lines=[esc(body)],
        tip_line="💡 Guarda este apunte para consultarlo rápido.",
        hashtags="#Aprende #Cripto #Chollo",
    )
    return text, None, None


# ---------- 3) Alerta de volatilidad ----------
def generate_volatility_alert(data):
    alerts = [
        c for c in data
        if c.get("price_change_percentage_1h_in_currency")
        and abs(c["price_change_percentage_1h_in_currency"]) >= 4.0
    ]
    if not alerts:
        return None
    top = max(alerts, key=lambda x: abs(x["price_change_percentage_1h_in_currency"]))
    h1 = top["price_change_percentage_1h_in_currency"]
    h24 = top.get("price_change_percentage_24h")
    sym = top["symbol"].upper()

    verb = "sube" if h1 > 0 else "cae"
    icon = "🚀" if h1 > 0 else "📉"
    box_lines = [f"⏱ 1h: <b>{pct(h1)}</b>"]
    if h24 is not None:
        box_lines.append(f"⏳ 24h: <b>{pct(h24)}</b>")
    box_lines.append(f"💰 Precio: <b>{price(top['current_price'])}</b>")
    if top.get("total_volume"):
        box_lines.append(f"📦 Vol 24h: <b>{compact(top['total_volume'])}</b>")
    if top.get("market_cap_rank"):
        box_lines.append(f"🏅 Rank: <b>#{top['market_cap_rank']}</b>")

    text = format_unified_post(
        badge=icon,
        title=f"{esc(sym)} ({top['name']}) {verb} {abs(h1):.2f}%",
        box_lines=box_lines,
        tip_line="💡 Revisa liquidez y spread antes de moverte.",
        hashtags=f"{tag(sym)} #Cripto #Chollo",
    )
    buttons = keyboard([[chart_button(top["id"]), bot_button()]])
    return text, top.get("image"), buttons


# ---------- Main ----------
def main():
    print(f"Tipo de publicación: {POST_TYPE} | Franja: {SLOT}")

    if POST_TYPE == "tip":
        text, image, buttons = generate_tip()
        return send_to_telegram(text, image, buttons, silent=True)

    data = get_market_data()
    if not data or isinstance(data, dict):
        print("Error al obtener datos de CoinGecko.")
        return

    if POST_TYPE == "digest":
        text, image, buttons = generate_digest(data)
        return send_to_telegram(text, image, buttons, silent=False)

    result = generate_volatility_alert(data)
    if not result:
        print("No hay alerta de volatilidad ahora. No se publica nada.")
        return
    text, image, buttons = result
    print("Volatility alert triggered!")
    send_to_telegram(text, image, buttons, silent=False)


if __name__ == "__main__":
    main()
