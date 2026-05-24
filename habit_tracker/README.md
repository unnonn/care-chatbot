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

## iPhoneで使えるようになるまで（一番簡単な手順）

### ステップ 1: Fly.io にデプロイする（初回1回だけ・PC作業）

Mac/Linux の場合:

```bash
# (1) flyctl をインストール
curl -L https://fly.io/install.sh | sh
export FLYCTL_INSTALL="$HOME/.fly"
export PATH="$FLYCTL_INSTALL/bin:$PATH"

# (2) Fly.io にサインアップ／ログイン（クレジットカード登録あり・無料枠で運用可）
fly auth signup    # 既存アカウントなら fly auth login

# (3) このリポジトリの habit_tracker/ ディレクトリに入って実行
cd habit_tracker
./deploy.sh
```

Windows (PowerShell) の場合:

```powershell
iwr https://fly.io/install.ps1 -useb | iex
fly auth signup
cd habit_tracker
bash deploy.sh
```

`./deploy.sh` が以下を自動でやります:

1. グローバル一意なアプリ名を聞いて作成
2. Tokyo (nrt) リージョンに 1GB の永続ボリュームを作成（SQLite用）
3. Resend APIキーを聞いて secret に設定
4. ビルド & デプロイ

完了するとURL（例: `https://habit-tracker-yourname.fly.dev`）が表示されます。

### ステップ 2: iPhone Safari で開く → ホーム画面に追加

1. iPhone の Safari で上記URLを開く
2. 画面下の共有ボタン（□に↑）をタップ
3. **「ホーム画面に追加」** を選択 → 「追加」
4. ホーム画面に「習慣」アイコンが出現。タップすると Safari UI なしのフルスクリーンで起動

### ステップ 3: アプリ内で通知メールを設定

1. アプリ右上の歯車アイコンをタップ
2. 通知先メールアドレスを入力
3. 「翌日記入忘れ時にメール通知」をON → 保存
4. 「通知テスト」ボタンで実際に届くか確認

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
