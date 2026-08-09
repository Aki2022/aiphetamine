---
id: SPEC-aiphetamine-mvp
status: active
created_at: 2026-07-19
updated_at: 2026-07-20
related_guides: []
affected_workstreams: []
---

# AIphetamine — Product Requirements Document

## 1. 文書情報

- プロダクト名: AIphetamine
- 文書種別: Product Requirements Document
- 対象バージョン: MVP
- 対象プラットフォーム: macOS 15.7.5 以降
- 対象CPU: Apple Silicon
- 実装言語: Python
- 配布形態: GitHubでソース公開
- App Store公開: 対象外
- Xcode利用: 対象外
- 初期対応プロバイダ: Claude Codeのみ
- Codex対応: 将来拡張
- 作成目的: 開発者またはAIコーディングエージェントが、本書と `architecture.md` を基に自律的に設計・実装・検証できる状態を作る

## 2. 背景

Claude Codeを長時間利用していると、5時間利用制限に到達してセッションが停止することがある。人間が作業中であれば、制限解除後に同じセッションを再開し、`Continue`を送れば作業を継続できる。

しかし、深夜や離席中は人間が再開操作を行えないため、長時間タスクが停止したままになる。特に、調査、実装、テスト、文書更新などをClaude Codeへ継続的に任せている場合、制限解除後もセッションが再開されないことで数時間単位の空白が生じる。

AIphetamineは、Claude Codeのrate limit到達をHookで検知してローカルJSONイベントとして保存し、ユーザーが明示的に選択したセッションに限り、2時間ごとの固定時刻に公式のresumeコマンドを実行する軽量なmacOSメニューバーアプリである。

## 3. プロダクトの目的

AIphetamineの目的は、ユーザーが明示的に指定したClaude Codeセッションについて、5時間利用制限が解除された後に公式resumeコマンドを起動し、固定メッセージ`Continue`を引き渡すことである。MVPはClaude Code内部で実際のタスク処理が継続したことまでは保証しない。

本プロダクトは、Claude Code全体の利用状況を管理するダッシュボードではない。AIエージェントを汎用的に自律運転する仕組みでもない。rate limitで停止したセッションを、最小限の仕組みで再開することだけに集中する。

## 4. プロダクト原則

### 4.1 明示的なオプトイン

新しく検出されたセッションは、必ず監視OFFで表示する。ユーザーがチェックしたセッションだけを自動再開対象とする。

### 4.2 アプリ稼働中のみ動作

AIphetamineが起動していない間は、監視、再開、状態保持を一切行わない。

### 4.3 永続状態を持たない

監視対象のチェック状態はメモリ上だけに保持する。アプリ終了またはMac再起動後には失われる。

候補発見イベントは、セッションを候補一覧へ再構成するための入力であり、監視対象のチェック状態や有効化期限を表す永続状態ではない。

### 4.4 JSONは状態DBではなくイベント

JSONファイルは「このセッションがrate limitに到達した」というイベントを表す。`running`、`completed`、`retry_count`などのアプリ状態はJSONに持たせない。

### 4.5 単純性を優先

解除時刻、利用率、週次制限、通知、承認応答、プロンプト解析などはMVPに含めない。

### 4.6 ドメイン用語

- 候補セッション: AIphetamineが発見し、ユーザーが自動再開対象に指定できるClaude Codeセッション
- 有効化セッション: 候補セッションのうち、ユーザーが自動再開を明示的にONにしたセッション
- rate limitイベント: 有効化状態とは独立した、「対象セッションがrate limitへ到達した」という単発イベント

候補セッションの発見、有効化状態、rate limitイベントを同一概念として扱わない。

## 5. 対象ユーザー

主な対象ユーザーは、macOS上でClaude Codeを長時間利用し、深夜や離席中にも開発や調査を継続させたい個人開発者である。

想定環境:

- Apple Silicon Mac
- macOS 15.7.5以降
- Claude Code CLI導入済み
- Python導入済み
- ターミナルまたはIDE内ターミナルからClaude Codeを利用
- tmuxは前提としない
- 同一プロジェクト内で複数のClaude Codeセッションを並行実行する場合がある
- 10セッションまでをMVPの動作保証・テスト規模とする

## 6. 代表ユースケース

### 6.1 深夜の自動再開

