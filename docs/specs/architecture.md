---
id: SPEC-aiphetamine-architecture
status: active
created_at: 2026-07-19
updated_at: 2026-07-20
related_guides: []
affected_workstreams: []
---

# AIphetamine — Architecture

## 1. 文書目的

本書は、`PRD.md`で定義したAIphetamine MVPを、Pythonで実装するためのアーキテクチャ、責務分割、データ構造、処理フロー、エラー処理、テスト方針を定義する。

実装者は、まず技術検証を行い、検証結果を本書へ反映した後に本実装へ進む。

## 2. アーキテクチャ方針

AIphetamineは小規模なローカル常駐アプリであるため、過剰なマイクロサービス化や複雑なDIフレームワークは採用しない。

一方で、以下の理由から責務は明確に分離する。

- メニューバーUIと業務ロジックを分離する
- Claude Code固有処理を将来交換可能にする
- JSONファイル操作の競合を局所化する
- 固定時刻スケジューラを単体テスト可能にする
- LaunchAgent操作をmacOS依存アダプターとして隔離する
- 技術検証結果によりresume判定方式が変わっても影響範囲を限定する

採用方針は、軽量なレイヤード構成とPorts and Adaptersの折衷とする。

## 3. システム全体像

```text
┌──────────────────────────────────────────────┐
│ Claude Code                                  │
│                                              │
│ StopFailure(rate_limit) Hook                 │
└───────────────────┬──────────────────────────┘
                    │ writes atomic JSON event
                    ▼
~/.local/share/aiphetamine/rate_limits/
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ AIphetamine                                  │
│                                              │
│  MenuBarController                           │
│        │                                     │
│        ▼                                     │
│  SelectionStore (in-memory activation)       │
│                                              │
│  BoundaryScheduler ── every 2 hours ─────┐   │
│                                          ▼   │
│  CandidateRepository                         │
│  RateLimitEventRepository → ResumeService    │
│                              │               │
│                              ▼               │
│                       ClaudeResumeAdapter     │
│                              │               │
│                              ▼               │
│             claude -p --resume ID Continue   │
│                                              │
│  LaunchAgentManager                          │
│  RotatingLogger                              │
└──────────────────────────────────────────────┘
```

## 4. ランタイム構成

## 4.1 推奨技術

- Python 3.11以降
- PyObjC
- 標準ライブラリ:
  - `pathlib`
  - `json`
  - `subprocess`
  - `logging`
  - `logging.handlers`
  - `datetime`
  - `zoneinfo`
  - `threading`
  - `dataclasses`
  - `enum`
  - `typing`
  - `os`
  - `shutil`
  - `plistlib`
  - `tempfile`

メニューバーUIはPyObjCからAppKitの`NSStatusItem`と`NSMenu`を直接利用する。`rumps`は採用しない。AppKitコールバックへドメインロジックを直接書かず、application serviceを呼び出す。

## 4.2 プロセスモデル

MVPでは、メニューバーUIとスケジューラを単一Pythonプロセスで動作させる。

別デーモンへの分離は行わない。

理由:

- アプリ終了中は何もしない要件と一致する
- 状態永続化が不要
- IPCが不要
- デバッグが容易
- 10セッションまでを動作保証・テスト規模とし、巡回処理が軽量

Launch at Login用のplistは同じエントリーポイントを起動する内容として生成する。plistの登録・解除は実装の副作用にせず、オペレーターが手動で行う。

MVPは専用venvを作成せず、ユーザーの既存Python環境を使用する。LaunchAgent plist生成時に指定されたPython実行ファイルを絶対パスとして記録し、手動起動とログイン起動で同じPythonを使う。

実装にはインストールスクリプトは含まれない。利用者がPython 3.11以上と必須モジュールを確認し、既存環境を変更せずに導入する。

## 5. ディレクトリ構成

推奨リポジトリ構成:

