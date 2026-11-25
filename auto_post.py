import os
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


# ---------- Ideas (texto, imagen de la moneda) ----------
def generate_volatility_alert(data):
    alerts = [c for c in data
              if c.get("price_change_percentage_1h_in_currency")
              and abs(c["price_change_percentage_1h_in_currency"]) >= 4.0]
    if not alerts:
        return None
    top = max(alerts, key=lambda x: abs(x["price_change_percentage_1h_in_currency"]))
    change = top["price_change_percentage_1h_in_currency"]
    direction = "🚀 subida" if change > 0 else "📉 caída"

    text = "🚨 <b>¡ALERTA DE VOLATILIDAD!</b> 🚨\n\n"
    text += (f"<b>{top['name']} ({top['symbol'].upper()})</b> acaba de registrar "
             f"una {direction} del <b>{abs(change):.2f}%</b> en la última hora.\n\n")
    text += f"💰 Precio actual: <b>${top['current_price']:,}</b>\n"
    text += "📊 ¿Oportunidad o trampa? Mantente atento al mercado.\n\n"
    text += "💡 <i>Analiza el mercado antes de operar.</i>"
    return text, top.get("image")


def generate_top_movers(data):
    valid = [c for c in data if c.get("price_change_percentage_24h") is not None]
    s = sorted(valid, key=lambda x: x["price_change_percentage_24h"], reverse=True)
    gainers, losers = s[:3], list(reversed(s[-3:]))

    text = "🏆 <b>Top Ganadores (24h)</b>\n"
    for g in gainers:
        text += f"• {g['symbol'].upper()}: +{g['price_change_percentage_24h']:.2f}%\n"
    text += "\n📉 <b>Top Perdedores (24h)</b>\n"
    for l in losers:
        text += f"• {l['symbol'].upper()}: {l['price_change_percentage_24h']:.2f}%\n"
    text += "\n💡 <i>El mercado se mueve rápido. Encuentra tu próxima oportunidad.</i>"
    return text, gainers[0].get("image")


def generate_duel(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    eth = next((c for c in data if c["symbol"] == "eth"), None)
    if not btc or not eth:
        return None
    b, e = btc["price_change_percentage_24h"], eth["price_change_percentage_24h"]
    winner_coin = btc if b > e else eth
    winner = "Bitcoin (BTC)" if b > e else "Ethereum (ETH)"

    text = "⚔️ <b>Duelo de rendimiento (Últimas 24h)</b>\n\n"
    text += f"• <b>Bitcoin (BTC):</b> {'🟢' if b > 0 else '🔴'} {b:+.2f}%\n"
    text += f"• <b>Ethereum (ETH):</b> {'🟢' if e > 0 else '🔴'} {e:+.2f}%\n\n"
    text += f"🏆 Hoy gana: <b>{winner}</b>\n"
    return text, winner_coin.get("image")


def generate_market_sentiment(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    if not btc:
        return None
    ch = btc["price_change_percentage_24h"]
    if ch > 2:
        status = "🟢 Positivo - Fuerte impulso comprador."
    elif ch < -2:
        status = "🔴 Negativo - Presión de venta."
    else:
        status = "🟡 Neutral - Mercado en consolidación."

    text = (f"🌡 <b>Termómetro del Mercado</b>\n\nBitcoin se mueve en "
            f"<b>{ch:+.2f}%</b> (24h).\n\n📌 <b>Estado:</b> {status}\n\n"
            f"💡 <i>Mantente informado.</i>")
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
