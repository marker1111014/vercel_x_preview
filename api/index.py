import logging
import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot Token (需在 Vercel 專案 Settings -> Environment Variables 設定)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    logger.warning("未偵測到 TELEGRAM_BOT_TOKEN，請至 Vercel 後台設定環境變數！")

# 替換目標網域（預設使用 vxtwitter.com，亦可設定為 fixupx.com 等）
TARGET_DOMAIN = os.environ.get("TARGET_DOMAIN", "vxtwitter.com").strip()

# 精準比對 Twitter / X 連結：
# 1. 不會誤判已替換的 vxtwitter.com、fixupx.com、fxtwitter.com
# 2. 支援 mobile.twitter.com、www.twitter.com、x.com 等
twitter_link_pattern = re.compile(
    r"(?:https?:\/\/)?(?:[a-zA-Z0-9-]+\.)*?(?<![a-zA-Z0-9])(?:x|twitter)\.com(/[^\s]*)",
    re.IGNORECASE
)

def convert_text(text: str) -> str:
    if not text:
        return ""

    def repl(match):
        raw_path = match.group(1)
        trailing = ""
        # 移除句子末尾常帶有的標點符號（例如句點、驚嘆號、閉括號等），避免破壞網址
        while raw_path and raw_path[-1] in ".,!?;:)'\">]":
            if raw_path[-1] == ")" and raw_path.count("(") >= raw_path.count(")"):
                break
            trailing = raw_path[-1] + trailing
            raw_path = raw_path[:-1]

        return f"https://{TARGET_DOMAIN}{raw_path}{trailing}"

    return twitter_link_pattern.sub(repl, text)

def post_send_message(chat_id: int, text: str, reply_to_message_id: int = None) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("未設定 TELEGRAM_BOT_TOKEN，無法發送訊息")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        r = requests.post(url, json=payload, timeout=10)
        logger.info(f"sendMessage 回應: {r.status_code} {r.text}")
        if r.status_code == 400 and reply_to_message_id is not None:
            # 若因原訊息不存在/回覆權限問題導致 400，重試直接發送
            logger.warning("嘗試移除 reply_to_message_id 重新發送...")
            payload.pop("reply_to_message_id", None)
            r = requests.post(url, json=payload, timeout=10)
            logger.info(f"重試回應: {r.status_code} {r.text}")
        return r.ok
    except Exception as e:
        logger.exception("發送 Telegram 訊息時發生網路異常: %s", e)
        return False

def get_base_url():
    host_url = request.host_url.rstrip("/")
    if "localhost" not in host_url and not host_url.startswith("https://"):
        host_url = host_url.replace("http://", "https://")
    return host_url

def handle_set_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "請先至 Vercel 專案 Settings -> Environment Variables 設定 TELEGRAM_BOT_TOKEN"
        }), 400

    base_url = get_base_url()
    webhook_url = f"{base_url}/api"

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
            params={"url": webhook_url},
            timeout=10
        )
        data = r.json() if "application/json" in r.headers.get("Content-Type", "") else {"raw": r.text}
        return jsonify({
            "ok": r.ok,
            "configured_webhook_url": webhook_url,
            "telegram_response": data
        }), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def handle_webhook_info():
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "請先至 Vercel 專案 Settings -> Environment Variables 設定 TELEGRAM_BOT_TOKEN"
        }), 400

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo",
            timeout=10
        )
        data = r.json() if "application/json" in r.headers.get("Content-Type", "") else {"raw": r.text}
        return jsonify(data), r.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

def handle_telegram_update():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"status": "no_data"}), 200

        logger.info(f"收到 Telegram Update: {data}")

        # 同時支援 message, edited_message, channel_post, edited_channel_post
        message = (
            data.get("message")
            or data.get("edited_message")
            or data.get("channel_post")
            or data.get("edited_channel_post")
        )
        if not message:
            return jsonify({"status": "ignored_non_message"}), 200

        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        text = message.get("text") or message.get("caption") or ""

        if not chat_id:
            return jsonify({"status": "no_chat_id"}), 200

        # 支援 /start 指令確認機器人狀態
        if text.strip() == "/start":
            welcome_text = (
                "👋 你好！我是推特/X 預覽轉換機器人。\n\n"
                "只要在對話或群組中發送包含 x.com 或 twitter.com 的連結，"
                f"我會自動回傳可直接內嵌預覽的 {TARGET_DOMAIN} 連結！"
            )
            post_send_message(chat_id, welcome_text, message_id)
            return jsonify({"status": "handled_start"}), 200

        if not text:
            return jsonify({"status": "no_text"}), 200

        converted_text = convert_text(text)
        if converted_text != text:
            logger.info(f"網址轉換: {text} -> {converted_text}")
            post_send_message(chat_id, converted_text, message_id)

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception("處理 Webhook 請求時發生錯誤: %s", e)
        # 即使發生錯誤依然回傳 200，避免 Telegram 反覆重發阻塞
        return jsonify({"status": "error", "message": str(e)}), 200

@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def entrypoint(path):
    # GET 請求：提供服務診斷與便利工具
    if request.method == "GET":
        if path == "set_webhook":
            return handle_set_webhook()
        if path in ("webhook_info", "get_webhook_info"):
            return handle_webhook_info()

        base_url = get_base_url()
        return jsonify({
            "service": "Telegram Twitter/X Preview Bot",
            "status": "online",
            "bot_token_configured": bool(TELEGRAM_BOT_TOKEN),
            "target_domain": TARGET_DOMAIN,
            "endpoint_accessed": f"/{path}",
            "quick_tools": {
                "set_webhook_url": f"{base_url}/set_webhook",
                "check_webhook_status": f"{base_url}/webhook_info"
            },
            "manual_setup": {
                "step1": "在 Vercel 專案 Settings -> Environment Variables 新增 TELEGRAM_BOT_TOKEN",
                "step2": f"瀏覽器開啟或 curl '{base_url}/set_webhook' 完成綁定"
            }
        }), 200

    # POST 請求：接收 Telegram Webhook
    return handle_telegram_update()
