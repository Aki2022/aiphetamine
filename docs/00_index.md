---
updated_at: 2026-08-09
current_focus:
  - docs/workstreams/WS-20260721-resume-wiring.md
---

# 00 Index

## Read Policy

Read this file first. Do not scan all docs unless needed. Read the active workstream or issue, then only related specs and guides.

## Current Focus

- docs/workstreams/WS-20260721-resume-wiring.md — live resumeの結果表示を追加し、AIphetamine再起動後のUI確認待ち

## Active Workstreams

- docs/workstreams/WS-20260720-phase0-technical-spikes.md — Candidate lifecycleとresumeのlive検証を反映し、ISSUE-03を保留したまま `phase0-results-review` ゲートで人間レビュー待ち
- docs/workstreams/WS-20260721-phase1-foundation.md — JSONリポジトリ、選択状態、固定時刻、resume判定のローカル基盤を実装済み。MVP実行機能は未実装で `phase1-foundation-review` 待ち
- docs/workstreams/WS-20260721-runtime-core.md — atomicイベント処理、poll cycle、resumeコマンド生成を実装済み。実Claude起動は未実施で `runtime-core-review` 待ち
- docs/workstreams/WS-20260721-app-shell.md — 起動状態、次回境界、dry-run出力を統合済み。実Claude起動は未実施
- docs/workstreams/WS-20260721-live-cli-e2e.md — 1回限定のlive CLI検証を実施、結果は不確定として人間レビュー待ち
- docs/workstreams/WS-20260721-mvp-integration.md — ローカルMVP統合は完了。本番適用・Claude実行は未実施
- docs/workstreams/WS-20260721-production-integration.md — 本番統合と通常Hook確認は完了。rate-limit検証は未実施
- docs/workstreams/WS-20260721-resume-wiring.md — 安全なresume接続は完了。実resumeは別承認待ち
- docs/workstreams/WS-20260721-natural-resume.md — 自然rate-limit 1件へのresume 1回を検証済み
- docs/workstreams/WS-20260722-resume-outcome.md — Claude resumeの終了コードを安全に判定する改善


## Specs

- docs/specs/PRD.md — AIphetamine MVP の目的、スコープ、機能要件、受け入れ基準
- docs/specs/architecture.md — AIphetamine MVP のアーキテクチャと設計方針

## Active Issues


## Guides

## Archive Policy

Completed workstreams and issues are stored in their respective archive directories. Archive files are historical context, not current truth.
