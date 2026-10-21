BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 62243260b0ef

CREATE TABLE users (
    id VARCHAR(36) NOT NULL, 
    email VARCHAR(320) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    password_hash TEXT, 
    picture TEXT, 
    provider VARCHAR(20) NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email)
);

CREATE TABLE repositories (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    name VARCHAR(200) NOT NULL, 
    source VARCHAR(20) NOT NULL, 
    source_url TEXT, 
    branch VARCHAR(200), 
    archive_key TEXT, 
    archive_sha256 VARCHAR(64), 
    source_commit VARCHAR(40), 
    active_job_id VARCHAR(36), 
    status VARCHAR(30) NOT NULL, 
    progress INTEGER NOT NULL, 
    message TEXT, 
    language_breakdown JSON NOT NULL, 
    stats JSON NOT NULL, 
    file_manifest JSON NOT NULL, 
    timeline JSON NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_repos_owner_created ON repositories (user_id, created_at);

CREATE INDEX ix_repositories_status ON repositories (status);

CREATE INDEX ix_repositories_user_id ON repositories (user_id);

CREATE TABLE user_settings (
    user_id VARCHAR(36) NOT NULL, 
    key VARCHAR(80) NOT NULL, 
    value JSON NOT NULL, 
    PRIMARY KEY (user_id, key), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_setting UNIQUE (user_id, key)
);

CREATE TABLE activity_events (
    id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36), 
    type VARCHAR(80) NOT NULL, 
    message TEXT NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_activity_events_repo_id ON activity_events (repo_id);

CREATE INDEX ix_activity_events_user_id ON activity_events (user_id);

CREATE TABLE conversations (
    id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    title VARCHAR(100) NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_conversations_repo_id ON conversations (repo_id);

CREATE INDEX ix_conversations_repo_updated ON conversations (repo_id, updated_at);

CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE documentation (
    id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    doc_type VARCHAR(80) NOT NULL, 
    content TEXT NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_document_type UNIQUE (repo_id, user_id, doc_type)
);

CREATE INDEX ix_documentation_repo_id ON documentation (repo_id);

CREATE INDEX ix_documentation_user_id ON documentation (user_id);

CREATE TABLE jobs (
    id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    attempts INTEGER NOT NULL, 
    next_run_at FLOAT NOT NULL, 
    lease_until FLOAT NOT NULL, 
    lease_token VARCHAR(36), 
    cancel_requested BOOLEAN NOT NULL, 
    error TEXT, 
    details JSON NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_jobs_claim ON jobs (status, next_run_at, lease_until);

CREATE INDEX ix_jobs_repo_id ON jobs (repo_id);

CREATE INDEX ix_jobs_user_id ON jobs (user_id);

CREATE TABLE reviews (
    id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    progress INTEGER NOT NULL, 
    overall_score INTEGER NOT NULL, 
    summary TEXT NOT NULL, 
    action_plan JSON NOT NULL, 
    agents JSON NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_reviews_repo_id ON reviews (repo_id);

CREATE INDEX ix_reviews_user_id ON reviews (user_id);

CREATE TABLE memories (
    id VARCHAR(36) NOT NULL, 
    repo_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    source VARCHAR(20) NOT NULL, 
    category VARCHAR(80) NOT NULL, 
    title VARCHAR(300) NOT NULL, 
    description TEXT NOT NULL, 
    severity VARCHAR(20) NOT NULL, 
    confidence FLOAT NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    file_path TEXT, 
    symbol TEXT, 
    tags JSON NOT NULL, 
    review_id VARCHAR(36), 
    finding_id VARCHAR(36), 
    created_at VARCHAR(40) NOT NULL, 
    updated_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(repo_id) REFERENCES repositories (id) ON DELETE CASCADE, 
    FOREIGN KEY(review_id) REFERENCES reviews (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_memory_finding UNIQUE (user_id, finding_id)
);

CREATE INDEX ix_memories_owner_status ON memories (user_id, status);

CREATE INDEX ix_memories_repo_id ON memories (repo_id);

CREATE INDEX ix_memories_user_id ON memories (user_id);

CREATE TABLE messages (
    id VARCHAR(36) NOT NULL, 
    conversation_id VARCHAR(36) NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    context_nodes JSON NOT NULL, 
    sources JSON NOT NULL, 
    relationships JSON NOT NULL, 
    created_at VARCHAR(40) NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX ix_messages_conversation_created ON messages (conversation_id, created_at);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

INSERT INTO alembic_version (version_num) VALUES ('62243260b0ef') RETURNING alembic_version.version_num;

-- Running upgrade 62243260b0ef -> b17006a91f42

ALTER TABLE users ADD COLUMN google_subject VARCHAR(255);

CREATE UNIQUE INDEX uq_users_google_subject ON users (google_subject);

UPDATE alembic_version SET version_num='b17006a91f42' WHERE alembic_version.version_num = '62243260b0ef';

COMMIT;

