# SOTA Rigid Model V93 Snapshot Manifest

**Date**: 2026-03-01
**Score**: >= 93.0
**Branch**: `SOTA-RIGID-V93-FINAL-SNAPSHOT`

## Snapshot Overview

This branch contains an integral copy of the trading system at the point where it achieved a stabilized assertiveness score of 93.0 or higher.

## Key Components Included

- **Backend**: All AI logic, `ai_core.py`, and MT5 bridge components.
- **Frontend**: Full Next.js/Vite application.
- **Weights**:
  - `backend/patchtst_weights_sota.pth`
  - `backend/patchtst_weights_sota.onnx`
- **Training Data**: Full `data/sota_training/` datasets.
- **Parameters**: `backend/v22_locked_params.json` (Locked Golden Params).
- **State**: `trading_state.db` (Force-added to ensure state continuity).

## Purpose

To maintain a rigid, immutable baseline for institutional-grade reliability before further experimentation or optimization.
