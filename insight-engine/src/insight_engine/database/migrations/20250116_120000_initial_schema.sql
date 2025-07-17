-- UP
-- Create users table
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_superuser BOOLEAN DEFAULT FALSE NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Create indexes for users table
CREATE INDEX idx_user_email_active ON users(email, is_active);
CREATE INDEX idx_user_username_active ON users(username, is_active);

-- Create videos table
CREATE TABLE videos (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    duration_seconds REAL CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    gcs_path VARCHAR(500) UNIQUE NOT NULL,
    processing_status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    processing_error TEXT,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    transcript TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for videos table
CREATE INDEX idx_video_user_status ON videos(user_id, processing_status);
CREATE INDEX idx_video_user_created ON videos(user_id, created_at);
CREATE INDEX idx_video_status_created ON videos(processing_status, created_at);
CREATE INDEX idx_video_gcs_path ON videos(gcs_path);

-- Create video_clips table
CREATE TABLE video_clips (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time REAL NOT NULL CHECK (start_time >= 0),
    end_time REAL NOT NULL CHECK (end_time > 0),
    duration REAL NOT NULL,
    gcs_path VARCHAR(500) UNIQUE NOT NULL,
    confidence_score REAL CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
    query_used VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CHECK (start_time < end_time),
    CHECK (duration = end_time - start_time)
);

-- Create indexes for video_clips table
CREATE INDEX idx_clip_video_time ON video_clips(video_id, start_time, end_time);
CREATE INDEX idx_clip_video_created ON video_clips(video_id, created_at);
CREATE INDEX idx_clip_confidence ON video_clips(confidence_score);

-- DOWN
-- Drop tables in reverse order due to foreign key constraints
DROP TABLE IF EXISTS video_clips;
DROP TABLE IF EXISTS videos;
DROP TABLE IF EXISTS users;