```text
aiphetamine/
├── README.md
├── PRD.md
├── architecture.md
├── pyproject.toml
├── requirements.txt
├── scripts/
│   ├── install.sh
│   ├── uninstall.sh
│   ├── run-dev.sh
│   └── generate-hook-config.sh
├── hooks/
│   └── claude_rate_limit_hook.py
├── src/
│   └── aiphetamine/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── config.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── errors.py
│       │   └── policies.py
│       ├── application/
│       │   ├── session_service.py
│       │   ├── resume_service.py
│       │   ├── startup_service.py
│       │   └── scheduling_service.py
│       ├── ports/
│       │   ├── session_repository.py
│       │   ├── resume_executor.py
│       │   ├── selection_store.py
│       │   ├── scheduler.py
│       │   └── login_item.py
│       ├── adapters/
│       │   ├── filesystem_session_repository.py
│       │   ├── claude_resume_executor.py
│       │   ├── in_memory_selection_store.py
│       │   ├── boundary_scheduler.py
│       │   ├── launch_agent_manager.py
│       │   └── rotating_file_logger.py
│       └── ui/
│           ├── menu_bar_controller.py
│           └── menu_models.py
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

過剰に細分化しない実装も許容するが、少なくとも以下は分離する。

- JSONリポジトリ
- スケジューラ
- resume実行
- 選択状態
- メニューバーUI
- LaunchAgent
- Hook

## 6. データディレクトリ

```text
~/.local/share/aiphetamine/
├── candidates/{main,alias,unknown}/
├── rate_limits/{main,alias,unknown}/
└── logs/
```

定数:

```python
DATA_DIR = Path.home() / ".local" / "share" / "aiphetamine"
CANDIDATES_DIR = DATA_DIR / "candidates"
RATE_LIMITS_DIR = DATA_DIR / "rate_limits"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_FILE = DATA_DIR / "config.json"
INSTANCE_LOCK = DATA_DIR / "instance.lock"
```

権限と所有境界:

- データルート、`candidates/`、`rate_limits/`、各アカウントスコープ、`logs/`はowner-onlyの`0700`
- 候補JSON、rate limit JSON、設定、ログは`0600`
- `instance.lock`は`0600`で作成し、起動中だけ非ブロッキング排他lockを保持する
- データルートから処理対象ファイルまでsymlinkを拒否する
- 所有者が実行ユーザーと異なる場合は権限変更や削除を行わず、resume処理を停止する
- 実行ユーザー所有の既存ファイルで権限が緩い場合に限り、安全側へ権限を狭める
- 安全性を確認できないファイルは不正イベントとして隔離せずその場に残し、内容を露出しないエラー表示とログ分類だけを行う

ローカル設定:

```json
{
  "schema_version": 1,
  "claude_executable": "<absolute-executable-path>"
}
```

実装は`config.json`を生成せず読み取りだけを行う。読み込み時は設定ファイルと親ディレクトリ、Claude実行ファイル、実行ファイルの親ディレクトリについて、所有者・権限・symlink・通常ファイル・実行可能性を検証する。Launch at Loginの登録状態は管理せず、plist生成後の手動操作に委ねる。

LaunchAgent:

```text
~/Library/LaunchAgents/local.aiphetamine.menubar.plist
```

LaunchAgent labelとplist名は`local.aiphetamine.menubar`へ固定する。個人名、ローカルユーザー名、所有していない公開ドメインを含めない。

## 7. ドメインモデル

## 7.1 RateLimitEvent

```python
@dataclass(frozen=True)
class RateLimitEvent:
    schema_version: int
    record_type: Literal["rate_limit"]
    reason: str
    session_id: str
    project_path: Path
    updated_at: datetime
    source_file: Path | None = None
    account_name: str | None = None
```

不変オブジェクトとする。

## 7.1A CandidateSession

```python
@dataclass(frozen=True)
class CandidateSession:
    schema_version: int
    record_type: Literal["candidate"]
    session_id: str
    project_path: Path
    updated_at: datetime
    session_name: str | None = None
    project_name: str | None = None
    source_file: Path | None = None
    account_name: str | None = None
```

候補スナップショットを表す不変オブジェクトとする。有効化状態や期限は含めない。

## 7.2 SessionDisplay

```python
@dataclass(frozen=True)
class SessionDisplay:
    session_id: str
    display_name: str
    project_name: str | None
    selected: bool
```

UIへ渡す表示専用モデル。

## 7.3 ResumeRequest

```python
@dataclass(frozen=True)
class ResumeRequest:
    session_id: str
    project_path: Path
    message: str = "Continue"
    account_name: str | None = None
```

## 7.4 ResumeLaunchResult

```python
@dataclass(frozen=True)
class ResumeLaunchResult:
    launched: bool
    pid: int | None
    error: str | None
```

MVPの成功判定は、標準出力・標準エラーを取得せずに回収した終了コードが0であることである。`launched`はこの正常完了を表す。非ゼロ終了または起動エラーは`launched=False`とサニタイズ済み分類で返す。

stdout/stderrは取得・保存しないため、結果モデルへ追加しない。

## 7.5 SessionActivation

```python
@dataclass(frozen=True)
class SessionActivation:
    session_id: str
    account_name: str | None
    activated_at: datetime
    expires_at: datetime
    resolved_project_path: Path
    project_device: int
    project_inode: int
