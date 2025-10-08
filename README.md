# AI見積システム (PDF → OCR → マッチング)

本リポジトリは PDF からのオフライン OCR、テキスト解析、CSV 照合を一気通貫で行う Web アプリです。FastAPI + React(TypeScript) の 2 層構成で、すべてローカル環境で動作し外部 API には依存しません。

## システム構成

```
project/
  backend/
    app/
      main.py              # FastAPI エントリーポイント
      ocr_backend.py       # YomiToku OCR ラッパー
      extract.py           # PDF 文字抽出 & OCR フォールバック
      match.py             # CSV マッチングロジック
      utils.py             # 正規化・トークン抽出ユーティリティ
      models.py            # Pydantic モデル
      storage/             # タスクごとの一時ディレクトリ
      sample_db.csv        # サンプル DB CSV
      sample_invoice*.pdf  # サンプル PDF
    requirements.txt
    README.md
  frontend/
    index.html
    src/
      main.tsx
      App.tsx
      api.ts
      components/
        *.tsx
    package.json
    vite.config.ts
```

## 必要環境

- Python 3.11+
- Node.js 18+
- Bun (最新安定版)
- uv (Python パッケージマネージャ)

### Poppler のインストール

- macOS: `brew install poppler`
- Ubuntu: `sudo apt update && sudo apt install poppler-utils`

### YomiToku モジュールの準備

1. Python 環境で `uv pip install yomitoku`
2. YomiToku 公式ドキュメントに従い、使用するモデルファイルをローカルキャッシュに配置してください。
   - 例: `~/.cache/yomitoku` 配下に必要モデルを展開
   - 事前に配置しておくことで実行時のオンラインアクセスを完全に遮断できます。
3. `python -c "import yomitoku; print('YomiToku OK')"` でインポート確認

## セットアップ手順

### 1. リポジトリを取得

```bash
git clone <this-repo>
cd mitsumori-ai
```

### 2. バックエンド

```bash
cd backend
uv init  # 初回のみ、仮想環境作成
uv pip install -r requirements.txt
uvicorn app.main:app --reload
```

デフォルトでは `http://127.0.0.1:8000` で起動します。

### 3. フロントエンド

別ターミナルで以下を実行します。

```bash
cd frontend
bun install
bun run dev
```

Vite のデフォルトポートは `5173` です。

## API エンドポイント一覧

| メソッド | パス | 説明 |
| --- | --- | --- |
| POST | `/api/upload` | DB CSV & PDF 群をアップロードし処理ジョブを生成 |
| GET | `/api/status/{task_id}` | 進捗率・統計値を取得 |
| GET | `/api/results/{task_id}` | マッチ結果 (JSON + CSV ダウンロード URL) |
| GET | `/api/failures/{task_id}` | 未ヒット一覧 |
| POST | `/api/retry` | 任意トークンを再照合 |
| GET | `/api/download/{task_id}?type=results|failures` | CSV をダウンロード |

## 実行デモ手順

1. フロントエンド画面を開き、左サイドの **DB CSV** エリアに `backend/app/sample_db.csv` をアップロード
2. **PDFs** エリアに `backend/app/sample_invoice1.pdf` と `sample_invoice2.pdf` をドラッグ & ドロップ
3. 「処理を開始する」をクリック
4. 進捗バーと統計カードを確認、完了後に「結果一覧」「失敗一覧」タブで確認
5. 右上のボタンから `results.csv` と `failure.csv` をダウンロード

## よくあるエラーと対処

| 症状 | 対処 |
| --- | --- |
| `Poppler not installed` 等 | Poppler が未導入、または PATH 未設定です。上記コマンドでインストールし、シェルを再読み込みしてください。 |
| `YomiTokuモジュールが見つかりません` | `uv pip install yomitoku` を実行し、さらにローカルモデルを事前配置してください。 |
| `OCR処理に失敗しました` | モデルディレクトリの権限・配置を再確認し、実行ユーザーが読み取り可能であることを確認してください。 |
| `onnxruntime` に関する警告 | 本システムでは不要です。YomiToku の依存として不要ライブラリを導入しないよう注意してください。 |
| `storage` ディレクトリ書き込み不可 | `backend/app/storage` の権限を確認し、必要に応じて `chmod 755 backend/app/storage` を実行してください。 |

## テスト

簡易ユニットテストは以下で実行できます。

```bash
cd backend
uv pip install pytest
pytest
```

`tests/test_utils.py` では正規化とトークン抽出の挙動を検証しています。

## ライセンス

社内用途を想定したサンプル実装です。商用利用時は各依存ライブラリのライセンスをご確認ください。
