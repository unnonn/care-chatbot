# 習慣化アプリ (Habit Tracker)

朝・夜のタスクをチェックして集計する、単一ユーザー向けの習慣管理アプリ。
iPhoneのホーム画面にPWAとして追加して、ネイティブアプリのように使えます。

## 機能

- 朝/夜に分けたタスク管理（追加・編集・削除）
- ドラッグ＆ドロップで並び替え／朝↔夜の入れ替え
- 日付ごとのチェック（過去日付の遅れ記入も可能）
- 個別タスク集計：累計／今年／今月／先月／今週／先週／最終チェック日／最長連続／作成日／経過日数（前月・前週比%表示付き）
- 全体集計：上記サマリ＋直近12ヶ月の月次推移バーチャート＋タスク別サマリ
- 翌日記入忘れ時のメール通知（毎朝 10:00 JST、Resend 経由）
- PWA対応：iPhoneのホーム画面に追加してフルスクリーン起動可能

---

## iPhoneで使えるようになるまで

### Windowsの場合：ワンライナー自動デプロイ（推奨）

事前準備:
1. **Fly.io アカウント**を作成 → https://fly.io/app/sign-up （カード登録必須・無料枠内なら課金なし）
2. **Resend アカウント**を作成 → https://resend.com/api-keys で **API Key** を発行してコピー（`re_xxxxxxxx...`）

PowerShell（管理者でなくてOK）を開いて以下を貼り付け実行:

```powershell
iex (iwr https://raw.githubusercontent.com/unnonn/care-chatbot/claude/habit-tracking-app-qVdZm/habit_tracker/windows-deploy.ps1 -UseBasicParsing).Content
```

スクリプトが対話形式で以下を自動でやります:
- flyctl の自動インストール（既にあればスキップ）
- Fly.io ログイン（ブラウザが自動で開く）
- ソースコード自動ダウンロード（Git不要）
- アプリ作成 → 東京リージョンに永続ボリューム作成
- Resend APIキーを secret に登録
- ビルド & デプロイ
- 完了後、PCブラウザで自動オープン

入力するのは2つだけ:
- **アプリ名**（例: `habit-yourname-2026`、英数小文字とハイフン）
- **Resend API Key**（事前準備2でコピーしたもの）

完了後表示される `https://habit-xxx.fly.dev` を iPhone Safari で開いて「ホーム画面に追加」してください。

### Mac/Linux の場合

```bash
# (1) flyctl インストール
brew install flyctl   # またはMacで brew が無ければ: curl -L https://fly.io/install.sh | sh

# (2) Fly.io ログイン（ブラウザが開く）
fly auth login

# (3) リポジトリ取得 & デプロイ
git clone -b claude/habit-tracking-app-qVdZm https://github.com/unnonn/care-chatbot.git
cd care-chatbot/habit_tracker
./deploy.sh
```

`./deploy.sh` が以下を対話形式で実行: アプリ作成 → 東京ボリューム作成 → Resend キー登録 → デプロイ。

### iPhoneでホーム画面に追加

1. 表示された `https://〜.fly.dev` を iPhone Safari で開く（PCからLINE等で自分宛に送ると楽）
2. 画面下の共有ボタン（□↑）→ **「ホーム画面に追加」** → 追加
3. ホーム画面の「習慣」アイコンをタップ → フルスクリーン起動
4. アプリ内右上の歯車 → 通知先メールアドレス入力 → 保存 → 「通知テスト」で送信確認

これで毎朝 10:00 JST に前日のチェック忘れがあるとメールが届きます。

---

## ローカルで試したい場合

```bash
cd habit_tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..
uvicorn habit_tracker.app:app --reload
```

http://localhost:8000 を開く。

## 環境変数

| 変数 | 説明 |
|------|------|
| `RESEND_API_KEY` | Resend API キー（メール通知に必要） |
| `RESEND_FROM` | 送信元アドレス。デフォルト `Habit Tracker <onboarding@resend.dev>` |
| `HABIT_DB_PATH` | SQLite DB パス。Fly.io では `/data/habits.db`（自動設定済み） |
| `PORT` | サーバーポート。Fly.io では `8080`（自動設定済み） |

## API

| Method | Path | 説明 |
|--------|------|------|
| GET    | `/api/habits` | タスク一覧 |
| POST   | `/api/habits` | タスク作成 |
| PUT    | `/api/habits/{id}` | タスク更新（リネーム／時間帯変更） |
| DELETE | `/api/habits/{id}` | タスク削除（チェック履歴も削除） |
| POST   | `/api/habits/reorder` | 並び順／朝夜の一括更新 |
| GET    | `/api/checks?start=&end=` | 期間内のチェック |
| POST   | `/api/checks/toggle` | チェックのトグル |
| GET    | `/api/stats/habit/{id}` | 個別集計 |
| GET    | `/api/stats/overall` | 全体集計 |
| GET    | `/api/settings` / PUT | 通知設定 |
| POST   | `/api/notifications/test` | 通知の手動実行 |

## 別のホスティングを使う場合

`Dockerfile` を含むため、Railway / Render / Cloud Run などにもデプロイできます。
SQLiteファイルが永続化されるよう、必ず `/data` を永続ボリュームにマウントしてください。

例: Railway の場合
1. New Project → Deploy from GitHub Repo
2. Root Directory に `habit_tracker` を指定
3. Volumes タブで `/data` にボリュームをマウント
4. Variables に `RESEND_API_KEY` などをセット