```

`activated_at`と`expires_at`はUTCのaware datetimeとする。`expires_at`は有効化時のUTC時刻へ12時間を加えて計算し、永続化しない。

有効化時に`project_path.resolve(strict=True)`を実行し、実体パスとディレクトリのdevice/inodeをSessionActivationへ保存する。resume直前に候補記録、rate limitイベント、再解決した実体パス、device/inodeがすべて一致することを検証する。不一致時はclaimもresumeも行わず、`パス不一致`として再登録と再有効化を要求する。

## 8. JSONイベントモデル

## 8.1 JSONの意味

JSONは「rate limitに到達した」という単発イベントである。

候補発見記録とrate limitイベントは、寿命と操作が異なるため用途別ディレクトリへ分離する。さらに、アカウント別のsession IDが同じファイル名を共有しないよう、`main`、`alias`、`unknown`のスコープへ分離する。

- `candidates/{main,alias,unknown}/`: アカウントスコープごとの最新候補記録。起動時に読み込むが、有効化状態や期限は保存しない
- `rate_limits/{main,alias,unknown}/`: rate limit到達を表す単発イベント。claim、complete、restore、起動時の鮮度付きcleanupの対象
- `unknown/`: アカウントラベルを持たない既存Hook記録の隔離先。表示はできても自動resume対象にはしない

旧形式の用途別ディレクトリ直下にあるJSONは、移行期間の読み取り対象として扱う。ただし、旧形式にアカウントラベルがあっても共有namespaceのため自動resume対象にはしない。新規Hook書き込みは必ずアカウントスコープへ行う。

候補発見記録を有効化状態のDBとして扱わない。

状態を持たせない。

持たせない項目:

- `enabled`
- `selected`
- `completed`
- `retry_count`
- `next_retry_at`
- `wake_attempted`
- `running`

これらはアプリ内部状態または不要な状態である。

## 8.2 Candidate JSONスキーマ

```json
{
  "schema_version": 1,
  "record_type": "candidate",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_name": "implement-dashboard",
  "project_name": "research-platform",
  "project_path": "<absolute-project-path>",
  "updated_at": "2026-07-20T01:42:15+09:00",
  "account_name": "main"
}
```

## 8.3 Rate Limit JSONスキーマ

```json
{
  "schema_version": 1,
  "record_type": "rate_limit",
  "reason": "rate_limit",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "project_path": "<absolute-project-path>",
  "updated_at": "2026-07-20T01:42:15+09:00",
  "account_name": "main"
}
```

`account_name`はHook設定で明示された場合だけ保存する任意項目であり、認証情報やメールアドレスではない。ファイルの親スコープが`main`または`alias`の場合は、そのスコープが正規のアカウント識別子であり、JSON内の値と一致しなければ無効とする。
同じsession IDが複数のアカウントのmetadataに存在する場合は、アカウントを
一意に決定できないため表示・resume対象から除外する。明示された
`account_name`がある場合は、そのアカウントのmetadataだけを参照する。
metadataから補ったタイトルやrepository名は表示専用であり、欠落した
`account_name`を補完しない。SelectionStoreのキーは
`(session_id, account_name)`とし、一方のアカウントでの選択を他方へ引き継がない。

## 8.4 バリデーション

必須条件:

- rootがobject
- `schema_version == 1`
- 保存ディレクトリと`record_type`が一致する
- `session_id`が非空文字列
- `project_path`が絶対パス
- `updated_at`がISO 8601として解釈可能
- ファイル名がsession_idから再計算したsession_keyと一致する
- `updated_at`が現在UTCより未来でも5分以内である
- `account_name`が存在する場合は設定済みのアカウント識別子である
- 同じsession IDが複数ファイルまたは複数アカウントスコープに現れた場合は、候補・イベントとも曖昧として除外する

rate limitイベント追加条件:

- `reason == "rate_limit"`

resume前追加条件:

- `project_path.exists()`
- `project_path.is_dir()`
- 候補とイベントの`account_name`がともに存在し、同じ値である

任意項目が不正でも、必須項目が有効なら無視してよい。

現在UTCより5分を超えて未来の`updated_at`を持つ記録は不正イベントとして処理対象から除外し、自動削除せず無効イベント件数へ含める。

## 9. Hook設計

## 9.1 責務

Claude Code Hookは、候補セッションの最新スナップショットとrate limit到達イベントをJSONへ変換する。セッション終了Hookは対応するrate limitイベントがない場合だけ候補記録を削除し、制限到達後のresume選択に必要な候補を保持する。

AIphetamine本体はClaudeの出力を直接監視しない。

## 9.2 Hook入力

技術検証で、実際のHook payloadから以下を取得する。

- session_id
- cwd
- transcript_path
- event type
- failure reason
- 人間向けsession name候補

取得できない任意項目は省略する。

## 9.3 Hook出力

候補発見Hookの出力先:

```text
~/.local/share/aiphetamine/candidates/{main,alias,unknown}/<session_key>.json
```

`session_key`はUTF-8のsession_idをSHA-256でハッシュ化した64桁の小文字16進文字列とする。同じsession_idが既に存在する場合は、最新候補情報として原子的に上書きする。

rate limit Hookの出力先:

```text
~/.local/share/aiphetamine/rate_limits/{main,alias,unknown}/<session_key>.json
```

同じアカウントスコープの同じsession_idが既に存在する場合は、最新候補として原子的に上書きする。アカウントをまたぐ同一session_idは曖昧として除外する。

セッション終了Hookは、対応する`candidates/{main,alias,unknown}/<session_key>.json`を直接かつ冪等に削除する。ファイルが既に存在しない場合も成功扱いとする。アプリ停止中も同じ処理を行う。

RepositoryはJSON内部のsession_idからsession_keyを再計算し、ファイル名と一致しない記録を不正として処理対象から除外する。

## 9.4 原子的書き込み

```text
<scope>/<session_key>.json.tmp.<pid>
→ flush
→ file fsync
→ os.replace(<session_key>.json)
→ parent directory fsync
```

一時ファイルは保存先と同じディレクトリへ`0600`で作成し、同一ファイルシステム上の`os.replace`を利用する。途中で失敗した一時ファイルは通常処理対象にせず、rate limit側は次回起動時cleanup対象とする。

候補削除時は対象ファイルをunlinkした後、対象スコープディレクトリを`fsync`する。ファイル不在は成功扱いとする。

## 9.5 Hookエラー

Hook失敗はClaude Code本体を妨げない。

- Hookは可能な限り短時間で終了する
- Hook失敗は許可リスト化した短いエラー分類だけをstderrへ出し、生の例外、パス、session_id、JSON内容は出力しない
- Hook側で再試行しない
- AIphetamineが起動していなくても候補記録の作成・更新・削除とrate limitイベント作成を行える
- 候補記録の削除失敗を含むHookエラーはClaude Code本体を妨げない
- 次回AIphetamine起動時、12時間以内の有効なrate limitイベントは保持され、古い・不正なイベントだけが削除される。候補記録は読み込まれる

## 9.6 Hook設定の適用境界

`scripts/generate_hook_config.py`はAIphetamine用Hookスクリプトを参照するClaude Code向け設定断片を生成し、Claude Codeの既存設定ファイルは自動編集しない。

ユーザーが生成内容と既存Hookとの競合を確認し、手動で設定へマージする。READMEに適用、検証、解除手順を記載する。

## 10. CandidateRepositoryとRateLimitEventRepository

### 10.1 CandidateRepository

責務:

- `candidates/`の候補スナップショット一覧取得
- パースとバリデーション
- session_id単位の重複排除
- 前回巡回から消失した候補の検出
- `updated_at`から24時間を超えた候補の除外

候補記録の作成・更新・削除はClaude Code Hookが担当し、アプリ側Repositoryは読み取り専用とする。

候補鮮度期限は24時間とする。現在UTCとの差が24時間を超える候補は一覧、有効化、resume照合に使用しない。同じsession_idの候補Hookが新しい`updated_at`で正常に上書きすれば再び有効になる。

この期限は、Spike 1Aで活動中のセッションについて候補スナップショットを定期的なユーザー操作時に更新できることを確認できた場合に限り採用する。セッション開始時にしか更新できない場合は本実装前に期限を再度grillする。

```python
class CandidateRepository(Protocol):
    def list_candidates(self) -> list[CandidateSession]: ...