1. ユーザーがClaude Codeに長時間の実装タスクを依頼する。
2. AIphetamineがrate limit到達前のセッションを候補セッションとして表示する。
3. ユーザーが離席前にそのセッションをチェックし、有効化する。
4. Claude Codeが23時台に5時間利用制限へ到達する。
5. Claude Code Hookがrate limitイベントJSONを作成する。
6. AIphetamineは次の固定巡回時刻にresumeコマンドを実行する。
7. 制限が解除済みなら、Claude Codeが同じセッションを再開して`Continue`を受け取る。
8. まだ制限中なら、Claude Code Hookが再びrate limitイベントJSONを生成する。
9. AIphetamineは次の2時間後に同じセッションを再試行する。
10. 制限解除後、作業が再開される。

### 6.2 複数セッションの選択

1. 複数のClaude Codeセッションがrate limitへ到達する。
2. AIphetamineは各セッションを別行で表示する。
3. ユーザーは自動再開したいセッションだけをチェックする。
4. チェックされていないセッションには何もしない。

### 6.3 アプリ停止中

1. AIphetamineが終了している間にClaude Codeがrate limitへ到達する。
2. Hookがrate limitイベントまたは候補発見イベントを作成する可能性がある。
3. AIphetamineは何もしない。
4. 次回起動時、12時間以内の正当なrate limitイベントは保持し、期限切れ・不正・processing・一時ファイルだけを削除する。
5. 既存の候補発見イベントは候補一覧へ取り込み、必ずチェックOFFで表示する。候補記録のないrate limitイベントは候補へ再構成するが、同一セッションの重複やアカウント不一致がある場合は再構成しない。
6. 起動直後はresumeせず、ユーザーがチェックしたセッションだけを次回の固定時刻の対象とする。

## 7. スコープ

### 7.1 MVPに含む

- Claude Codeのrate limitイベントJSONの検出
- 1セッション1JSON
- 10件までの候補セッション表示を動作保証・テスト対象とする
- 11件以上も発見分を除外せず表示するが、性能とレイアウトは保証外とする
- メニューバーUI
- セッション単位のチェックボックス
- 新規セッションはデフォルトOFF
- rate limit到達前の候補セッションの発見と表示
- 離席前に候補セッションを自動再開対象として有効化
- アプリ起動中のみチェック状態を保持
- 2時間ごとの固定時刻巡回
- 候補発見、rate limitイベント検出、resume判定を同じ固定巡回で実行
- 次の固定時刻まで待機し、起動直後には実行しない
- `claude -p --resume <session_id> "Continue"` の実行
- 実行対象JSONの安全な一時退避
- resumeコマンドを起動できた場合のJSON削除
- resume起動失敗時のJSON復元
- 同一session_idのJSON再生成時にチェック状態を維持
- 1回の有効化につき12時間の有効期限
- 12時間経過時の自動OFF
- 起動時の既存JSON削除
- Dockアイコン非表示
- Launch at LoginのON/OFF
- 7日分のログ保存
- GitHub上でのソース公開
- ユーザー自身によるclone・依存導入・起動

### 7.2 MVPに含まない

- Codex対応
- 週次制限
- 月次制限
- 解除時刻の取得
- 5時間枠の利用率表示
- 通知
- App Store配布
- 自動アップデート
- コード署名・公証
- Xcodeプロジェクト
- 設定ウィンドウ
- Dockアプリ
- tmux連携
- Terminalへのキー入力注入
- 元のClaude Codeプロセスへの直接入力
- 承認待ちへの自動回答
- 質問への自動回答
- 危険コマンドの自動承認
- プロンプト内容の解析
- セッション出力のキーワード解析
- 永続DB
- スリープ防止
- ログアウト中の動作
- Mac再起動前の監視状態復元

## 8. 機能要件

## 8.1 アプリ起動

AIphetamine起動時に、以下を実行する。

1. `candidates`、`rate_limits`、`logs`ディレクトリを作成する。存在する場合は再利用する。
2. 各ディレクトリの所有者、権限、symlinkでないことを検証する。
3. `rate_limits`ディレクトリ内の12時間以内の有効なrate limitイベントは保持し、古い・不正なイベントと`.processing`ファイルを削除する。
4. 既存の候補発見イベントを候補一覧へ取り込む。
5. メモリ上の`(session_id, account_name)`集合と有効化期限を空にする。
6. メニューバーUIを表示する。取り込んだ候補はチェックOFFとする。
7. 次の2時間境界を計算する。
8. 起動直後のresume処理は行わず、次の境界時刻まで待つ。

