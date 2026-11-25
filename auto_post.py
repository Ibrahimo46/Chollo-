import os
import html
import random
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@CholloOficial")
CG_API_KEY = os.environ.get("COINGECKO_API_KEY")


# ---------- Imagen desde plantilla HTML ----------
def render_card(badge, content, out="card.png"):
    from playwright.sync_api import sync_playwright

    with open(os.path.join(BASE, "templates", "card.html"), encoding="utf-8") as f:
        page = f.read()

    if os.path.exists(os.path.join(BASE, "assets", "logo.png")):
        logo = '<img class="logo" src="assets/logo.png">'
    else:
        logo = '<div class="logo-fallback">C</div>'

    page = (page.replace("{{LOGO}}", logo)
                .replace("{{BADGE}}", html.escape(badge))
                .replace("{{CONTENT}}", content))

    tmp = os.path.join(BASE, "_render.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(page)

    out_path = os.path.join(BASE, out)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1080, "height": 1080})
        pg.goto("file://" + tmp)
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=out_path)
        browser.close()
    return out_path


def safe_render(badge, content):
    try:
        return render_card(badge, content)
    except Exception as e:
        print(f"No se pudo generar la imagen: {e}")
        return None


def row(label, value, css):
    return (f'<div class="row"><span>{html.escape(label)}</span>'
            f'<span class="{css}">{html.escape(value)}</span></div>')


# ---------- Telegram ----------
def send_text(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHANNEL_ID, "text": text,
                                 "parse_mode": "HTML"})
    print("Texto enviado." if r.status_code == 200 else f"Error: {r.text}")


def send_to_telegram(text, image=None):
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN no está configurado.")
        return
    if not image:
        return send_text(text)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    data = {"chat_id": CHANNEL_ID, "caption": text, "parse_mode": "HTML"}
    try:
        with open(image, "rb") as f:
            r = requests.post(url, data=data, files={"photo": f}, timeout=60)
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


# ---------- Ideas ----------
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

    css = "up" if change > 0 else "down"
    arrow = "▲" if change > 0 else "▼"
    coin = f'<img class="coin" src="{top["image"]}">' if top.get("image") else ""
    content = (f'<h1>{coin}<span>{html.escape(top["name"])} ({top["symbol"].upper()})</span></h1>'
               f'<div class="big {css}">{arrow} {abs(change):.2f}%</div>'
               f'<div class="sub">Precio actual ${top["current_price"]:,} · última hora</div>')
    return text, safe_render("Volatilidad 1h", content)


def generate_top_movers(data):
    valid = [c for c in data if c.get("price_change_percentage_24h") is not None]
    s = sorted(valid, key=lambda x: x["price_change_percentage_24h"], reverse=True)
    gainers, losers = s[:3], list(reversed(s[-3:]))

    text = "🏆 <b>Top Ganadores (24h)</b>\n"
    content = '<div class="sec">Top ganadores</div><div class="rows">'
    for g in gainers:
        v = g["price_change_percentage_24h"]
        text += f"• {g['symbol'].upper()}: +{v:.2f}%\n"
        content += row(g["symbol"].upper(), f"▲ {v:.2f}%", "up")
    content += '</div>'

    text += "\n📉 <b>Top Perdedores (24h)</b>\n"
    content += '<div class="sec">Top perdedores</div><div class="rows">'
    for l in losers:
        v = l["price_change_percentage_24h"]
        text += f"• {l['symbol'].upper()}: {v:.2f}%\n"
        content += row(l["symbol"].upper(), f"▼ {abs(v):.2f}%", "down")
    content += '</div>'

    text += "\n💡 <i>El mercado se mueve rápido. Encuentra tu próxima oportunidad.</i>"
    return text, safe_render("Últimas 24h", content)


def generate_duel(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    eth = next((c for c in data if c["symbol"] == "eth"), None)
    if not btc or not eth:
        return None
    b, e = btc["price_change_percentage_24h"], eth["price_change_percentage_24h"]
    winner = "Bitcoin (BTC)" if b > e else "Ethereum (ETH)"

    text = "⚔️ <b>Duelo de rendimiento (Últimas 24h)</b>\n\n"
    text += f"• <b>Bitcoin (BTC):</b> {'🟢' if b > 0 else '🔴'} {b:+.2f}%\n"
    text += f"• <b>Ethereum (ETH):</b> {'🟢' if e > 0 else '🔴'} {e:+.2f}%\n\n"
    text += f"🏆 Hoy gana: <b>{winner}</b>\n"

    content = ('<div class="sec">Bitcoin vs Ethereum</div><div class="rows">'
               + row("BTC", f"{b:+.2f}%", "up" if b > 0 else "down")
               + row("ETH", f"{e:+.2f}%", "up" if e > 0 else "down")
               + '</div>'
               f'<div class="sub">Hoy gana: <span class="gold">{winner}</span></div>')
    return text, safe_render("Duelo 24h", content)


def generate_market_sentiment(data):
    btc = next((c for c in data if c["symbol"] == "btc"), None)
    if not btc:
        return None
    ch = btc["price_change_percentage_24h"]
    if ch > 2:
        status, label, css = "🟢 Positivo - Fuerte impulso comprador.", "Positivo", "up"
    elif ch < -2:
        status, label, css = "🔴 Negativo - Presión de venta.", "Negativo", "down"
    else:
        status, label, css = "🟡 Neutral - Mercado en consolidación.", "Neutral", "gold"

    text = (f"🌡 <b>Termómetro del Mercado</b>\n\nBitcoin se mueve en "
            f"<b>{ch:+.2f}%</b> (24h).\n\n📌 <b>Estado:</b> {status}\n\n"
            f"💡 <i>Mantente informado.</i>")
    content = (f'<h1><span>Bitcoin (BTC) · 24h</span></h1>'
               f'<div class="big {css}">{ch:+.2f}%</div>'
               f'<div class="sub">Estado del mercado: <span class="{css}">{label}</span></div>')
    return text, safe_render("Termómetro", content)


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