```

### 10.2 RateLimitEventRepository

責務:

- `rate_limits/`のJSON一覧取得
- パース
- バリデーション
- `updated_at`から12時間を超えたイベントの削除
- `.json`から`.processing`へのclaim
- `.processing`削除
- `.processing`から`.json`へのrestore
- 起動時cleanup

インターフェース例:

```python
class RateLimitEventRepository(Protocol):
    def initialize(self) -> None: ...
    def list_events(self) -> list[RateLimitEvent]: ...
    def claim(self, event: RateLimitEvent) -> Path: ...
    def complete(self, processing_path: Path) -> None: ...
    def restore(self, processing_path: Path) -> Path: ...
    def cleanup_on_startup(self) -> None: ...
```

### 10.2.1 Claim

```text
abc.json
→ os.replace
abc.processing
```

renameに失敗した場合、他処理がclaim済みとみなしスキップする。

### 10.2.2 Complete

プロセス生成成功時:

```text
abc.processing
→ unlink
```

### 10.2.3 Restore

プロセス生成失敗時:

```text
abc.processing
→ abc.json
```

同名JSONが既にHookにより再生成されている場合:

- 既存JSONを優先
- `.processing`は削除
- 上書きしない
- ログへ競合を記録

### 10.2.4 起動時Cleanup

起動時に`rate_limits/`だけを対象として:

- 12時間以内の有効な`*.json`は保持
- 古い・不正な`*.json`削除
- `*.processing`削除
- `*.tmp.*`削除

削除失敗はログに記録するが、可能な限り起動を継続する。

`candidates/`はcleanupせず、候補一覧の再構成に使用する。

固定巡回では、現在UTCとの差が12時間を超えるrate limitイベントをclaim対象へ含めず削除する。削除時はイベント内容や識別子を記録せず、失効件数だけをログへ記録する。

## 11. SelectionStore

メモリ上で有効化セッションとUTC絶対期限を保持する。

```python
class InMemorySelectionStore:
    _activations: dict[str, SessionActivation]
