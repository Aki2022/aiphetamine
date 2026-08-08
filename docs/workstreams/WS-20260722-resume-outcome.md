---
schema_version: 2
id: WS-20260722-resume-outcome
status: active
created_at: 2026-07-22
updated_at: 2026-07-22
branch: WS-20260722-resume-outcome
pr: ""
human_boundary_confirmed_at: 2026-07-22
next_human_gate: resume-outcome-review
related_specs:
  - docs/specs/PRD.md
  - docs/specs/architecture.md
related_guides:
  - docs/guides/natural-resume.md
---

# Resume Outcome

## Goal

Claude resumeのプロセス生成成功を処理完了と誤認しない。標準出力・標準エラーを保持せず、終了コードだけで安全に成功・失敗を判定する。

## Success Criteria

- 終了コード0のときだけイベントを完了にする。
- 非ゼロ終了と起動エラーではイベントを復元する。
- Claudeの送信・再試行・設定変更を行わない。

## Authorization Envelope

- Approved scope: Claude resume processの終了結果を安全に分類し、起動成功を完了扱いにしない。Claude送信は行わない。
- Autonomous actions allowed: コード、テスト、仕様、ガイド、作業記録の更新とローカル検証。
- Confirm first: Claudeの起動・送信、設定またはアカウント変更、依存追加、ネットワーク利用、Git公開。
- Cost or usage ceiling: Claude送信0回、再試行0回。従量課金作業なし。
- Out of scope: 会話継続のlive検証、rate-limit再発検証、メニューバーUI変更、常駐スケジューラの有効化。

## Human Gates

- Start gate: confirmed on 2026-07-22
- Next gate: resume-outcome-review
- Stop conditions: `resume-outcome-review`到達、または追加のClaude起動が必要になった時点。

## Issue Queue

| Issue | Status | Depends on | Outcome |
| ----- | ------ | ---------- | ------- |
| ISSUE-01-safe-exit-observation | complete | none | 終了コードに基づく安全な完了判定 |

### ISSUE-01-safe-exit-observation

- status: complete
- depends_on: []
- guide_impact: required
- related_guides: [GUIDE-natural-resume]
- guide_impact_reason: ""

#### Goal

標準出力・標準エラーを破棄したままClaudeプロセスの終了コードを待ち、成功時だけイベントを完了にする。

#### Acceptance

- 非ゼロ終了を成功扱いにしないテストがある。
- 終了コード0だけが`completed`となり、非ゼロと起動エラーは復元される。
- 現行のテスト、構文、差分、文書検証が通る。

#### Current Status

非ゼロ終了を復元するテストを先に追加し、終了コード0だけを成功とする実装へ更新した。Claudeのlive起動は行っていない。

#### Next Actions

- `resume-outcome-review`で人間レビューを受ける。

## Decisions

Record only decisions that are difficult to reverse or surprising without context.

- `ResumeLaunchResult.launched`は「プロセスを生成できた」ではなく「出力を取得せず終了コード0で完了した」を表す。非ゼロ終了の詳細コードや出力本文は保存しない。
- 先行するone-shot検証の成功は、後から得た運用者確認を受け入れ基準とする。本作業単位は、その確認とは独立して将来の終了結果判定を改善する。

## Completion

- [x] Every issue meets its acceptance criteria
- [x] Every issue records guide impact as required or none
- [x] Required guides describe current implemented behavior
- [x] Specs reflect any changed direction or requirements
- [x] Next human gate reached or the workstream intentionally stopped
- [x] 00_index.md updated
- [ ] Workstream archived when complete
