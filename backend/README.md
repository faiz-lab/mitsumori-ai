# Backend Setup

バックエンドは FastAPI + uvicorn で動作します。`requirements.txt` に必要な依存がまとまっているため、uv を用いて以下の通りセットアップしてください。

```bash
uv init
uv pip install -r requirements.txt
uvicorn app.main:app --reload
```

OCR は `yomitoku.DocumentAnalyzer` を利用します。必ずローカルにモデルファイルを配置し、オフラインで動作するよう準備してください。