例:

- 21:10起動 → 22:00に初回巡回
- 22:00ちょうどに起動 → 実装上の丸め規則に従い、次の00:00を初回巡回とする
- 23:45起動 → 翌00:00に初回巡回

## 8.2 固定巡回時刻

巡回時刻はmacOSのローカルタイムに従い、以下とする。

```text
00:00
02:00
04:00
06:00
08:00
10:00
12:00
14:00
16:00
18:00
20:00
22:00
```

タイムゾーン変更、スリープ復帰、時計変更が発生した場合は、次回スケジュールをローカル時刻から再計算する。

アプリが起動していない時刻の巡回は補完しない。

各巡回では、候補発見イベントの取り込み、rate limitイベントの検出、選択済みセッションのresume判定を行う。常時ファイル監視や短周期のUI更新ポーリングは行わない。

新しい候補セッションはイベント作成後の次回巡回で初期OFFとして表示される。ユーザーがONにした後、次の固定巡回から自動resume対象になる。このため、候補表示まで最大2時間、選択後のresume判定まで最大2時間を許容する。

## 8.3 JSONイベントの監視

監視ディレクトリ:

```text
~/.local/share/aiphetamine/rate_limits/{main,alias,unknown}/
```

Hookは、rate limit到達時に1セッション1ファイルのJSONを作成する。

推奨ファイル名:

```text
<account-scope>/<session_key>.json
```

AIphetamineはディレクトリ内の`.json`ファイルを検出し、内容を検証して一覧へ反映する。

同一アカウントスコープの同一session_idのJSONが再生成された場合、既存の同一セッションとして扱う。アカウントをまたぐ同一session_idは曖昧として除外する。

rate limitイベントJSONは候補セッションの発見情報や有効化状態の保存先として兼用しない。

候補セッションはClaude Code Hookから自動発見する。利用可能なHookイベント、`session_id`、`project_path`、表示名候補の取得可否は本実装前の技術スパイクで確認する。

必要情報をHookから取得できない場合のみ、ユーザーによる手動登録をフォールバック候補として評価し、成立する方式を本実装前に本書へ反映する。

## 8.4 セッション一覧

メニューバーのドロップダウンに、検出済みセッションを表示する。

各セッション行に表示する情報:

- チェックボックス
- 人間向けセッション名
- プロジェクト名

プロバイダ名は表示しない。MVPはClaude Code専用であるため、`Claude`表示も不要とする。

表示名の優先順位:

1. JSONの`session_name`
2. JSONの`project_name`
3. `project_path`末尾のディレクトリ名
4. `session_id`先頭8文字

プロジェクト名の優先順位:

1. JSONの`project_name`
2. `project_path`末尾のディレクトリ名
3. 非表示

`session_name`と`project_name`の表示結果が他の候補セッションと重複する場合に限り、各行の末尾へ`session_id`先頭8文字を付けて識別する。重複しない候補には表示しない。

## 8.5 監視対象の選択

- 新規の候補セッションは必ずOFF
- rate limit到達前でも候補セッションを選択可能
- ユーザーがチェックした`(session_id, account_name)`をメモリ上の集合に追加
- ユーザーがチェックを外した`(session_id, account_name)`を集合から削除
- 永続化しない
- アプリ終了時に消失
- Mac再起動後にも復元しない

JSONが一度削除された後、同じ`(session_id, account_name)`のJSONが再生成された場合は、アプリ起動中に限り、以前のチェック状態を維持する。同じsession_idでもアカウントが異なる場合は状態を引き継がない。

明示的なセッション終了Hookを受信した場合は、該当session_idを候補一覧と監視対象集合から削除する。終了を確認できない場合は、一時停止や通知欠落を終了と推測せず、ユーザーがチェックを外すかアプリが終了するまで保持する。

有効化セッションごとに有効化時刻をメモリ上で保持する。1回の有効化は12時間で失効し、候補セッションを一覧へ残したまま自動的にチェックOFFへ戻す。行内に`有効期限切れ`と表示してログにも記録する。ユーザーが再度ONにした場合は表示を解除し、その時点から新しい12時間を開始する。有効化時刻と期限は永続化しない。

12時間はスリープ中も経過する実時間として扱う。Macの復帰時は、有効期限切れの判定と自動OFFをresume判定より先に実行する。タイムゾーン変更によって期限の長さは変えない。

## 8.6 Resume対象判定

