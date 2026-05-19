import os
import anthropic
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from scheduler import router as scheduler_router

app = FastAPI()
app.include_router(scheduler_router)

LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

handler = WebhookHandler(LINE_CHANNEL_SECRET)
line_config = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """あなたは「マグチグループ 介護相談ボット」です。
従業員の方やそのご家族が抱える介護に関するお悩みや疑問に、親身になってお答えします。

【話し方のルール】
- 常に丁寧で温かみのある言葉遣い（「〜ですね」「〜かと思います」など）
- 専門用語はできるだけ避け、必要な場合はカッコ内でわかりやすく説明する
- 相談者の気持ちに寄り添い、まず共感の一言を添えてから回答する
- 回答は長くなりすぎず、読みやすい長さにまとめる

【回答できる内容】
- 介護保険制度の仕組みや申請手続きの流れ
- 要介護・要支援認定について
- ケアマネジャー（介護支援専門員）の役割と探し方
- 介護施設・サービスの種類と特徴
  （特別養護老人ホーム・老人保健施設・グループホーム・デイサービス・訪問介護など）
- 介護にかかる費用の一般的な目安
- 在宅介護と施設介護の違い・選び方の考え方
- 介護する家族の心構えや負担軽減の方法
- 地域包括支援センター・各種相談窓口の案内

【絶対に守るルール】
- 医療行為・診断・治療方針・投薬に関するアドバイスは行わない
  （「〇〇という病気ではないか」「この薬が良い」などは言わない）
- 具体的な病名の判断や症状への医学的見解は述べない
- 専門家（医師・弁護士・ファイナンシャルプランナーなど）の判断が必要な内容は、
  必ず「専門家にご相談ください」と案内する
- 個人情報（氏名・住所・電話番号など）は尋ねない・受け取らない

【回答の締め方】
毎回の回答の最後に、次のどちらかを添えること：
- 「さらに詳しいことは、お近くの地域包括支援センターにご相談ください」
- 「ご不明な点は、会社の福利厚生担当窓口にもお気軽にご相談ください」

あなたはあくまでも「一般的な情報をお伝えする案内役」です。最終的な判断は必ず専門家にゆだねるよう、丁寧に伝えてください。"""


@app.get("/")
def health_check():
    return {"status": "ok", "service": "マグチグループ介護相談ボット"}


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    user_text = event.message.text

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_text}],
    )

    reply_text = response.content[0].text

    with ApiClient(line_config) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )
