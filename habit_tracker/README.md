# 習慣化アプリ (Habit Tracker)

朝・夜のタスクをチェックして集計するシンプルな単一ユーザー向け習慣管理アプリ。

## 機能

- 朝/夜に分けたタスク管理（追加・編集・削除）
- ドラッグ＆ドロップで並び替え／朝↔夜の入れ替え
- 日付ごとのチェック（過去日付の遅れ記入も可能）
- 個別タスク集計：累計／今年／今月／先月／今週／先週／最終チェック日／最長連続／作成日／経過日数（前月・前週比%表示付き）
- 全体集計：上記サマリ＋直近12ヶ月の月次推移バーチャート＋タスク別サマリ
- 翌日記入忘れ時のメール通知（毎朝 10:00 JST、Resend 経由）

## ローカル起動

```bash
cd habit_tracker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # RESEND_API_KEY を編集
# プロジェクトルートから起動（モジュール解決のため）
cd ..
uvicorn habit_tracker.app:app --reload
```

ブラウザで http://localhost:8000 を開く。

## デプロイ

このディレクトリは独立したアプリとしてデプロイ可能。`Procfile` を含むので Heroku / Railway / Render などにそのままデプロイできます。

**重要**: SQLite ファイル (`data/habits.db`) は永続ストレージにマウントしてください。Heroku のような ephemeral filesystem を使うサービスではボリュームのアタッチが必要です。

### 環境変数

| 変数 | 説明 |
|------|------|
| `RESEND_API_KEY` | Resend API キー（メール通知に必要） |
| `RESEND_FROM` | 送信元アドレス（デフォルト: `onboarding@resend.dev`） |
| `HABIT_DB_PATH` | SQLite DB パスのオーバーライド（永続ボリュームを指す） |
| `PORT` | サーバーポート（デフォルト: 8000） |

### 通知の設定

1. 起動後アプリ右上の歯車アイコン → 通知先メールアドレスを入力
2. 「翌日記入忘れ時にメール通知」をON
3. 保存後、「通知テスト」ボタンで実際に送信できるか確認

通知はスケジューラが毎朝 10:00（JST）に「前日にチェックが1件もなければ」メール送信します。

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