固定巡回時刻に、以下をすべて満たすJSONだけを処理する。

- JSONが構文的に正しい
- `schema_version`が対応範囲内
- `reason == "rate_limit"`
- `session_id`が空でない
- `project_path`が空でない
- `project_path`が存在する
- 候補セッションとして記録された`project_path`と一致する
- `(session_id, account_name)`がメモリ上の監視対象集合に含まれる
- イベントと候補のallowlisted `account_name`が存在し、一致する
- メニュー選択が`(session_id, account_name)`単位で有効である
- 同一session_idが現在処理中でない
- 対象ファイルが`.json`である
- `.processing`ではない

同じsession_idでも、候補セッションとrate limitイベントの`project_path`が一致しない場合は、イベントをclaimせずresumeを実行しない。候補行に`パス不一致`と表示してログへ記録する。復旧には候補セッションの再登録と、ユーザーによる再度の有効化を必要とする。

## 8.7 Resume実行

実行コマンド:

```bash
claude -p --resume "<session_id>" "Continue"
```

実行時のカレントディレクトリ:

```text
project_path
```

送信文字列:

```text
Continue
```

固定値とし、ユーザー設定は設けない。

AIphetamineは、元のClaude Codeプロセスへ入力を注入しない。公式resumeコマンドを新規CLIプロセスとして起動し、既存セッションIDを再開する。

## 8.8 JSONの処理中保護

二重実行を防ぐため、resume前に対象ファイルを原子的にrenameする。

```text
<account-scope>/<session_key>.json
→
<account-scope>/<session_key>.processing
```

`.processing`ファイルは通常の一覧および巡回対象から除外する。

## 8.9 Resume起動成功時

Pythonのプロセス生成APIが正常にプロセスを開始できた場合、AIphetamineはその時点でresume起動成功とみなす。

その後:

1. `.processing`ファイルを削除する。
2. session_idのチェック状態はメモリに残す。
3. ログへ実行情報を記録する。
4. 同じsession_idのJSONがHookによって再生成されるかを待つ。

Claude Codeがまだrate limit中であれば、Hookが同一session_idのrate limitイベントJSONを再生成することを期待する。

JSONが再生成された場合、次の固定巡回時刻に再試行する。

JSONが再生成されなければ、一覧から対象セッションが消え、再試行しない。

## 8.10 Resume起動失敗時

次のようなローカル起動エラーが発生した場合:

- `claude`コマンドが見つからない
- 実行権限がない
- `project_path`へ移動できない
- subprocess生成に失敗
- OSレベルの実行エラー

処理:

1. `.processing`を元の`.json`へ戻す。
2. エラーをログに記録する。
3. チェック状態は維持する。
4. 次の固定巡回時刻に再試行する。

候補行には、生のエラー内容を表示せず、`起動失敗`とだけ表示する。詳細はサニタイズしたエラー分類としてログへ記録する。

## 8.11 セッション終了と削除

MVPでは、通常稼働中の全Claude Codeセッションを一覧化しない。

rate limitイベントJSONが存在するセッションだけを表示する。

以下の場合、そのセッションは一覧から消える。

- resume実行後にJSONを削除した
- Hookまたは外部処理がJSONを削除した
- ユーザーがアプリを終了した
- AIphetamine再起動時の初期化で削除した

アプリ起動中の監視対象`(session_id, account_name)`集合は、JSONが一時的に消えても保持する。ただしUI一覧にはJSONが存在するセッションだけを表示する。

## 8.12 Launch at Login

メニューバーに以下の項目を設ける。

```text
Launch at Login
```

ON/OFFのメニュー操作は設定生成の状態だけを扱う。LaunchAgentの登録・解除や
既存plistの削除は実施せず、生成済みplistを利用者が手動で`launchctl`
へ登録・解除する。

ログイン起動後も、通常起動と同様に既存JSONを削除し、次の2時間境界まで待つ。

## 8.13 終了

メニューに`Quit AIphetamine`を設ける。

終了時:

- 監視対象`(session_id, account_name)`集合を破棄
- スケジューラを停止
- 実行中のresumeプロセスは強制終了しない
- JSONは終了時には削除しない
- 次回起動時に既存JSONを削除する

## 9. JSON仕様

JSONはClaude Code Hookが作成するrate limitイベントである。

### 9.1 必須項目

```json
{
  "schema_version": 1,
  "reason": "rate_limit",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_path": "<absolute-project-path>",
  "updated_at": "2026-07-20T01:42:15+09:00"
}
```

