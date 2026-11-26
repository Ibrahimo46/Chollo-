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

# ---------- Botones (desactivados por ahora) ----------
BOT_URL = "https://t.me/ChollooOficial_bot"
SHOW_COINGECKO_BUTTON = False  # True = botón "Ver en CoinGecko" bajo la alerta
SHOW_BOT_BUTTON = False        # True cuando quieras promocionar el bot


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
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML",
               "disable_notification": silent,
               "link_preview_options": {"is_disabled": True}}
    if buttons:
        payload["reply_markup"] = buttons
    r = requests.post(url, json=payload)
    print("Texto enviado." if r.status_code == 200 else f"Error: {r.text}")


def send_to_telegram(text, image_url=None, buttons=None, silent=False):
    """Foto + texto. Si falla la foto, se envía solo el texto."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN no está configurado.")
        return
    if not image_url:
        return send_text(text, buttons, silent)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": image_url, "caption": text,
               "parse_mode": "HTML", "disable_notification": silent}
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
        r = requests.get(f"https://api.coingecko.com/api/v3/{path}",
                         params=params, headers=headers, timeout=30)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"Error CoinGecko ({path}): {e}")
        return None


def get_market_data():
    return cg_get("coins/markets", {
        "vs_currency": "usd", "order": "market_cap_desc", "per_page": 100,
        "page": 1, "sparkline": "false", "price_change_percentage": "1h,24h"})


FNG_ES = {"Extreme Fear": "Miedo extremo", "Fear": "Miedo", "Neutral": "Neutral",
          "Greed": "Codicia", "Extreme Greed": "Codicia extrema"}


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=20)
        d = r.json()["data"][0]
        return int(d["value"]), FNG_ES.get(d["value_classification"], d["value_classification"])
    except Exception as e:
        print(f"Error Fear & Greed: {e}")
        return None


# ---------- Formato ----------
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


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_es():
    now = datetime.now(MADRID)
    return f"{DIAS[now.weekday()]} {now.day} {MESES[now.month - 1]}"


# ---------- 1) Resumen diario ----------
def lectura_rapida(fng, dominance):
    parts = []
    if fng is not None:
        v = fng[0]
        if v <= 25:
            parts.append("Miedo extremo en el mercado: la volatilidad suele ser alta, "
                         "así que más prudencia y menos impulsos.")
        elif v <= 45:
            parts.append("El mercado sigue con miedo. Cuando domina el miedo, "
                         "las decisiones impulsivas suelen salir caras.")
        elif v <= 55:
            parts.append("Sentimiento neutral: el mercado espera una señal clara.")
        elif v <= 75:
            parts.append("Hay optimismo en el mercado. Ojo con la euforia: "
                         "lo que sube rápido también puede corregir rápido.")
        else:
            parts.append("Codicia extrema: históricamente es cuando más conviene la cautela.")
    if dominance is not None:
        if dominance >= 55:
            parts.append("Bitcoin domina el mercado, y las altcoins suelen moverse con más riesgo.")
        else:
            parts.append("Las altcoins ganan peso frente a Bitcoin.")
    return " ".join(parts)


def generate_digest(data):
    glob = (cg_get("global") or {}).get("data") or {}
    fng = get_fear_greed()
    trending = cg_get("search/trending") or {}

    btc = next((c for c in data if c["symbol"] == "btc"), None)
    eth = next((c for c in data if c["symbol"] == "eth"), None)
    movers = [c for c in data if c.get("price_change_percentage_24h") is not None]

    # Bloque 1: panorama general
    block = []
    cap = (glob.get("total_market_cap") or {}).get("usd")
    chg = glob.get("market_cap_change_percentage_24h_usd")
    if cap:
        arrow = "" if chg is None else f" ({'▲' if chg >= 0 else '▼'} {abs(chg):.1f}%)"
        block.append(f"🌍 Mercado total: <b>{compact(cap)}</b>{arrow}")
    dom = (glob.get("market_cap_percentage") or {}).get("btc")
    if dom is not None:
        block.append(f"₿ Dominancia BTC: <b>{dom:.1f}%</b>")
    if fng:
        icon = "😨" if fng[0] <= 45 else ("😐" if fng[0] <= 55 else "🤑")
        block.append(f"{icon} Miedo y codicia: <b>{fng[0]}/100</b> · {fng[1]}")

    lines = [f"📰 <b>Resumen cripto · {fecha_es()}</b>", ""]
    if block:
        lines += ["<blockquote>" + "\n".join(block) + "</blockquote>"]

    # Bloque 2: precios
    if btc:
        lines.append(f"₿ Bitcoin <b>{price(btc['current_price'])}</b> "
                     f"({pct(btc['price_change_percentage_24h'])})")
    if eth:
        lines.append(f"Ξ Ethereum <b>{price(eth['current_price'])}</b> "
                     f"({pct(eth['price_change_percentage_24h'])})")

    # Bloque 3: tendencia y extremos
    trend = [c["item"]["symbol"].upper() for c in (trending.get("coins") or [])[:3]]
    if trend:
        lines += ["", f"🔥 En tendencia: <b>{esc(', '.join(trend))}</b>"]
    if movers:
        best = max(movers, key=lambda c: c["price_change_percentage_24h"])
        worst = min(movers, key=lambda c: c["price_change_percentage_24h"])
        lines.append(f"🏆 Mejor 24h: <b>{esc(best['symbol'].upper())} "
                     f"{pct(best['price_change_percentage_24h'])}</b>")
        lines.append(f"📉 Peor 24h: <b>{esc(worst['symbol'].upper())} "
                     f"{pct(worst['price_change_percentage_24h'])}</b>")

    # Bloque 4: lectura rápida
    reading = lectura_rapida(fng, dom)
    if reading:
        lines += ["", f"<blockquote>💡 <b>Lectura rápida:</b> {esc(reading)}</blockquote>"]

    lines += ["", "#Cripto #Bitcoin #Chollo"]
    text = "\n".join(lines)

    if fng:
        image = f"https://alternative.me/crypto/fear-and-greed-index.png?t={int(time.time())}"
    else:
        image = btc.get("image") if btc else None
    return text, image, None


# ---------- 2) «Cripto en 30 segundos» ----------
TIPS = [
    ("¿Qué es una cartera (wallet)?",
     "Es la app o dispositivo que guarda tus claves privadas, no tus monedas. Las monedas viven en la blockchain; la clave es lo que te da acceso a ellas."),
    ("La frase semilla",
     "Son 12 o 24 palabras que restauran tu cartera. Quien las tenga controla tus fondos. No las compartas nunca ni las guardes en fotos o en la nube."),
    ("Cartera caliente vs. fría",
     "La caliente está conectada a internet: cómoda, pero más expuesta. La fría (hardware) guarda las claves fuera de línea y es más segura para cantidades grandes."),
    ("Exchange centralizado vs. descentralizado",
     "En un exchange centralizado la plataforma custodia tus fondos; en uno descentralizado operas desde tu propia cartera. Cada modelo tiene sus propios riesgos."),
    ("«Not your keys, not your coins»",
     "Si tus claves están en un exchange, el acceso a tus fondos depende de él. Es una advertencia sobre la custodia: conviene saber dónde están tus monedas."),
    ("Capitalización de mercado",
     "Se calcula como precio × monedas en circulación. Una moneda de $0.01 no es «más barata» que una de $1,000: compara la capitalización, no solo el precio."),
    ("Volumen de trading",
     "Es el valor negociado en 24 horas. Una subida con poco volumen es menos fiable, porque pocas operaciones pueden mover el precio."),
    ("Volatilidad",
     "Las criptomonedas pueden subir o caer un 10% en un solo día. Invierte únicamente lo que puedas permitirte perder."),
    ("DCA: comprar poco a poco",
     "Comprar una cantidad fija a intervalos regulares reduce el impacto de elegir mal el momento. No elimina el riesgo ni asegura ganancias."),
    ("Stop loss",
     "Es una orden que vende automáticamente si el precio cae a un nivel que tú fijas. Ayuda a limitar pérdidas, aunque en mercados muy rápidos puede ejecutarse a un precio peor."),
    ("FOMO",
     "Es el miedo a quedarte fuera: comprar solo porque algo sube mucho y todos hablan de ello. Suele terminar en comprar caro. Ten un plan antes de operar."),
    ("FUD",
     "Miedo, incertidumbre y duda: rumores negativos que pueden provocar ventas masivas. Verifica en fuentes oficiales antes de reaccionar."),
    ("El halving de Bitcoin",
     "Cada cuatro años aproximadamente, la recompensa de los mineros se reduce a la mitad. Limita la emisión de nuevos bitcoin y es un tema central en el mercado."),
    ("Stablecoins",
     "Son monedas diseñadas para mantener un valor estable, por ejemplo 1 dólar. Sirven para moverte entre criptos, pero revisa siempre quién las respalda."),
    ("Comisiones de red (gas)",
     "Es lo que pagas para que la red procese tu transacción. Varía según la congestión: compara antes de enviar y no te apresures."),
    ("Estafas de «duplica tu dinero»",
     "Nadie legítimo te garantiza rendimientos ni te pide enviar cripto para «desbloquear» ganancias. Si suena demasiado bueno para ser verdad, desconfía."),
    ("Phishing",
     "Son enlaces falsos que imitan webs reales para robar tus claves. Usa marcadores, escribe las direcciones a mano y nunca introduzcas tu frase semilla en una web."),
    ("Verifica la dirección y la red",
     "Las transacciones cripto no se pueden revertir. Comprueba la dirección y la red antes de enviar, y haz primero un envío pequeño de prueba."),
    ("Diversificación",
     "No poner todo en una sola moneda reduce el riesgo de que un único fallo te afecte demasiado. No significa comprar muchas monedas sin criterio."),
    ("¿Qué es una altcoin?",
     "Cualquier criptomoneda que no sea Bitcoin. Suelen ser más volátiles y arriesgadas que BTC."),
    ("Dominancia de Bitcoin",
     "Es el porcentaje del mercado total que representa Bitcoin. Si sube, el dinero se concentra en BTC; si baja, las altcoins ganan peso."),
    ("Índice de miedo y codicia",
     "Mide el sentimiento del mercado de 0 (miedo extremo) a 100 (codicia extrema). Es un termómetro, no una predicción."),
    ("Capitalización baja = más riesgo",
     "Las monedas de baja capitalización se mueven con pocas operaciones: pueden dispararse, pero también caer a cero. Investiga antes de entrar."),
    ("Rug pull",
     "Ocurre cuando los creadores de un proyecto se llevan el dinero y lo abandonan. Señales de alerta: equipo anónimo, promesas irreales y falta de auditorías."),
    ("Staking",
     "Consiste en bloquear tus monedas para ayudar a validar una red a cambio de recompensas. Ojo: tus fondos pueden quedar bloqueados y las recompensas no están garantizadas."),
    ("¿Qué es un NFT?",
     "Es un token único que representa la propiedad de un elemento digital. Su valor depende por completo de la demanda y el mercado puede ser poco líquido."),
    ("¿Qué es la blockchain?",
     "Es un registro público y compartido donde las transacciones quedan encadenadas y son muy difíciles de alterar. Es la tecnología detrás de Bitcoin."),
    ("Impuestos y criptomonedas",
     "En muchos países vender o intercambiar cripto es una operación fiscal. Guarda un registro de tus compras y ventas y consulta las normas de tu país."),
    ("Liquidez",
     "Es la facilidad para comprar o vender sin mover el precio. Una moneda con poca liquidez puede ser difícil de vender justo cuando lo necesitas."),
    ("Ten un plan antes de operar",
     "Define de antemano cuánto inviertes, cuándo sales si va mal y cuándo tomas ganancias. Un plan escrito te protege de decidir con emociones."),
]


def generate_tip():
    today = datetime.now(MADRID).date()
    n = today.toordinal() % len(TIPS)
    title, body = TIPS[n]
    text = (f"💡 <b>Cripto en 30 segundos: {esc(title)}</b>\n\n"
            f"<blockquote>{esc(body)}</blockquote>\n"
            f"📌 Guarda este post por si lo necesitas más tarde.\n\n"
            f"#Aprende #Cripto #Chollo")
    return text, None, None


# ---------- 3) Alerta de volatilidad ----------
def generate_volatility_alert(data):
    alerts = [c for c in data
              if c.get("price_change_percentage_1h_in_currency")
              and abs(c["price_change_percentage_1h_in_currency"]) >= 4.0]
    if not alerts:
        return None
    top = max(alerts, key=lambda x: abs(x["price_change_percentage_1h_in_currency"]))
    h1 = top["price_change_percentage_1h_in_currency"]
    h24 = top.get("price_change_percentage_24h")
    sym = top["symbol"].upper()

    verb = "sube" if h1 > 0 else "cae"
    icon = "🚀" if h1 > 0 else "📉"
    lines = [f"⏱ 1 hora: <b>{pct(h1)}</b>"]
    if h24 is not None:
        lines.append(f"⏳ 24 horas: <b>{pct(h24)}</b>")
    lines.append(f"💰 Precio: <b>{price(top['current_price'])}</b>")
    if top.get("total_volume"):
        lines.append(f"📦 Volumen 24h: <b>{compact(top['total_volume'])}</b>")
    if top.get("market_cap_rank"):
        lines.append(f"🏅 Ranking: <b>#{top['market_cap_rank']}</b>")

    text = (f"{icon} <b>{esc(top['name'])} ({esc(sym)}) {verb} un {abs(h1):.2f}%</b>\n\n"
            f"<blockquote>" + "\n".join(lines) + "</blockquote>\n"
            f"📊 ¿Oportunidad o trampa? Analiza antes de operar.\n\n"
            f"{tag(sym)} #Cripto #Chollo")
    buttons = keyboard([[chart_button(top["id"]), bot_button()]])
    return text, top.get("image"), buttons


# ---------- Main ----------
def main():
    print(f"Tipo de publicación: {POST_TYPE}")

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
