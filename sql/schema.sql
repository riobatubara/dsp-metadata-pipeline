-- DSP Metadata Pipeline
-- PostgreSQL Schema
--
-- Layers:
--   audit = pipeline execution and data-quality tracking
--   raw   = immutable Spotify / YouTube API payloads
--   core  = cleaned / standardized analytical data
--   mart  = reporting & presentation Layer
--
-- Google Sheets catalog:
--   Used only as input parameters for Spotify / YouTube searches.
--   It is NOT persisted in this database.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;


-- AUDIT
CREATE TABLE IF NOT EXISTS audit.catalog_file_log (
    file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_checksum TEXT NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL,

    UNIQUE (file_name, file_checksum)
);

CREATE TABLE IF NOT EXISTS audit.ingestion_log (
    ingestion_id    UUID PRIMARY KEY,
    source_name     TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    status          TEXT NOT NULL,
    records_read    BIGINT NOT NULL DEFAULT 0,
    records_written BIGINT NOT NULL DEFAULT 0,
    error_message   TEXT,

    CONSTRAINT chk_ingestion_status
        CHECK (
            status IN ('RUNNING', 'SUCCESS', 'FAILED')
        )
);

CREATE TABLE IF NOT EXISTS audit.data_quality_log (
    quality_check_id BIGSERIAL PRIMARY KEY,

    ingestion_id     UUID
        REFERENCES audit.ingestion_log(ingestion_id),

    check_name       TEXT NOT NULL,
    table_name       TEXT NOT NULL,
    status           TEXT NOT NULL,
    records_checked  BIGINT NOT NULL DEFAULT 0,
    records_failed   BIGINT NOT NULL DEFAULT 0,
    error_message    TEXT,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_quality_status
        CHECK (
            status IN ('PASS', 'FAIL', 'WARNING')
        )
);


-- RAW
--
-- Original API responses are preserved as JSONB.
-- The raw layer is used for traceability, debugging,
-- and reprocessing without calling the APIs again.