```

操作:

```python
activate(session_id, now_utc)
deactivate(session_id)
is_selected(session_id)
is_expired(session_id, now_utc)
expire_due(now_utc)
clear()
```

重要:

rate limitイベントが削除されてもSessionActivationは保持する。

理由:

- resume後、まだrate limit中なら同じsession_idのJSONが再生成される
- 再生成時にチェックONを維持する必要がある

アプリ終了時に破棄する。巡回前とスリープ復帰時に、現在UTCで期限切れを判定し、resume判定より先に対象をOFFへ戻す。タイムゾーン変更では期限を再計算しない。システム時計が変更された場合は、変更後のUTC時刻で再評価する。

## 12. BoundaryScheduler

## 12.1 要件

- 毎日偶数時の00分に実行
- 起動直後は実行しない
- 次の境界を計算する
- 実行後は次の2時間後を予約
- スリープ復帰後は現在時刻から次の境界を再計算
- 過去の未実行分を補完しない
- NSRunLoop上の一回限りのFoundation Timerで、次の未来境界だけを予約する
- Timer発火後は現在ローカル時刻から次の境界を再計算して予約する
- スリープ復帰時は古いTimerを破棄し、UTC期限切れ処理後に次の未来境界を予約する

## 12.2 次回時刻計算

例:

```python
def next_boundary(now: datetime) -> datetime:
    local = now.astimezone()
    next_hour = ((local.hour // 2) + 1) * 2

    if next_hour >= 24:
        return local.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

    return local.replace(
        hour=next_hour, minute=0, second=0, microsecond=0
    )
```

22:00ちょうどなど境界時刻に起動した場合も、次の境界へ送る。

比較時に`now >= scheduled_at`となった場合は一度実行し、次を再計算する。ただし、複数回分を連続実行しない。

## 12.3 UIスレッドとの関係

メニューバーUIのイベントループをブロックしない。

NSRunLoop上の一回限りのFoundation Timerを使用する。Timerコールバックは巡回処理をワーカーへ委譲し、ファイルI/Oやプロセス起動でUIスレッドをブロックしない。巡回完了後のメニュー更新だけをメインスレッドへ戻す。

resume処理は単一ワーカースレッドへ渡す。

## 13. ResumeService

固定巡回時のユースケースを統括する。

巡回順序:

1. CandidateRepositoryから候補スナップショットを読み込む
2. 前回から消失した候補をSelectionStoreから解除する
3. 現在UTCで期限切れの有効化をOFFへ戻す
4. RateLimitEventRepositoryからイベントを読み、現在候補、有効化状態、期限、project_path一致を検証する
5. 対象イベントをclaimしてresumeプロセスを起動する
6. 最終状態でメニューを更新する

巡回処理中に到着して現在のスナップショットへ含まれなかった候補記録またはrate limitイベントは、次回巡回まで処理しない。

擬似コード:

```python
def run_poll_cycle() -> None:
    events = repository.list_events()

    for event in events:
        if not selection_store.is_selected(event.session_id, event.account_name):
            continue

        if processing_registry.contains(event.session_id):
            continue

        processing_path = repository.claim(event)

        try:
            result = resume_executor.launch(
                ResumeRequest(
                    session_id=event.session_id,
                    project_path=event.project_path,
                    message="Continue",
                )
            )

            if result.launched:
                repository.complete(processing_path)
            else:
                repository.restore(processing_path)

        except Exception as error:
            repository.restore(processing_path)
            logger.error(classify_error(error))
```

## 13.1 並列性

10件までを動作保証・テスト規模とし、巡回全体を単一ワーカーで直列実行する。

- セッションごとにsubprocessを起動
- 起動処理自体は順次行う
- 起動後の完了はUIスレッドでは待たず、巡回ワーカーで終了コードを待つ
- claim、restore、complete、候補同期、期限切れ処理を同じワーカー上で直列化する
- 前回巡回が実行中の場合は新しい巡回を開始せず、重複スキップをログへ記録して次の未来境界を予約する

これにより巡回処理が長時間ブロックしない。

MVPでは以下を必須とする。

- stdin、stdout、stderrを`subprocess.DEVNULL`へ接続する
- `start_new_session=True`でアプリ本体から独立させる
- `Popen`後は同じ巡回ワーカーで`wait()`し、終了コードだけを回収する
- アプリ終了時にresume子プロセスを強制終了しない

## 13.2 子プロセス終了メタデータ

終了コード0の場合だけ対象イベントを完了にし、非ゼロ終了ではイベントを復元する。標準出力・標準エラー、終了コードの数値、会話内容は保存しない。記録する場合も匿名化した相関IDとサニタイズ済み分類に限る。

## 14. ClaudeResumeExecutor

実行引数:

```python
[
    "claude",
    "-p",
    "--resume",
    session_id,
    "Continue",
]
```

`shell=False`を必須とする。

cwd:

```python
cwd=str(project_path)
```

環境変数:

- 基本は現在の環境を継承
- `ResumeRequest.account_name`が`alias`の場合は検証済みの第二設定ディレクトリを`CLAUDE_CONFIG_DIR`へ設定する
- アカウント名が不明または候補とイベントで不一致の場合はresumeを起動しない
- Claude実行にはローカル設定から読み込んだ検証済み絶対パスを使い、実行時PATH探索は行わない

## 14.1 Claude実行ファイル探索

Claude実行ファイルの解決・設定ファイルへの保存を行うインストール処理は提供しない。利用者が用意した絶対パスを設定へ登録し、実行時は既知パスのハードコードやOS cron、ログインシェル経由の探索を行わない。

アプリ起動時は保存済み絶対パスが存在し、通常ファイルで、実行可能であることを検証する。検証に失敗した場合はresumeを行わず、候補行へ`起動失敗`を表示し、サニタイズした分類をログへ記録する。Claudeのインストール先が変わった場合は設定ファイルを利用者が更新する。

## 14.2 元プロセスとの関係

AIphetamineは元のClaude Code OSプロセスへ入力しない。

`claude --resume`は新しいOSプロセスとして既存会話セッションを再開する。

次は技術検証対象:

- 元プロセスがまだ生存している場合の同一session_id競合
- 元プロセスが終了している場合のresume
- `-p`モードのHook発火
- 非対話プロセス終了後の作業継続性

## 15. MenuBarController

責務:

- アプリメニュー生成
- セッション一覧表示
- チェック状態変更
- Launch at Login変更
- Quit
- リポジトリ変更時の再描画
- アイコン状態更新

UIはドメインロジックを直接実行せず、application serviceを呼ぶ。

## 15.1 メニュー構造

```text
[Session rows]

Separator

Launch at Login

Separator

Quit AIphetamine
```

## 15.2 セッション行

人間向け表示:

```text
☐ implement-dashboard — research-platform
```

状態がある場合:

```text
☐ implement-dashboard — research-platform · 起動失敗
```

標準`NSMenuItem`の一行表示へ固定し、カスタムViewは使用しない。重複時だけsession_id先頭8文字を追加する。状態は`起動失敗`、`パス不一致`、`有効期限切れ`のいずれかを末尾へ表示する。

`session_name`と`project_name`はUnicode NFCへ正規化し、制御文字を除去し、連続空白を1つへ圧縮する。各フィールドを40 Unicode code pointまでとし、超過時は末尾を省略記号に置き換える。サニタイズ・切り詰め後の表示が重複する場合もsession_id先頭8文字で区別する。

## 15.3 更新方法

候補発見、rate limitイベント検出、resume判定は同じ2時間固定巡回で行う。FSEvents、常時監視、短周期ポーリングは使用しない。

チェック状態の変更、期限切れ、起動失敗、パス不一致、巡回完了時は、メモリ上の最新状態からメニューを直ちに再構築する。ファイルシステム上の新規イベントは次回固定巡回まで反映しない。

## 15.4 アイコン状態

```python
NORMAL
WAITING
```

WAITING条件:

```text
選択済み`(session_id, account_name)`に対応する有効JSONが1件以上存在
```

## 16. LaunchAgentManager

責務:

- plist生成
- 登録・登録解除
- 有効状態確認
- 削除

LaunchAgent managerは、保存済みのPython、アプリのエントリーポイント、設定パスの絶対パスからplistを一時ファイルへ生成し、原子的に置換する。LaunchAgentの登録・解除やON/OFFのUI操作は提供せず、利用者が手動で行う。

登録解除や専用plistの削除は手動の運用境界であり、アプリは生成済みplistの存在だけを確認する。

## 16.1 uninstall境界

通常の運用でLaunchAgentを登録解除し、AIphetamine専用plistを削除する場合は利用者が手動で行う。ユーザーが手動でマージしたClaude Code Hook設定は編集せず、解除手順を表示する。

ローカル設定、`candidates/`、`rate_limits/`、`logs/`は通常uninstallでは保持する。明示的な`--purge-data`指定時だけ、データルートが期待する固定パス、実行ユーザー所有、非symlinkであることを検証してから削除する。検証に失敗した場合は削除せず停止する。

plist項目例:

```xml
<key>Label</key>
<string>local.aiphetamine.menubar</string>

<key>ProgramArguments</key>
<array>
  <string>/absolute/path/to/python</string>
  <string>-m</string>
  <string>aiphetamine</string>
</array>

<key>RunAtLoad</key>
<true/>

<key>KeepAlive</key>
<false/>
```

重要:

- `KeepAlive`は不要
- アプリ終了後に自動復活させない
- ログイン時だけ起動
- PATH依存を避けるため絶対パスを使用

## 17. ロギング

## 17.1 アプリログ

`TimedRotatingFileHandler`を基底にしたdescriptor-relativeなsecure handlerを利用する。

```python
handler = SecureTimedRotatingFileHandler(
    filename=LOGS_DIR / "aiphetamine.log",
    when="midnight",
    backupCount=7,
    encoding="utf-8",
)
```

## 17.2 ログフォーマット

```text
timestamp level component event correlation_id error_class
```

`session_id`列には生値ではなく、アプリ起動時に生成したランダムsaltとsession_idを連結してSHA-256を計算し、その先頭12桁を相関IDとして記録する。saltはメモリだけに保持し、ログや設定へ保存しない。

例:

```text
2026-07-20T02:00:00+09:00 INFO resume_service poll_started
2026-07-20T02:00:01+09:00 INFO resume_executor launched correlation_id=12hexchars
```

## 17.3 機密性

- 固定文字列`Continue`は記録可
- transcript本文は読まない
- プロンプト本文は保存しない
- stdout/stderrは取得・保存しない
- ローカル絶対パス、ユーザー名、生のsession_id、イベントJSON内容を記録しない
- 生の例外文字列とスタックトレースを記録しない
- 許可リスト化したイベントコードとサニタイズ済みエラー分類だけを記録する
- ログはローカルのみ

## 18. 起動シーケンス

`config.json`が欠落、破損、または検証失敗した場合もAppKitメニューバーを縮退起動する。候補一覧と選択UIは表示されるが、`DisabledResumeExecutor`がresume起動を拒否し、結果は`launch_disabled`として復元される。Launch at LoginのOFF、Quit、サニタイズ済みログは利用可能とする。設定エラー専用のメニュー行は現行実装の契約に含めない。

データルートを安全に作成・検証した直後、起動時cleanupより前に`instance.lock`を開き、`fcntl.flock(LOCK_EX | LOCK_NB)`を取得する。lockはプロセス終了まで保持する。取得できない二つ目のプロセスは、cleanup、設定変更、UI起動を行わず、サニタイズした理由だけを記録して終了する。lockファイル自体は残してよい。

```text
User launches AIphetamine
        │
        ▼
Create data directories
        │
        ▼
Acquire exclusive instance.lock
        │
        ▼
Delete stale rate_limits/{main,alias,unknown}/*.json/.processing/.tmp
        │
        ▼
Load fresh candidates/{main,alias,unknown}/*.json snapshots
        │
        ▼
Clear in-memory activations and expiry state
        │
        ▼
Resolve Claude executable
        │
        ▼
Start menu bar UI
        │
        ▼
Schedule next fixed boundary
        │
        ▼
Calculate next even-hour boundary
        │
        ▼
Wait
```

## 19. rate limitイベント処理シーケンス

```text
Claude Code
    │
    │ rate limit reached
    ▼
StopFailure(rate_limit) Hook
    │
    │ atomic write
    ▼
<account-scope>/<session_key>.json
    │
    ▼
UI watcher detects JSON
    │
    ▼
Menu shows unchecked session
    │
    ▼
User checks session
    │
    ▼
SelectionStore.add(session_id)
```

## 20. Resumeシーケンス

```text
BoundaryScheduler
    │
    ▼
ResumeService.poll()
    │
    ▼
List valid events
    │
    ▼
Filter selected session IDs
    │
    ▼
Rename .json → .processing
    │
    ▼
    posix_spawn(
        verified_claude_path,
        cwd=file_actions.addfchdir(verified_project_directory),
        argv=["claude", "-p", "--resume", id, "Continue"],
        stdin=DEVNULL,
        stdout=DEVNULL,
        stderr=DEVNULL,
        start_new_session=True,
    )
    │
    ├── launch failed
    │      ▼
    │   restore .json
    │
    └── process exits with code 0
           ▼
        delete .processing
           ▼
        wait for Hook recreation
```

## 21. rate limit継続時の期待フロー

```text
Resume process launched
        │
        ▼
Claude Code still rate-limited
        │
        ▼
StopFailure(rate_limit) fires again
        │
        ▼
Same session_id JSON recreated
        │
        ▼
SelectionStore still contains session_id
        │
        ▼
UI shows checked session again
        │
        ▼
Next boundary retries
```

このフローは技術検証で成立確認が必要である。

## 22. 競合と障害シナリオ

## 22.1 Hook再生成とrestore競合

resume起動失敗後、restoreしようとした時点でHookが同名JSONを作っている場合:

- 新JSONを保持
- `.processing`を削除
- 上書きしない
- ログ記録

## 22.2 アプリクラッシュ

`.processing`が残る。

次回起動時、12時間以内の有効なrate limitイベントは保持されるが、選択状態は空なので自動resumeは行われない。`candidates/`はcleanupせず、24時間鮮度期限を満たす候補だけを読み込む。

## 22.3 JSON途中書き込み

Hookの原子的書き込みで防止する。

不正JSONはスキップし、次回再読込する。

## 22.4 同一session_idの複数ファイル

アカウントスコープをまたいで同じsession_idが複数存在する場合は、Repositoryが
任意のwinnerを選ばず、すべてresume対象外として除外する。異なるスコープへの
選択状態の引き継ぎも行わない。

## 22.5 project_path削除

resume対象外。

JSONは残し、ログへ記録する。

ユーザーがチェック解除またはアプリ再起動するまで残る。

## 22.6 claudeコマンド不在

- resume失敗
- JSON復元
- ログ記録
- 次回再試行

メニューにエラー表示はMVPでは不要。

## 22.7 Macスリープ

スリープ中の境界は実行しない。

復帰後、次の未来の境界を予約する。

過去分を即時実行しない。

## 23. テスト戦略

## 23.1 Unit Tests

### BoundaryScheduler

- 21:10 → 22:00
- 22:00 → 翌00:00
- 23:59 → 翌00:00
- 00:01 → 02:00
- 日付跨ぎ
- タイムゾーン変更
- DSTがあるタイムゾーンでも破綻しない

### JSON Parser

- 完全JSON
- 任意項目なし
- 不正JSON
- schema_version不一致
- reason不一致
- 空session_id
- 相対project_path
- 不正updated_at

### SelectionStore

- select
- deselect
- clear
- JSON消失後も保持

### Repository

- list
- claim
- complete
- restore
- restore競合
- cleanup
- 原子的rename失敗

### ResumeService

- 未選択は実行しない
- 選択済みだけ実行
- 複数セッション
- 終了コード0でdelete
- 非ゼロ終了または起動失敗でrestore
- 1件失敗しても他を継続

## 23.2 Integration Tests

- 一時ディレクトリでHook JSON生成
- UIモデルへの反映
- ダミーClaude実行ファイルでPopen
- 同一session_id JSON再生成
- LaunchAgent plist生成
- ログローテーション

## 23.3 Manual Tests

- 実際のClaude Code rate limit到達
- Hook発火
- session_id一致
- resume成功
- rate limit中の再Hook
- 元プロセスあり/なし
- Macスリープ復帰
- ログイン起動
- Dock非表示
- 10セッションまでの動作保証と、11件以上を除外しないこと

## 24. 技術スパイク実施順

### Phase 0

1. Claude Hook payloadの保存
2. rate limit matcher確認
3. `claude -p --resume`挙動確認
4. rate limit中の再Hook確認
5. 元プロセス競合確認

### Phase 1

- JSON Hook
- Repository
- Resume executor
- CLIだけでE2E確認

### Phase 2

- BoundaryScheduler
- SelectionStore
- MenuBar UI

### Phase 3

- LaunchAgent
- ログ
- install/uninstall scripts
- README

## 25. 実装完了条件

- すべての受け入れ基準を満たす
- 技術スパイク結果が文書化される
- Spike 3が不成立ならフォールバック設計が更新される
- 単体テストが主要ロジックをカバーする
- 手動E2Eテスト手順がREADMEにある
- clone後にXcodeなしで起動できる
- Apple Silicon macOS 15.7.5で動作確認する
- App Storeや署名を前提としない

## 26. Impact on Existing System

- activeな`PRD.md`で、候補発見・終了イベント、12時間の有効期限、2時間巡回への統合、安全なログ制約が追加された。
- 候補発見・終了イベント、12時間の有効期限、2時間巡回への統合、安全なログ制約を本architectureへ反映中である。
- 現在のリポジトリでは、repository、selection、boundary、resume eligibility基盤、runtime coreのatomic event操作・poll cycle・固定resume command、Hook、メニューバーUI、LaunchAgent plist生成、およびread-only dry-run app shellが実装済みである。
- Claude設定へのHookマージ、LaunchAgentの登録、PyObjCを含む実環境のメニューバー起動、自然なrate limit再Hook、実Claudeセッションのresume継続は手動操作または環境依存であり、このリポジトリでは未検証である。