### 9.2 任意項目

```json
{
  "session_name": "implement-dashboard",
  "project_name": "research-platform",
  "transcript_path": "<transcript-path>"
}
```

### 9.3 完全例

```json
{
  "schema_version": 1,
  "reason": "rate_limit",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_name": "implement-dashboard",
  "project_name": "research-platform",
  "project_path": "<absolute-project-path>",
  "transcript_path": "<transcript-path>",
  "updated_at": "2026-07-20T01:42:15+09:00"
}
```

### 9.4 書き込み要件

Hookは途中書き込みされたJSONをAIphetamineが読まないよう、原子的に書き込む。

推奨手順:

1. 一時ファイルへ書く
2. flush
3. 必要に応じてfsync
4. `<account-scope>/<session_key>.json`へrename

### 9.5 不正JSON

不正JSONはresume対象にしない。

- UI上では個別内容を表示せず、メニュー末尾に`無効なイベント N件（ログ参照）`と件数だけを表示する
- ログへ匿名化した相関IDとサニタイズした理由を記録する
- 自動削除しない
- 次回巡回でも再検証する

## 10. メニューバーUI要件

## 10.1 基本構成

Dockアイコンを表示せず、メニューバーのみで動作する。

ドロップダウン構成例:

```text
AIphetamine

☐ implement-dashboard
   research-platform

☑ write-documentation
   aiphetamine

────────────
☑ Launch at Login
Quit AIphetamine
```

## 10.2 アイコン状態

最低限、次の2状態を持つ。

### 通常

- チェック済みrate limitセッションがない
- またはJSONが存在しない

### 待機中

- チェック済みrate limitセッションが1件以上存在する

処理中専用アイコンやエラー専用アイコンはMVPでは不要。

## 10.3 UI更新

以下のタイミングでメニューを更新する。

- 固定巡回での候補発見イベント取り込み
- 固定巡回でのrate limitイベント検出、削除、更新
- チェック状態変更
- resume処理開始
- resume処理完了
- 起動時初期化後

## 11. ログ要件

ログ保存先:

```text
~/.local/share/aiphetamine/logs/
```

日次ローテーションを行い、7日分を保持する。

記録対象:

- アプリ起動・終了
- 起動時に削除したイベント件数
- 次回巡回予定時刻
- 巡回開始・終了
- 検出イベント件数
- JSONパース結果
- バリデーションエラー
- ユーザーのチェックON/OFF
- `.json`から`.processing`へのrename
- resumeプロセスの起動成否
- 匿名化したセッション相関ID
- サニタイズしたエラー分類
- `.processing`削除
- `.json`復元
- Launch at Loginの変更
- サニタイズしたエラー分類（生の例外とスタックトレースは記録しない）

プロンプト本文、作業内容、resumeプロセスのstdout/stderrは取得・保存しない。固定送信文字列`Continue`はログへ記録してよい。

ローカルの絶対パス、ユーザー名、生のsession_idはログへ記録しない。セッションの相関が必要な場合は、アプリ実行中だけ有効な匿名化識別子を利用する。

## 12. 非機能要件

### 12.1 軽量性

- 常駐時CPU使用率を実質ゼロに近づける
- ポーリングは固定時刻の処理だけ
- 常時ファイル監視と短周期ポーリングを行わない
- メモリ使用量を最小限にする

### 12.2 信頼性

- 同一JSONを二重実行しない
- JSON処理中にクラッシュしても、`.processing`が残ることで二重処理を防ぐ
- 起動時に残存`.processing`を削除する
- 不正JSONでアプリ全体を停止しない
- 1セッションの失敗が他セッションへ影響しない
- 自動resumeの有効化は12時間を超えて継続しない

### 12.3 セキュリティ

- ネットワーク通信を追加しない
- 外部サーバーへログを送らない
- shell文字列連結を避け、引数配列でsubprocessを起動する
- session_idやproject_pathをシェル展開しない
- JSONのproject_path存在確認を行う
- 固定メッセージ以外をClaudeへ送らない
- ローカルの絶対パス、ユーザー名、生のsession_idをログへ出力しない

### 12.4 保守性

- UI、スケジューラ、JSONリポジトリ、resume実行、ログイン起動を分離する
- Claude Code固有処理をアダプターとして隔離する
- 将来Codex対応を追加できる構造にするが、MVPでは抽象化を過剰にしない

