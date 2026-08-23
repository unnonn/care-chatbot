# Plaud NotePin S × 介護相談ボット 連携活用の検討

対象デバイス: [Plaud NotePin S](https://amzn.asia/d/01q1P7QI)(AIボイスレコーダー / 自動文字起こし・要約 / 話者識別 / 112言語対応 / アプリ連動)

既存アプリ: マグチグループ 介護相談ボット(LINE Bot / FastAPI / Claude API)

---

## 1. 前提整理

### 既存アプリの現状(main.py)

- LINE のテキストメッセージを受信 → Claude(claude-sonnet-4-6)が介護相談に回答 → LINE に返信
- **テキスト入力のみ**対応(音声・ファイルは未対応)
- **ステートレス**(会話履歴・データ保存なし)
- ガードレール: 医療行為への助言禁止・個人情報を扱わない・専門窓口への誘導

### Plaud NotePin S 側の連携手段

| 手段 | 内容 | 備考 |
|------|------|------|
| ① Zapier 連携 | 「文字起こし完了」「要約完了」をトリガーに、テキストを任意の宛先へ自動送信(Webhook POST 可) | Plaud 公式が提供。有料プランが前提となる可能性あり |
| ② Plaud Developer Platform | 文字起こし・要約・メタデータを JSON API で取得。Webhook・SDK あり | 法人向け。「Request Access」による申請制 |
| ③ 手動エクスポート | アプリから txt / Word / PDF / 音声を書き出し、共有シートで他アプリへ | 無料枠でも可能。自動化はされない |

---

## 2. 活用ユースケース案

### 案A: ケアマネ面談・窓口相談の「録音 → 要約 → LINEで解説」パイプライン(本命)

**シナリオ**: 従業員やその家族が、ケアマネジャーや地域包括支援センターとの面談を NotePin で録音。Plaud が文字起こし・要約 → Zapier Webhook 経由で本アプリの新エンドポイントに自動送信 → Claude が「介護相談ボット」の視点で加工し、LINE にプッシュ通知。

Claude による加工の例:

- 面談内容の平易な要約(専門用語のかみ砕き)
- 「次にやるべきこと」チェックリスト(申請手続き・持ち物・期限など)
- 面談で出た制度・サービスの補足説明
- 「次回の面談で確認すべき質問」の提案

```
NotePin S ──録音──▶ Plaud アプリ/クラウド(文字起こし・要約・話者識別)
                        │ Zapier トリガー(要約完了)
                        ▼
              POST /plaud/webhook(本アプリに新設)
                        │ Claude で介護相談ボット視点の解説・TODO化
                        ▼
              LINE push_message で本人へ配信
```

既存ボットは reply(受信への返信)のみなので、**push メッセージの送信**と、送信先 LINE ユーザー ID の紐づけ(初回に友だち登録時の userId を控える等)の実装が必要。

### 案B: 社内介護セミナー・説明会の議事録配信

福利厚生担当が説明会を NotePin で録音 → Plaud の議事録テンプレートで要約 → Claude で「従業員向けのやさしい案内文」に整形 → LINE 公式アカウントからブロードキャスト配信。話者識別により質疑応答部分を Q&A 形式に再構成できる。

### 案C: 相談ナレッジの蓄積によるボット回答品質の向上

窓口での対面相談(同意取得済みのもの)を録音・匿名化し、「よくある相談と回答」を Claude で抽出 → SYSTEM_PROMPT ないし将来的な RAG のナレッジとして反映。ボットが「マグチグループでよくある相談」に即した回答を返せるようになる。

### 案D(最小構成・開発ほぼ不要): 手動エクスポート + 長文対応

Plaud アプリから要約テキストをコピーし、そのまま LINE ボットに貼り付けて「この面談内容について次にすべきことを教えて」と聞く運用。**今日から可能**だが、以下の小改修を推奨:

- LINE の 1 メッセージ上限(5,000文字)近い長文入力への対応確認
- 「面談メモを貼り付けたら要約・TODO 化する」旨を SYSTEM_PROMPT に追記

---

## 3. 実装ロードマップ(推奨順)

| フェーズ | 内容 | 開発規模 |
|---------|------|---------|
| Phase 0 | 案D: 手動貼り付け運用 + SYSTEM_PROMPT 追記 | 数行 |
| Phase 1 | `/plaud/webhook` 新設 + Zapier 連携 + LINE push 配信(案A) | 中(1エンドポイント + userId 管理) |
| Phase 2 | 議事録ブロードキャスト(案B)、ナレッジ蓄積(案C) | 中〜大(保存層が必要) |
| Phase 3 | Plaud Developer Platform 申請による直接 API 連携(Zapier 依存を排除) | 申請次第 |

### Phase 1 の実装イメージ

```python
# main.py への追加イメージ(概略)
@app.post("/plaud/webhook")
async def plaud_webhook(request: Request):
    # Zapier からの POST(共有シークレットで検証)
    payload = await request.json()
    transcript = payload.get("summary") or payload.get("transcript")

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=MEETING_SUMMARY_PROMPT,  # 面談記録の解説・TODO化用プロンプト
        messages=[{"role": "user", "content": transcript}],
    )

    with ApiClient(line_config) as api_client:
        MessagingApi(api_client).push_message(
            PushMessageRequest(
                to=TARGET_USER_ID,  # 録音者と LINE userId の紐づけが必要
                messages=[TextMessage(text=response.content[0].text)],
            )
        )
    return {"status": "ok"}
```

---

## 4. 留意点(重要)

1. **録音の同意**: 面談相手(ケアマネ・窓口職員等)への録音同意の取得を運用ルール化すること。
2. **個人情報の扱い**: 現行ボットは「個人情報を受け取らない」方針だが、面談録には氏名・健康状態等が含まれ得る。案A/Cでは **匿名化処理(Claude で氏名等をマスク)** を Webhook 受信直後に挟むこと。Plaud クラウドは ISO 27001 / GDPR / HIPAA 等に準拠と公称しているが、社内の個人情報取扱規程との整合確認が必要。
3. **医療情報のガードレール**: 面談録の解説でも既存の「医療行為への助言をしない」ルールを新プロンプトに引き継ぐこと。
4. **コスト**: Plaud の月間文字起こし時間は無料枠に制限があり、Zapier 連携は有料プラン前提の可能性が高い。Zapier 側の有料枠も含めた月額試算を購入前に確認推奨。
5. **NotePin の「AIに質問」機能との棲み分け**: Plaud 純正機能でも録音内容への質問は可能。**本連携の付加価値は「マグチグループ固有の窓口案内・介護制度ガードレール付きで、使い慣れた LINE に届く」こと**に置く。

---

## 5. 結論

購入する価値は十分にある。まず **案D(手動運用)で効果を確認**し、有効なら **Phase 1(Zapier → Webhook → LINE push)** を実装するのが低リスク。既存コードへの追加は Webhook エンドポイント 1 本 + push 配信のみで、アーキテクチャ変更は不要。

参考リンク:
- [Plaud Zapier integration(公式サポート)](https://support.plaud.ai/hc/en-us/articles/12200669941647-Zapier-integration)
- [Plaud Webhooks by Zapier](https://zapier.com/apps/plaud/integrations/webhook)
- [Plaud Developer Platform](https://eu.plaud.ai/pages/developer-platform)
- [データエクスポート方法(公式サポート)](https://support.plaud.ai/hc/en-us/articles/51573949068697-How-to-export-my-data)
