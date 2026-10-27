-- RoadGuard v2 upgrades. Safe to run again: every step checks first.
-- (init_db.py runs schema.sql, then this file.)

-- Accounts: forced password change after an admin reset, and "log out other sessions"
IF COL_LENGTH('Users', 'must_change_password') IS NULL
ALTER TABLE Users ADD must_change_password BIT NOT NULL CONSTRAINT DF_Users_mcp DEFAULT 0;

IF COL_LENGTH('Users', 'token_version') IS NULL
ALTER TABLE Users ADD token_version INT NOT NULL CONSTRAINT DF_Users_tv DEFAULT 0;

-- CCTV / IP camera streams
IF COL_LENGTH('Cameras', 'stream_url') IS NULL
ALTER TABLE Cameras ADD stream_url NVARCHAR(400) NULL;

IF COL_LENGTH('Cameras', 'stream_enabled') IS NULL
ALTER TABLE Cameras ADD stream_enabled BIT NOT NULL CONSTRAINT DF_Cameras_se DEFAULT 0;

-- Jobs can now also be 'stream' (a camera being watched in the background)
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_Jobs_kind_v2')
BEGIN
    DECLARE @old NVARCHAR(200);
    SELECT @old = cc.name FROM sys.check_constraints cc
      JOIN sys.columns c ON c.object_id = cc.parent_object_id AND c.column_id = cc.parent_column_id
     WHERE cc.parent_object_id = OBJECT_ID('Jobs') AND c.name = 'kind';
    IF @old IS NOT NULL EXEC('ALTER TABLE Jobs DROP CONSTRAINT [' + @old + ']');
    ALTER TABLE Jobs ADD CONSTRAINT CK_Jobs_kind_v2 CHECK (kind IN ('image', 'video', 'live', 'stream'));
END;

-- Challans: paid / unpaid / cancelled (after an accepted appeal)
IF COL_LENGTH('Challans', 'status') IS NULL
ALTER TABLE Challans ADD status NVARCHAR(20) NOT NULL CONSTRAINT DF_Challans_status DEFAULT 'unpaid'
    CONSTRAINT CK_Challans_status CHECK (status IN ('unpaid', 'paid', 'cancelled'));

IF COL_LENGTH('Challans', 'paid_at') IS NULL
ALTER TABLE Challans ADD paid_at DATETIME2 NULL;

IF COL_LENGTH('Challans', 'payment_ref') IS NULL
ALTER TABLE Challans ADD payment_ref NVARCHAR(40) NULL;

-- "Request access" from the login page, approved by an admin
IF OBJECT_ID('AccessRequests') IS NULL
CREATE TABLE AccessRequests (
    request_id      INT IDENTITY PRIMARY KEY,
    full_name       NVARCHAR(100) NOT NULL,
    email           NVARCHAR(150) NOT NULL,
    organisation    NVARCHAR(150) NULL,
    reason          NVARCHAR(400) NULL,
    requested_role  NVARCHAR(20) NOT NULL CHECK (requested_role IN ('officer', 'viewer')),
    status          NVARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    decided_by      INT NULL REFERENCES Users(user_id),
    decided_at      DATETIME2 NULL,
    ip_address      NVARCHAR(50) NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

-- Citizen appeals against a challan
IF OBJECT_ID('Appeals') IS NULL
CREATE TABLE Appeals (
    appeal_id       INT IDENTITY PRIMARY KEY,
    challan_id      INT NOT NULL REFERENCES Challans(challan_id),
    reason          NVARCHAR(1000) NOT NULL,
    contact         NVARCHAR(100) NULL,
    status          NVARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    response        NVARCHAR(500) NULL,
    decided_by      INT NULL REFERENCES Users(user_id),
    decided_at      DATETIME2 NULL,
    created_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