## 13. 受け入れ基準

### AC-01 起動時リセット

Given rate_limitsディレクトリに既存のrate limitイベントがある
And candidatesディレクトリに既存の候補発見記録がある
When AIphetamineを起動する
Then 12時間以内の有効なrate limitイベントは保持される
And 古い・不正なrate limitイベントと`.processing`は削除される
And 候補発見イベントは候補一覧へ取り込まれる
And チェック状態は空になる
And 起動直後にresumeは実行されない

### AC-02 次回固定時刻

Given AIphetamineを21:10に起動する
When アプリが正常起動する
Then 初回巡回は22:00に予約される

### AC-02A イベント反映周期

Given 有効な候補発見イベントまたはrate limitイベントが作成される
When 次の固定巡回時刻になる
Then イベントが候補一覧または待機状態へ反映される
And 固定巡回前の即時反映は要求しない

### AC-03 新規セッションはOFF

Given 新しいrate limit JSONが作成される
When AIphetamineが検出する
Then セッションは一覧へ表示される
And チェックはOFFである

### AC-04 未選択セッションは実行しない

Given rate limit JSONが存在する
And セッションが未選択である
When 固定巡回時刻になる
Then resumeコマンドは実行されない

### AC-05 選択セッションを再開

Given 有効なrate limit JSONが存在する
And セッションが選択されている
When 固定巡回時刻になる
Then JSONは`.processing`へrenameされる
And `claude -p --resume SESSION_ID "Continue"`がproject_pathで起動される
And MVPの成功判定はresumeプロセスの生成成功である

### AC-06 起動成功時にJSON削除

Given resumeプロセスが生成できる
When subprocess起動が成功する
Then `.processing`は削除される
And `(session_id, account_name)`の選択状態はメモリに残る

### AC-07 Hook再生成時に再試行

Given 選択済み`(session_id, account_name)`のJSONがresume後に再生成される
When 次の固定巡回時刻になる
Then チェックONのまま同じresume処理が再実行される

### AC-08 起動失敗時に復元

Given resumeプロセス生成に失敗する
When エラーが発生する
Then `.processing`は元の`.json`へ戻される
And エラーがログに記録される
And 次回巡回対象として残る

### AC-09 複数セッション

Given 複数のrate limit JSONが存在する
And 一部だけ選択されている
When 固定巡回時刻になる
Then 選択済みセッションだけが処理される

### AC-09A 11件以上の候補

Given 11件以上の候補セッションが発見される
When 候補一覧を更新する
Then 発見済み候補を件数上限によって除外しない
And 11件以上での性能とレイアウト品質はMVPの保証対象外とする

### AC-09B 同名セッションの識別

Given 複数の候補セッションでsession_nameとproject_nameの表示結果が同じである
When 候補一覧を表示する
Then 各行の末尾にsession_id先頭8文字を表示する
And 重複しない候補にはsession_idを表示しない

### AC-10 Launch at Login

Given Launch at LoginをONにする
When 設定変更が成功する
Thenユーザー用LaunchAgentが有効になる

### AC-11 自動resume有効期限

Given セッションが有効化されている
And 有効化から12時間が経過する
When 有効期限を判定する
Then セッションは自動的にチェックOFFへ戻る
And 行内に`有効期限切れ`と表示される
And 期限切れがログへ記録される
And 以後はユーザーが再度ONにするまで自動resumeしない

### AC-11A スリープ中の期限経過

Given セッションが有効化された状態でMacがスリープする
And スリープ中を含めて有効化から12時間が経過する
When Macが復帰する
Then resume判定より先にセッションをチェックOFFへ戻す
And 自動resumeを実行しない

### AC-13 project_path不一致

Given 有効化時の候補セッションと同じsession_idのrate limitイベントが存在する
And 両者のproject_pathが異なる
When 固定巡回時刻になる
Then イベントはclaimされない
And resumeは実行されない
And 候補行に`パス不一致`と表示される
And 不一致がログへ記録される

### AC-14 不正イベント表示

Given 不正または未対応のイベントが1件以上存在する
When 固定巡回でイベントを検証する
Then resume対象にしない
And メニュー末尾に無効イベントの件数だけを表示する
And イベント内容、ローカルパス、生のsession_idはUIへ表示しない

### AC-15 resume出力を保存しない

Given AIphetamineがresumeプロセスを起動する
When Claude Codeがstdoutまたはstderrへ出力する
Then AIphetamineはその内容を取得・保存しない
And アプリログには起動成否、匿名化した相関ID、サニタイズしたエラー分類だけを記録する

