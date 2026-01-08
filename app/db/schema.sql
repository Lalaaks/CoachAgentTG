PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS settings (
  user_id INTEGER PRIMARY KEY,
  timezone TEXT NOT NULL,
  study_reminder_enabled INTEGER NOT NULL DEFAULT 1,
  study_reminder_time TEXT NOT NULL DEFAULT '18:00',
  study_reminder_days TEXT NOT NULL DEFAULT '1,2,3,4,5',
  weekly_summary_day INTEGER NOT NULL DEFAULT 7,
  weekly_summary_time TEXT NOT NULL DEFAULT '19:00',
  last_reminder_date TEXT
);

CREATE TABLE IF NOT EXISTS study_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  topic TEXT,
  goal TEXT,
  planned_minutes INTEGER,
  done_minutes INTEGER,
  what_done TEXT,
  stuck_point TEXT,
  focus INTEGER,
  difficulty INTEGER,
  next_step TEXT,
  feynman TEXT,
  status TEXT NOT NULL DEFAULT 'active'
);
