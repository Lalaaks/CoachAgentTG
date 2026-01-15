-- 004_ai_analyses.sql
-- Stores AI-generated analyses (e.g., task insights) per user & period.

CREATE TABLE IF NOT EXISTS ai_analyses (
  analysis_id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,

  kind TEXT NOT NULL,                 -- e.g. "tasks"
  period_days INTEGER NOT NULL,       -- e.g. 7 or 30
  period_start TEXT NOT NULL,         -- ISO UTC
  period_end TEXT NOT NULL,           -- ISO UTC

  model TEXT NOT NULL,
  input_json TEXT,                    -- JSON (metrics + sample titles)
  output_text TEXT NOT NULL,          -- final analysis shown to user

  created_at TEXT NOT NULL            -- ISO UTC
);

CREATE INDEX IF NOT EXISTS idx_ai_analyses_user_kind_created
ON ai_analyses(user_id, kind, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_analyses_user_kind_period
ON ai_analyses(user_id, kind, period_days, period_end DESC);
