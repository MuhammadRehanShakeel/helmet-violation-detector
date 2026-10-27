-- RoadGuard database schema (Microsoft SQL Server)
-- Run with:  venv\Scripts\python.exe scripts\init_db.py
-- Every table is created only if it does not exist, so running it again is safe.

IF OBJECT_ID('Users') IS NULL
CREATE TABLE Users (
    user_id         INT IDENTITY PRIMARY KEY,
    full_name       NVARCHAR(100) NOT NULL,
    email           NVARCHAR(150) NOT NULL UNIQUE,
    password_hash   NVARCHAR(100) NOT NULL,          -- bcrypt hash, never the password
    role            NVARCHAR(20)  NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('admin', 'officer', 'viewer')),
    is_active       BIT NOT NULL DEFAULT 1,
    failed_logins   INT NOT NULL DEFAULT 0,
    locked_until    DATETIME2 NULL,
    last_login      DATETIME2 NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

IF OBJECT_ID('Cameras') IS NULL
CREATE TABLE Cameras (
    camera_id       INT IDENTITY PRIMARY KEY,
    name            NVARCHAR(100) NOT NULL,
    location        NVARCHAR(200) NULL,
    latitude        DECIMAL(9, 6) NULL,
    longitude       DECIMAL(9, 6) NULL,
    is_active       BIT NOT NULL DEFAULT 1,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

IF OBJECT_ID('Jobs') IS NULL
CREATE TABLE Jobs (
    job_id          INT IDENTITY PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES Users(user_id),
    camera_id       INT NULL REFERENCES Cameras(camera_id),
    kind            NVARCHAR(10) NOT NULL CHECK (kind IN ('image', 'video', 'live')),
    original_name   NVARCHAR(255) NULL,
    stored_path     NVARCHAR(400) NULL,
    status          NVARCHAR(20) NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'done', 'failed')),
    progress        INT NOT NULL DEFAULT 0,
    stage           NVARCHAR(100) NULL,
    motorcyclists   INT NOT NULL DEFAULT 0,          -- bikes seen (unique tracks for videos)
    violations      INT NOT NULL DEFAULT 0,
    seconds_taken   FLOAT NULL,
    error           NVARCHAR(400) NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    finished_at     DATETIME2 NULL
);

IF OBJECT_ID('Violations') IS NULL
CREATE TABLE Violations (
    violation_id    INT IDENTITY PRIMARY KEY,
    job_id          INT NOT NULL REFERENCES Jobs(job_id),
    camera_id       INT NULL REFERENCES Cameras(camera_id),
    violation_type  NVARCHAR(20) NOT NULL CHECK (violation_type IN ('NO_HELMET', 'TRIPLE_RIDING')),
    confidence      FLOAT NOT NULL,
    low_confidence  BIT NOT NULL DEFAULT 0,
    riders          INT NOT NULL DEFAULT 0,
    no_helmet_count INT NOT NULL DEFAULT 0,
    plate_text      NVARCHAR(20) NULL,               -- cleaned, e.g. LEA-1234
    plate_raw       NVARCHAR(60) NULL,               -- what the OCR actually read
    plate_valid     BIT NOT NULL DEFAULT 0,          -- matches the Pakistani plate pattern
    plate_confidence FLOAT NULL,
    frame_time      FLOAT NULL,                      -- seconds into the video
    evidence_file   NVARCHAR(200) NULL,              -- annotated frame (bystanders blurred)
    crop_file       NVARCHAR(200) NULL,              -- the motorcyclist
    plate_file      NVARCHAR(200) NULL,              -- the number plate
    status          NVARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by     INT NULL REFERENCES Users(user_id),
    reviewed_at     DATETIME2 NULL,
    review_note     NVARCHAR(300) NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Violations_Plate')
CREATE INDEX IX_Violations_Plate ON Violations(plate_text);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Violations_Status')
CREATE INDEX IX_Violations_Status ON Violations(status, created_at);

IF OBJECT_ID('Challans') IS NULL
CREATE TABLE Challans (
    challan_id      INT IDENTITY PRIMARY KEY,
    violation_id    INT NOT NULL UNIQUE REFERENCES Violations(violation_id),  -- one challan per violation
    challan_no      NVARCHAR(30) NOT NULL UNIQUE,
    verify_code     NVARCHAR(40) NOT NULL UNIQUE,    -- random, printed as a QR code
    fine_amount     INT NOT NULL,
    issued_by       INT NOT NULL REFERENCES Users(user_id),
    issued_at       DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    pdf_file        NVARCHAR(200) NULL
);

IF OBJECT_ID('AuditLog') IS NULL
CREATE TABLE AuditLog (
    audit_id        INT IDENTITY PRIMARY KEY,
    user_id         INT NULL,
    action          NVARCHAR(50) NOT NULL,
    target          NVARCHAR(100) NULL,
    details         NVARCHAR(400) NULL,
    ip_address      NVARCHAR(50) NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