### AC-16 ローカル起動失敗表示

Given 有効化セッションのresumeプロセス生成に失敗する
When 候補一覧を更新する
Then 候補行に`起動失敗`と表示する
And 生のエラー内容、ローカルパス、生のsession_idは表示しない

## 14. 成功指標

MVPの成功は、次を満たすことで判定する。

- rate limit到達後、ユーザーが選択したセッションだけについてresumeプロセスが起動され、固定メッセージ`Continue`が引き渡される
- 制限解除前のresumeで再度rate limitになった場合、Hook再生成により次回も自動再試行される
- 深夜に人間が操作しなくても、制限解除後に同一セッションのresumeプロセスへ`Continue`が引き渡される
- Claude Code内部で実際のタスク処理が継続したかどうかは、MVPの保証範囲外とし、技術スパイクと手動E2Eテストで観測する
- 未選択セッションへ誤送信しない
- アプリ終了中には何もしない
- Mac再起動後には監視状態を引き継がない

## 15. 技術検証ゲート

本実装前に、以下を必ず実機検証する。

### Spike 1: StopFailure rate_limit Hook

確認事項:

- rate limit到達時にHookが発火する
- session_idを取得できる
- cwdまたはproject_pathを取得できる
- 非対話resume実行時にもHookが利用できる
- 同一session_idで再度JSONを書ける

### Spike 1A: 候補セッションの自動発見Hook

確認事項:

- rate limit到達前に候補セッションを通知できるHookイベントがある
- session_idとproject_pathを取得できる
- 表示名候補を取得できる
- 同一セッションの通知を安全に重複排除できる
- セッションの明示的な終了を通知できるHookイベントがある
- 成立しない場合に手動登録へフォールバックできる

### Spike 2: 公式resumeコマンド

確認事項:

```bash
claude -p --resume "<session_id>" "Continue"
```

- 既存セッション履歴を再開する
- 非対話で実行できる
- project_pathをcwdにして動作する
- 元のCLIプロセスが終了していても動作する
- 元のCLIプロセスが残っている場合の競合挙動

### Spike 3: rate limit中の再resume

最重要仮説:

1. rate limitイベントJSONがある
2. AIphetamineがresumeを実行する
3. まだrate limit中である
4. StopFailure(rate_limit) Hookが再度発火する
5. 同一session_idのJSONが再生成される

この仮説が成立すれば、出力解析や終了コード判定は不要である。

### Spike 4: フォールバック判断

Spike 3が成立しない場合のみ、以下の順で代替手段を評価する。

1. Claude CLIが返す構造化終了コード
2. Claude CLIが返す構造化エラー
3. transcriptまたはローカルイベント

stdout/stderrの取得、保存、キーワードマッチは代替手段に含めない。構造化シグナルだけで安全に成立しない場合は本実装を開始せず、要件を再度grillする。

## 16. 将来拡張

- Codex対応
- プロバイダ別アダプター
- 巡回間隔設定
- 利用率表示
- 解除予定時刻表示
- 週次制限対応
- 通知
- 手動Resume
- ログビューア
- セッション履歴
- GitHub Releases用パッケージ

## 17. Impact on Existing System

- `architecture.md`と実装は、rate limitイベントだけでなく候補発見・終了イベントを扱う構成へ更新済みである。
- 選択状態、12時間の有効期限、期限切れ表示、パス不一致表示、起動失敗表示は実装済みである。
- 短周期のUIスキャンは採用せず、2時間固定巡回へ統合している。
- stdout/stderr、ローカルパス、生のsession_idを保存しないサニタイズ済みロギングを実装している。
- Hook設定のマージ、LaunchAgent登録、PyObjCを含む実環境起動、自然なrate limit再Hook、実Claudeセッションのresume継続は生成または手動確認の境界にあり、未検証である。

## 18. Deferred Decisions

- 候補発見・終了に利用できるClaude Code HookイベントとpayloadはSpike 1Aで確定する。成立しない場合のみ手動登録方式を再検討する。
- rate limit中のresumeで同一イベントを再生成できるかはSpike 3で確定する。成立しない場合は、安全制約を維持できる代替検出方式を再検討する。
- Claude Code内部で実際のタスク処理が継続したかどうかはMVPの保証外とし、技術スパイクと手動E2Eで観測する。
