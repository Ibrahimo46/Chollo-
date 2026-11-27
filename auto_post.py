import html
import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHANNEL_ID")


def build_fixed_caption(data: dict) -> str:
    """
    قالب نص ثابت وموحّد لجميع المنشورات بتنسيق HTML (بدون زر Mini App)
    """
    esc = lambda v: html.escape(str(v))

    return (
        f"<b>{esc(data['header'])}</b>\n"
        f"<i>{esc(data['date_str'])}</i>\n\n"
        f"• <b>Mercado total:</b> <code>{esc(data['market_cap'])}</code> (<code>{esc(data['market_cap_change'])}</code>)\n"
        f"• <b>Dominancia BTC:</b> <code>{esc(data['btc_dominance'])}</code>\n"
        f"• <b>Sentimiento:</b> <code>{esc(data['fng_value'])}/100</code> — <b>{esc(data['fng_label'])}</b>\n\n"
        f"<b>Precios clave:</b>\n"
        f"• <b>BTC:</b> <code>{esc(data['btc_price'])}</code> (<code>{esc(data['btc_change'])}</code>)\n"
        f"• <b>ETH:</b> <code>{esc(data['eth_price'])}</code> (<code>{esc(data['eth_change'])}</code>)\n\n"
        f"<blockquote expandable><b>Radar 24h:</b>\n"
        f"• Mayor subida: <code>{esc(data['top_gainer'])}</code> (<code>{esc(data['top_gainer_change'])}</code>)\n"
        f"• Mayor caída: <code>{esc(data['top_loser'])}</code> (<code>{esc(data['top_loser_change'])}</code>)\n"
        f"• Tendencia: <code>{esc(data['trending'])}</code></blockquote>\n\n"
        f"#BTC #Cripto #Chollo"
    )


def send_channel_post(photo_path_or_url: str, data: dict):
    caption = build_fixed_caption(data)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    if os.path.exists(photo_path_or_url):
        with open(photo_path_or_url, "rb") as img_file:
            payload = {
                "chat_id": CHAT_ID,
                "caption": caption,
                "parse_mode": "HTML",
            }
            response = requests.post(
                url,
                data=payload,
                files={"photo": img_file},
                timeout=30,
            )
    else:
        img_resp = requests.get(photo_path_or_url, timeout=20)
        img_resp.raise_for_status()
        payload = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML",
        }
        response = requests.post(
            url,
            data=payload,
            files={"photo": ("post_image.png", img_resp.content, "image/png")},
            timeout=30,
        )

    if not response.ok:
        print("Telegram error:", response.status_code, response.text)
        response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    sample_data = {
        "header": "CHOLLO CRYPTO · RESUMEN DEL MERCADO",
        "date_str": "Viernes, 27 nov",
        "market_cap": "$2.10T",
        "market_cap_change": "+0.1%",
        "btc_dominance": "57.9%",
        "fng_value": "11",
        "fng_label": "Miedo extremo",
        "btc_price": "$60,521.00",
        "btc_change": "+2.50%",
        "eth_price": "$1,693.31",
        "eth_change": "+2.26%",
        "top_gainer": "PIEVERSE",
        "top_gainer_change": "+17.77%",
        "top_loser": "XMR",
        "top_loser_change": "-13.01%",
        "trending": "PEJAK, FOCO, NPS",
    }

    photo_source = "https://alternative.me/crypto/fear-and-greed-index.png"
    res = send_channel_post(photo_source, sample_data)
    print("تم نشر المنشور بنجاح:", res.get("ok"))