CREATE TABLE IF NOT EXISTS raw.spotify (
    raw_id          BIGSERIAL PRIMARY KEY,

    ingestion_id    UUID NOT NULL
        REFERENCES audit.ingestion_log(ingestion_id),

    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_artist TEXT,
    song_title      TEXT,
    track_id        TEXT,
    response_json   JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_spotify_track_id
    ON raw.spotify (track_id);

CREATE INDEX IF NOT EXISTS idx_raw_spotify_ingestion_id
    ON raw.spotify (ingestion_id);



CREATE TABLE IF NOT EXISTS raw.youtube (
    raw_id          BIGSERIAL PRIMARY KEY,

    ingestion_id    UUID NOT NULL
        REFERENCES audit.ingestion_log(ingestion_id),

    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_artist TEXT,
    song_title      TEXT,
    video_id        TEXT,
    response_json   JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_youtube_video_id
    ON raw.youtube (video_id);

CREATE INDEX IF NOT EXISTS idx_raw_youtube_ingestion_id
    ON raw.youtube (ingestion_id);


-- CORE

-- ARTIST
CREATE TABLE IF NOT EXISTS core.artist (
    artist_id       TEXT PRIMARY KEY,

    artist_name     TEXT NOT NULL,
    normalized_name TEXT NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ALBUM
CREATE TABLE IF NOT EXISTS core.album (
    album_id             TEXT PRIMARY KEY,

    album_name           TEXT NOT NULL,
    normalize_album_name TEXT NULL,
    release_date         DATE,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- SONG
CREATE TABLE IF NOT EXISTS core.song (
    song_id          BIGSERIAL PRIMARY KEY,

    recording_title  TEXT NOT NULL,
    normalized_title TEXT NOT NULL,

    release_date     DATE,

    album_id         TEXT
        REFERENCES core.album(album_id),

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_song_title_album 
        UNIQUE (normalized_title, album_id)
);

CREATE INDEX IF NOT EXISTS idx_song_normalized_title
    ON core.song (normalized_title);

CREATE INDEX IF NOT EXISTS idx_song_release_date
    ON core.song (release_date);


-- SONG ↔ ARTIST
CREATE TABLE IF NOT EXISTS core.song_artist (
    song_id     BIGINT NOT NULL
        REFERENCES core.song(song_id),

    artist_id   TEXT NOT NULL
        REFERENCES core.artist(artist_id),

    PRIMARY KEY (song_id, artist_id)
);


-- SPOTIFY TRACK
CREATE TABLE IF NOT EXISTS core.spotify_track (
    spotify_track_id BIGSERIAL PRIMARY KEY,

    song_id          BIGINT NOT NULL
        REFERENCES core.song(song_id),

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_spotify_track_song UNIQUE (song_id)
);

CREATE INDEX IF NOT EXISTS idx_spotify_track_song_id
    ON core.spotify_track (song_id);


-- ISRC
CREATE TABLE IF NOT EXISTS core.song_isrc (
    song_isrc_id     BIGSERIAL PRIMARY KEY,

    song_id          BIGINT NOT NULL
        REFERENCES core.song(song_id),

    isrc             TEXT NOT NULL,

    spotify_track_id BIGINT
        REFERENCES core.spotify_track(spotify_track_id),

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_song_isrc
        UNIQUE (song_id, isrc),

    CONSTRAINT uq_isrc
        UNIQUE (isrc)
);

CREATE INDEX IF NOT EXISTS idx_song_isrc_song_id
    ON core.song_isrc (song_id);


-- YOUTUBE CHANNEL
CREATE TABLE IF NOT EXISTS core.youtube_channel (
    channel_id      TEXT PRIMARY KEY,

    channel_name    TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- YOUTUBE VIDEO
CREATE TABLE IF NOT EXISTS core.youtube_video (
    video_id            TEXT PRIMARY KEY,

    channel_id          TEXT
        REFERENCES core.youtube_channel(channel_id),

    video_title               TEXT NOT NULL,
    normalized_video_title    TEXT NOT NULL,

    song_title            TEXT,
    normalized_song_title TEXT,

    artist_name            TEXT,
    normalized_artist_name TEXT,

    published_at        TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_youtube_channel_id
    ON core.youtube_video (channel_id);

CREATE INDEX IF NOT EXISTS idx_youtube_normalized_video_title
    ON core.youtube_video (normalized_video_title);

CREATE INDEX IF NOT EXISTS idx_youtube_normalized_song_title
    ON core.youtube_video (normalized_song_title);

CREATE INDEX IF NOT EXISTS idx_youtube_normalized_artist_name
    ON core.youtube_video (normalized_artist_name);


-- SONG ↔ YOUTUBE VIDEO
CREATE TABLE IF NOT EXISTS core.song_youtube_video (
    song_id          BIGINT NOT NULL
        REFERENCES core.song(song_id),

    video_id         TEXT NOT NULL
        REFERENCES core.youtube_video(video_id),

    match_method     TEXT,

    match_confidence NUMERIC(5,4),

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (song_id, video_id),

    CONSTRAINT chk_match_confidence
        CHECK (
            match_confidence IS NULL
            OR match_confidence BETWEEN 0 AND 1
        )
);

CREATE INDEX IF NOT EXISTS idx_song_youtube_song_id
    ON core.song_youtube_video (song_id);



-- Purpose: Denormalized, pre-joined tables and views optimized for BI and fast analytical querying.
CREATE SCHEMA IF NOT EXISTS mart;

-- Denormalized Wide Table for Song Cross-Platform Matching & Reporting
CREATE TABLE IF NOT EXISTS mart.fact_song_cross_platform_matches (
    song_id BIGINT PRIMARY KEY,
    recording_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    release_date DATE,
    album_id TEXT,
    album_name TEXT,
    artist_ids TEXT[],
    artist_names TEXT[],
    spotify_track_id BIGINT,
    isrc TEXT,
    youtube_video_id TEXT,
    youtube_video_title TEXT,
    youtube_channel_id TEXT,
    youtube_channel_name TEXT,
    match_method TEXT,
    match_confidence NUMERIC(5,4),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mart_cross_match_confidence ON mart.fact_song_cross_platform_matches (match_confidence);
CREATE INDEX IF NOT EXISTS idx_mart_cross_match_isrc ON mart.fact_song_cross_platform_matches (isrc);

-- Aggregated Mart Table for Artist Coverage & Matching Performance
CREATE TABLE IF NOT EXISTS mart.agg_artist_platform_coverage (
    artist_id TEXT PRIMARY KEY,
    artist_name TEXT NOT NULL,
    total_songs BIGINT NOT NULL DEFAULT 0,
    songs_with_spotify BIGINT NOT NULL DEFAULT 0,
    songs_with_youtube_match BIGINT NOT NULL DEFAULT 0,
    avg_match_confidence NUMERIC(5,4),
    last_computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mart_agg_artist_name ON mart.agg_artist_platform_coverage (artist_name);
