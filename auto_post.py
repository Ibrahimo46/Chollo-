import requests
import os
import random

# إذا كنت تستخدم GitHub Secrets، سيتم استخدامها. وإلا، سيتم استخدام القيمة الافتراضية.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@CholloOficial")

def send_to_telegram(text):
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN no está configurado.")
        return
        
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("✅ Publicado con éxito en @CholloOficial.")
    else:
        print(f"❌ Error al publicar: {response.text}")

def get_market_data():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h" 
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

# --- الفكرة الرابعة: تنبيه التقلبات (Volatility Alert) ---
def generate_volatility_alert(data):
    alerts = []
    for coin in data:
        change_1h = coin.get('price_change_percentage_1h_in_currency')
        if change_1h and abs(change_1h) >= 4.0: # حركة 4% أو أكثر في ساعة
            alerts.append(coin)
    
    if not alerts:
        return None
        
    top_alert = max(alerts, key=lambda x: abs(x.get('price_change_percentage_1h_in_currency', 0)))
    change = top_alert['price_change_percentage_1h_in_currency']
    direction = "🚀 subida" if change > 0 else "🔻 caída"
    
    text = f"🚨 <b>¡ALERTA DE VOLATILIDAD!</b> 🚨\n\n"
    text += f"<b>{top_alert['name']} ({top_alert['symbol'].upper()})</b> acaba de registrar una {direction} del <b>{abs(change):.2f}%</b> en la última hora.\n\n"
    text += f"💰 Precio actual: <b>${top_alert['current_price']:,}</b>\n"
    text += f"📊 ¿Oportunidad o trampa? Mantente atento al mercado.\n\n"
    text += f"💡 <i>Analiza el mercado antes de operar.</i>"
    return text

# --- الفكرة الأولى: الأكثر ربحاً وخسارة ---
def generate_top_movers(data):
    sorted_data = sorted([c for c in data if c.get('price_change_percentage_24h') is not None], key=lambda x: x['price_change_percentage_24h'], reverse=True)
    gainers = sorted_data[:3]
    losers = sorted_data[-3:]
    text = f"🚀 <b>Top Ganadores (24h)</b>\n"
    for g in gainers: text += f"• {g['symbol'].upper()}: 📈 +{g['price_change_percentage_24h']:.2f}%\n"
    text += f"\n📉 <b>Top Perdedores (24h)</b>\n"
    for l in reversed(losers): text += f"• {l['symbol'].upper()}: 📉 {l['price_change_percentage_24h']:.2f}%\n"
    text += f"\n💡 <i>El mercado se mueve rápido. Encuentra tu próxima oportunidad.</i>"
    return text

# --- الفكرة الثانية: مبارزة العملات ---
def generate_duel(data):
    btc = next((c for c in data if c['symbol'] == 'btc'), None)
    eth = next((c for c in data if c['symbol'] == 'eth'), None)
    if not btc or not eth: return None
    
    btc_change = btc['price_change_percentage_24h']
    eth_change = eth['price_change_percentage_24h']
    winner = "Bitcoin (BTC)" if btc_change > eth_change else "Ethereum (ETH)"
    
    text = f"🥊 <b>Duelo de rendimiento (Últimas 24h)</b>\n\n"
    text += f"• <b>Bitcoin (BTC):</b> {'📈' if btc_change > 0 else '📉'} {btc_change:+.2f}%\n"
    text += f"• <b>Ethereum (ETH):</b> {'📈' if eth_change > 0 else '📉'} {eth_change:+.2f}%\n\n"
    text += f"🏆 Hoy gana: <b>{winner}</b>\n"
    return text

# --- الفكرة الثالثة: حالة السوق ---
def generate_market_sentiment(data):
    btc = next((c for c in data if c['symbol'] == 'btc'), None)
    if not btc: return None
    
    change = btc['price_change_percentage_24h']
    if change > 2: status = "🟢 Positivo - Fuerte impulso comprador."
    elif change < -2: status = "🔴 Negativo - Presión de venta."
    else: status = "🟡 Neutral - Mercado en consolidación."
    
    text = f"📊 <b>Termómetro del Mercado</b>\n\nBitcoin se mueve en <b>{change:+.2f}%</b> (24h).\n\n🚦 <b>Estado:</b> {status}\n\n💡 <i>Mantente informado.</i>"
    return text

def main():
    data = get_market_data()
    if not data or isinstance(data, dict):
        print("Error al obtener datos de CoinGecko.")
        return

    # 1. الأولوية القصوى: هل هناك تنبيه تقلبات؟
    alert_msg = generate_volatility_alert(data)
    
    if alert_msg:
        print("Volatility alert triggered!")
        send_to_telegram(alert_msg)
    else:
        # 2. إذا لم تكن هناك تقلبات، نختار فكرة عشوائية من الأفكار الثلاثة
        content_type = random.choice(["movers", "duel", "sentiment"])
        if content_type == "movers":
            send_to_telegram(generate_top_movers(data))
        elif content_type == "duel":
            send_to_telegram(generate_duel(data))
        elif content_type == "sentiment":
            send_to_telegram(generate_market_sentiment(data))

if __name__ == "__main__":
    main()
