import os
import re
import html
import random
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@CholloOficial")
CG_API_KEY = os.environ.get("COINGECKO_API_KEY")


# ---------- Telegram ----------
def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHANNEL_ID, "text": text,
                                 "parse_mode": "HTML"})
    print("Texto enviado." if r.status_code == 200 else f"Error: {r.text}")


def send_to_telegram(text, image_url=None):
    """Envía foto (URL del logo de la moneda) + texto. Si falla, solo texto."""
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN no está configurado.")
        return
    if not image_url:
        return send_text(text)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": CHANNEL_ID, "photo": image_url,
               "caption": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            print("Publicado con foto.")
            return
        print(f"Error con foto: {r.text}")
    except Exception as e:
        print(f"Error con foto: {e}")
    send_text(text)


# ---------- Datos ----------
def get_market_data():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100,
              "page": 1, "sparkline": "false", "price_change_percentage": "1h,24h"}
    headers = {"x-cg-demo-api-key": CG_API_KEY} if CG_API_KEY else {}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    return r.json() if r.status_code == 200 else None


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


def dot(v):
    return "🟢" if v > 0 else "🔴"


# ---------- Ideas (texto, imagen de la moneda) ----------
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
    lines = [f"⏱ Última hora: <b>{pct(h1)}</b>"]
    if h24 is not None:
        lines.append(f"📅 24 horas: <b>{pct(h24)}</b>")
    lines.append(f"💰 Precio: <b>{price(top['current_price'])}</b>")

    text = (f"{icon} <b>{esc(top['name'])} ({esc(sym)}) {verb} un {abs(h1):.2f}%</b>\n\n"
            f"<blockquote>" + "\n".join(lines) + "</blockquote>\n"
            f"📊 ¿Oportunidad o trampa? Analiza antes de operar.\n\n"
            f"{tag(sym)} #Cripto #Chollo")
    return text, top.get("image")


def generate_top_movers(data):
    valid = [c for c in data if c.get("price_change_percentage_24h") is not None]
    s = sorted(valid, key=lambda x: x["price_change_percentage_24h"], reverse=True)
    gainers, losers = s[:3], list(reversed(s[-3:]))
    lead = gainers[0]

    body = "🟢 <b>Ganadores (24h)</b>\n"
    for g in gainers:
        body += f"• {esc(g['symbol'].upper())}: {pct(g['price_change_percentage_24h'])}\n"
    body += "\n🔴 <b>Perdedores (24h)</b>\n"
    for l in losers:
        body += f"• {esc(l['symbol'].upper())}: {pct(l['price_change_percentage_24h'])}\n"

    text = (f"🏆 <b>{esc(lead['name'])} ({esc(lead['symbol'].upper())}) lidera el día con "
            f"{pct(lead['price_change_percentage_24h'])}</b>\n\n"
            f"<blockquote>{body.rstrip()}</blockquote>\n"
            f"📊 El mercado se mueve rápido. Encuentra tu próxima oportunidad.\n\n"
            f"#Cripto #Mercado #Chollo")
    return text, lead.get("image")


def generate_duel(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    eth = next((c for c in data if c["symbol"] == "eth"), None)
    if not btc or not eth:
        return None
    b, e = btc["price_change_percentage_24h"], eth["price_change_percentage_24h"]
    win_coin = btc if b > e else eth
    winner = "Bitcoin (BTC)" if b > e else "Ethereum (ETH)"

    body = (f"• Bitcoin (BTC): {dot(b)} <b>{pct(b)}</b>\n"
            f"• Ethereum (ETH): {dot(e)} <b>{pct(e)}</b>\n"
            f"📏 Diferencia: <b>{abs(b - e):.2f} puntos</b>")
    text = (f"⚔️ <b>{winner} gana el duelo de hoy</b>\n\n"
            f"<blockquote>{body}</blockquote>\n"
            f"📊 Rendimiento de las últimas 24 horas.\n\n"
            f"#BTC #ETH #Cripto #Chollo")
    return text, win_coin.get("image")


def generate_market_sentiment(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    if not btc:
        return None
    ch = btc["price_change_percentage_24h"]
    if ch > 2:
        word, status = "positivo", "🟢 Positivo - Fuerte impulso comprador."
    elif ch < -2:
        word, status = "negativo", "🔴 Negativo - Presión de venta."
    else:
        word, status = "neutral", "🟡 Neutral - Mercado en consolidación."

    body = (f"₿ Bitcoin (24h): <b>{pct(ch)}</b>\n"
            f"💰 Precio: <b>{price(btc['current_price'])}</b>\n"
            f"📌 Estado: {status}")
    text = (f"🌡 <b>Mercado {word}: Bitcoin {pct(ch)}</b>\n\n"
            f"<blockquote>{body}</blockquote>\n"
            f"📊 Mantente informado.\n\n"
            f"#BTC #Cripto #Chollo")
    return text, btc.get("image")


def main():
    data = get_market_data()
    if not data or isinstance(data, dict):
        print("Error al obtener datos de CoinGecko.")
        return

    result = generate_volatility_alert(data)
    if result:
        print("Volatility alert triggered!")
    else:
        gen = random.choice([generate_top_movers, generate_duel,
                             generate_market_sentiment])
        result = gen(data)

    if result:
        text, image = result
        send_to_telegram(text, image)


if __name__ == "__main__":
    main()
