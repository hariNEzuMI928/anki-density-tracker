# Anki Density Tracker

Ankiの学習データを自動集計し、学習の「密度」を可視化するとともに、Slackで進捗を通知するシステムです。

## 概要

このシステムは、Ankiの学習履歴を30分ごとのバケットで集計し、Googleスプレッドシートに記録します。また、月間の新規カード消化目標に対する現在の進捗を判定し、毎日決まった時間にSlackへ通知を行います。

Ankiデスクトップアプリを起動していなくても、`apy` (Anki CLI) を介してデータの同期と抽出が可能です。

## 主な機能

- **学習密度集計**: デッキごとの学習枚数と所要時間を30分単位で集計。
- **Google Sheets 連携**: 集計データをスプレッドシートに自動追記。
- **目標進捗通知**:
  - `EnglishComposition` および `FluencyTest` デッキの新規カード消化状況をチェック。
  - 今月末までの目標達成に必要な1日あたりの枚数と、当日の実績を比較してSlack通知。
- **自動同期**: `apy sync` によりAnkiWebとの同期を自動実行。
- **DBロック回避**: Ankiデスクトップアプリが起動している場合は、処理を安全にスキップ。

## 技術スタック

- **Language**: Python 3.12+ (Managed by [mise](https://mise.jdx.dev/))
- **Data Access**: [apy](https://github.com/pndurette/apy)
- **External APIs**:
  - Google Sheets API ([gspread](https://github.com/burnash/gspread))
  - Slack Incoming Webhooks
- **Automation**: macOS launchd (via mise)

## セットアップ

### 1. 依存関係のインストール

```bash
git clone <repository-url>
cd anki-density-tracker

# miseを使用してツールをセットアップ
mise install

# 仮想環境の作成とパッケージのインストール
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 環境設定

`.env.example` をコピーして `.env` を作成し、必要な情報を入力してください。

```bash
cp .env.example .env
```

`.env` の内容:
- `SLACK_WEBHOOK_URL`: Slack通知用のWebhook URL
- `SPREADSHEET_ID`: 記録先のGoogleスプレッドシートID

また、Google Sheets APIを使用するために `credentials.json` (Service Account Key) をプロジェクトルートに配置してください。

### 3. Anki プロファイルの設定

`apy` が正しくプロファイルを認識できるように設定されている必要があります。通常、`~/.config/apy/config.json` などで設定します。

## 実行方法

手動で実行する場合（miseを使用）:

```bash
mise run run
```

あるいは直接スクリプトを叩く場合:

```bash
source .venv/bin/activate
python anki_density_tracker.py
```

## 定期実行の設定 (macOS)

`launchd` を使用して、1日複数回（12:05, 17:05, 21:05, 23:05）実行するように設定されています。
設定ファイルは `$HOME/dotfiles/launchd/com.user.anki-density-tracker.plist` で管理し、`~/Library/LaunchAgents/com.user.anki-density-tracker.plist` にシンボリックリンクを貼って使用します。
内部では `mise run run` を呼び出しています。

## ライセンス

MIT
