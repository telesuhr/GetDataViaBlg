# GetDataViaBlg - LME Copper Monitor

BloombergAPIを使用してLME Copperの価格をリアルタイムで監視し、関連ニュースを表示するWindowsアプリケーションです。

## 機能

- **リアルタイム価格監視**: LME Copperの価格を2秒間隔で取得・表示
- **価格チャート**: matplotlibを使用した動的チャート表示
- **ニュースフィード**: 銅関連のニュース表示
- **デモモード**: Bloomberg API未接続時の模擬データ表示

## 必要条件

### Bloomberg API
- Bloomberg Terminal または Bloomberg Server API ライセンス
- blpapi Python ライブラリ

### Python環境
- Python 3.8以上
- 必要なライブラリ（requirements.txt参照）

## インストール

1. 必要なライブラリをインストール:
```bash
pip install -r requirements.txt
```

2. Bloomberg API (blpapi) のインストール:
```bash
# Bloomberg提供のインストーラーまたは
pip install blpapi
```

## 使用方法

1. Bloomberg Terminalを起動（Desktop API使用の場合）

2. アプリケーションを実行:
```bash
python main.py
```

3. "Start Monitoring"ボタンで監視を開始

## Bloomberg API設定

アプリケーションは以下の設定でBloomberg APIに接続します：
- Host: localhost
- Port: 8194
- Service: //blp/mktdata
- 銘柄: LME_COPPER Comdty

## デモモード

Bloomberg APIが利用できない場合、アプリケーションは自動的にデモモードで動作し、模擬的な価格データとニュースを生成します。

## ファイル構成

- `main.py`: メインアプリケーション
- `requirements.txt`: 必要なPythonライブラリ
- `README.md`: このファイル

## 注意事項

- Bloomberg APIの利用には適切なライセンスが必要です
- 実際の銘柄コードは環境に応じて調整が必要な場合があります
- ネットワーク接続とBloomberg Terminalの状態を確認してください
