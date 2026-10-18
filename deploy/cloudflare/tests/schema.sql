CREATE TABLE IF NOT EXISTS spike_cells (
    id TEXT PRIMARY KEY,
    value INTEGER NOT NULL CONSTRAINT spike_value_nonnegative CHECK(value >= 0)
);
CREATE TABLE IF NOT EXISTS spike_events (
    id INTEGER PRIMARY KEY,
    marker TEXT NOT NULL,
    ack_sync INTEGER NOT NULL CHECK(ack_sync = 1)
);
