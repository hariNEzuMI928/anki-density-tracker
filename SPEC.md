Anki学習密度分析・進捗通知システム 設計書

1. システム概要

本システムは、Ankiの学習データをバックグラウンドで集計し、学習の「密度」を可視化するとともに、月間の新規カード消化目標に対する進捗を自動通知するツールである。Ankiデスクトップアプリを起動することなく、CLIツール apy を介してデータの同期と抽出を行う。

2. アーキテクチャ構成

Core Logic: Python 3.12+ (pyenv管理)

Data Access: apy (Anki Python Library Wrapper)

Data Sync: AnkiWeb (via apy sync)

External Integration:

Google Sheets API (gspread)

Slack Incoming Webhook

Execution Environment: macOS (launchdによる定期実行)

Project Root: /Users/daisukesuzuki/Dev/anki-density-tracker

3. 機能詳細

3.1. 同期・データ抽出

apy sync コマンドにより、ローカルのSQLite DBをAnkiWebの最新状態に更新する。

実行時にAnkiアプリが起動している場合は、DBロックを避けるため処理を中断する。

3.2. 学習密度集計ロジック

調査対象デッキ:

1_Vocabulary

2_EnglishComposition

3_FluencyTest

集計単位: 30分ごとのバケット（00:00, 00:30, 01:00...）。

指標:

枚数 (Count): デッキごとに、その30分間で回答した枚数を集計。

時間 (Duration): デッキごとに、回答に要した合計時間を記録。

3.3. 目標管理・進捗判定（Slack通知）

ターゲットデッキとゴール:

2_EnglishComposition: 今月末までに全ての新規カードを完了。

3_FluencyTest: 今月末までに全ての新規カードを完了。

判定ロジック:

各デッキの「残り新規カード数」を取得。

「残り新規カード数 / 今月の残り日数」により1日あたりの必要消化枚数を算出。

**当日実績（新規着手枚数）**が「必要消化枚数」を下回っている場合、Slackで強力に促すメッセージを生成。

3.4. 外部連携

スプレッドシート: 30分ごとの時間枠を1行として追加。

複数デッキを学習した時間枠では、デッキごとに1行ずつ作成（またはDescriptionにデッキ別枚数を併記）。

Slack: 毎日21時に各ターゲットデッキの進捗（必要枚数 vs 実績）を詳細に通知。

4. 環境構築手順

4.1. 前提条件

macOS (Sequoia 15.5)

Homebrew, pyenv 導入済み

4.2. Python環境の構築

cd /Users/daisukesuzuki/Dev/anki-density-tracker
pyenv local 3.12.0
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install apy-cli gspread oauth2client requests


4.3. launchd による定期実行設定

設定ファイルは /Users/daisukesuzuki/dotfiles/launchd で管理する。
※シンボリックリンクの作成とロードは外部の管理スクリプトにて実施するため、本レポジトリでは定義ファイルの作成のみを行う。

設定ファイルパス: /Users/daisukesuzuki/dotfiles/launchd/com.daisukesuzuki.anki-density-tracker.plist

<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "[http://www.apple.com/DTDs/PropertyList-1.0.dtd](http://www.apple.com/DTDs/PropertyList-1.0.dtd)">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.daisukesuzuki.anki-density-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/daisukesuzuki/Dev/anki-density-tracker/.venv/bin/python</string>
        <string>/Users/daisukesuzuki/Dev/anki-density-tracker/anki_density_tracker.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>21</integer>
        <integer>Minute</integer>
        <integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/daisukesuzuki/Dev/anki-density-tracker</string>
    <key>StandardOutPath</key>
    <string>/Users/daisukesuzuki/Dev/anki-density-tracker/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/daisukesuzuki/Dev/anki-density-tracker/logs/stderr.log</string>
</dict>
</plist>


5. 運用上の注意

集計粒度: 10分単位よりも30分単位の方がスプレッドシート上での可読性が高く、集中セッションの区切りとして適切である。

DBロック: 21時時点でAnkiデスクトップアプリが終了していることを確認すること。
