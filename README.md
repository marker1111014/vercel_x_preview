# Telegram Twitter/X 連結預覽轉換機器人 (Vercel Serverless)

當使用者在 Telegram 聊天或群組中發送 X (Twitter) 連結時，Telegram 常常無法正常顯示推文的內嵌多媒體預覽。本機器人會自動將 `x.com` 或 `twitter.com` 轉換為支援完整預覽的 `vxtwitter.com` 連結。

---

## 🚀 部署至 Vercel 步驟

### 1. 將此專案匯入 Vercel
1. 前往 [Vercel 儀表板](https://vercel.com/dashboard) 點擊 **Add New...** -> **Project**。
2. 選擇並匯入您的 GitHub 專案 `vercel_x_preview`。
3. **Framework Preset** 保持預設（Other）即可。

### 2. 設定環境變數（重要！）
在 Vercel 部署頁面或專案後台：
- 進入 **Project Settings** -> **Environment Variables**。
- 新增以下環境變數：
  - **Key**: `TELEGRAM_BOT_TOKEN`
  - **Value**: 您的 Telegram Bot Token（從 [@BotFather](https://t.me/BotFather) 取得）。
  - *(選填)* **Key**: `TARGET_DOMAIN`（預設為 `vxtwitter.com`，也可改設為 `fixupx.com`）。
- 點擊 **Save**。

> ⚠️ 如果您是部署後才新增環境變數，請務必到 **Deployments** 重新 **Redeploy** 一次讓設定生效！

### 3. 設定 Telegram Webhook（最容易遺漏的一步！）
部署完成後，Vercel 會給您一個專案網址（例如：`https://your-project.vercel.app`）。  
此時 Telegram 還不知道要把訊息轉發到哪裡，您需要綁定 Webhook：

#### 方法 A：直接用瀏覽器開啟（最簡單）
直接在瀏覽器開啟：
```text
https://your-project.vercel.app/set_webhook
```
如果成功，畫面上會顯示：
```json
{
  "ok": true,
  "configured_webhook_url": "https://your-project.vercel.app/api",
  "telegram_response": {
    "ok": true,
    "result": true,
    "description": "Webhook was set"
  }
}
```

#### 方法 B：使用 curl 指令手動綁定
```bash
curl "https://api.telegram.org/bot<您的TELEGRAM_BOT_TOKEN>/setWebhook?url=https://your-project.vercel.app/api"
```

---

## 🔍 機器人「沒反應」的常見原因與排查清單

如果部署後傳連結給機器人依然沒有反應，請依照以下 5 點檢查：

### 1. 是否尚未執行 `setWebhook`？
- 機器人在 Vercel 屬於 Serverless 模式，**不會自動接收訊息**，必須先設定 Webhook。
- **檢查方式**：在瀏覽器開啟 `https://your-project.vercel.app/webhook_info`  
  若 `url` 是空的，代表尚未綁定 Webhook，請執行上方步驟 3。

### 2. `TELEGRAM_BOT_TOKEN` 是否已設定並生效？
- **檢查方式**：直接在瀏覽器訪問您的 Vercel 網址 `https://your-project.vercel.app/`。
- 檢查回傳的 JSON 中 `"bot_token_configured"` 是否為 `true`。若為 `false`，代表環境變數尚未設定或未重新部署。

### 3. 如果在「群組」中測試，是否開啟了「群組隱私模式」？
- Telegram 機器人預設開啟 **Group Privacy（隱私模式）**。
- 在此模式下，機器人**無法接收群組中的普通文字訊息**，除非是指令 `/`、@提及機器人，或回覆機器人。
- **解決方法**：
  1. 先在**與機器人的一對一私聊**中傳送 `/start` 或 X 連結測試。
  2. 若要在群組中使用，請前往 Telegram 找 [@BotFather](https://t.me/BotFather)：
     - 發送 `/setprivacy`
     - 選擇您的機器人
     - 選擇 **Disable**
     - 將機器人移出群組後重新加入即可。

### 4. 路由（Route）問題（本次更新已修復）
- 原先代碼只監聽 `/api/index`，而 Vercel 預設將請求分派至 `/api`，若未設定重寫會造成 **404 Not Found**。
- 現已新增 `vercel.json` 並支援 `/`、`/api` 等所有路徑，不論指向何處皆能正常接收。

### 5. 查看 Vercel 即時日誌（Runtime Logs）
- 進入 Vercel 專案後台 -> **Logs**（或 **Deployments** -> 點擊最新一次部署 -> **Functions** / **Runtime Logs**）。
- 在 Telegram 發送一則訊息，觀察是否有即時 Log 印出：
  - 若完全沒有 Log：代表 Telegram 沒有將請求發送到 Vercel（Webhook 網址有誤或 Telegram 封鎖）。
  - 若有收到 Update 但 sendMessage 報錯：Log 中會印出 Telegram API 回傳的具體錯誤訊息（例如 Token 錯誤或 400 Bad Request）。

---

## 🛠 本地測試
```bash
# 安裝相依套件
pip install -r requirements.txt

# 設定環境變數
export TELEGRAM_BOT_TOKEN="your_token_here"

# 啟動服務
python api/index.py
```
