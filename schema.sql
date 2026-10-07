-- =====================================================================
-- Campus Facility Maintenance Request Management System (Campus FMS)
-- Review 1 Exact Schema Definition for MySQL 8.0+
-- Database: campus_fms (Only campus_fms is created/modified)
-- =====================================================================

DROP DATABASE IF EXISTS campus_fms;
CREATE DATABASE campus_fms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE campus_fms;

-- 1. Users
CREATE TABLE Users (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(120) NOT NULL UNIQUE,
    Phone VARCHAR(25) NULL,
    PasswordHash VARCHAR(255) NOT NULL,
    Role ENUM('student_staff', 'facility_admin', 'technician', 'management') NOT NULL,
    Dept VARCHAR(100) NULL,
    INDEX idx_users_role (Role),
    INDEX idx_users_email (Email)
) ENGINE=InnoDB;

-- 2. Buildings
CREATE TABLE Buildings (
    BuildingID INT AUTO_INCREMENT PRIMARY KEY,
    BuildingName VARCHAR(100) NOT NULL UNIQUE,
    Address VARCHAR(255) NULL
) ENGINE=InnoDB;

-- 3. Facilities
CREATE TABLE Facilities (
    FacilityID INT AUTO_INCREMENT PRIMARY KEY,
    BuildingID INT NOT NULL,
    RoomNo VARCHAR(50) NOT NULL,
    Floor VARCHAR(20) NULL,
    Type VARCHAR(50) NULL,
    CONSTRAINT fk_facilities_building FOREIGN KEY (BuildingID) REFERENCES Buildings(BuildingID) ON DELETE CASCADE,
    INDEX idx_facilities_building (BuildingID)
) ENGINE=InnoDB;

-- 4. Categories
CREATE TABLE Categories (
    CategoryID INT AUTO_INCREMENT PRIMARY KEY,
    CategoryName VARCHAR(100) NOT NULL UNIQUE,
    Description VARCHAR(255) NULL
) ENGINE=InnoDB;

-- 5. Priorities
CREATE TABLE Priorities (
    PriorityID INT AUTO_INCREMENT PRIMARY KEY,
    Label VARCHAR(50) NOT NULL UNIQUE,
    SLAHours INT NOT NULL
) ENGINE=InnoDB;

-- 6. Assets
CREATE TABLE Assets (
    AssetID INT AUTO_INCREMENT PRIMARY KEY,
    AssetName VARCHAR(100) NOT NULL,
    CategoryID INT NOT NULL,
    FacilityID INT NOT NULL,
    Status VARCHAR(50) NOT NULL DEFAULT 'Operational',
    CONSTRAINT fk_assets_category FOREIGN KEY (CategoryID) REFERENCES Categories(CategoryID) ON DELETE CASCADE,
    CONSTRAINT fk_assets_facility FOREIGN KEY (FacilityID) REFERENCES Facilities(FacilityID) ON DELETE CASCADE,
    INDEX idx_assets_category (CategoryID),
    INDEX idx_assets_facility (FacilityID)
) ENGINE=InnoDB;

-- 7. Technicians (supports multiple skills per technician user)
CREATE TABLE Technicians (
    TechID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    Skill VARCHAR(100) NOT NULL,
    Available BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_tech_user FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    INDEX idx_tech_user (UserID),
    INDEX idx_tech_skill (Skill)
) ENGINE=InnoDB;

-- 8. Requests (Redundant columns room, priority text, assigned tech removed)
CREATE TABLE Requests (
    RequestID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    FacilityID INT NOT NULL,
    CategoryID INT NOT NULL,
    PriorityID INT NOT NULL,
    Description TEXT NOT NULL,
    Status ENUM('Open', 'Assigned', 'In Progress', 'Resolved', 'Closed') NOT NULL DEFAULT 'Open',
    RequestDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_requests_user FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    CONSTRAINT fk_requests_facility FOREIGN KEY (FacilityID) REFERENCES Facilities(FacilityID) ON DELETE CASCADE,
    CONSTRAINT fk_requests_category FOREIGN KEY (CategoryID) REFERENCES Categories(CategoryID) ON DELETE CASCADE,
    CONSTRAINT fk_requests_priority FOREIGN KEY (PriorityID) REFERENCES Priorities(PriorityID) ON DELETE CASCADE,
    INDEX idx_requests_status (Status),
    INDEX idx_requests_user (UserID),
    INDEX idx_requests_facility (FacilityID),
    INDEX idx_requests_category (CategoryID)
) ENGINE=InnoDB;

-- 9. Assignments (supports multiple technicians per request)
CREATE TABLE Assignments (
    AssignID INT AUTO_INCREMENT PRIMARY KEY,
    RequestID INT NOT NULL,
    TechID INT NOT NULL,
    AssignedOn DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_assignments_request FOREIGN KEY (RequestID) REFERENCES Requests(RequestID) ON DELETE CASCADE,
    CONSTRAINT fk_assignments_tech FOREIGN KEY (TechID) REFERENCES Technicians(TechID) ON DELETE CASCADE,
    INDEX idx_assignments_request (RequestID),
    INDEX idx_assignments_tech (TechID)
) ENGINE=InnoDB;

-- 10. WorkLogs
CREATE TABLE WorkLogs (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    AssignID INT NOT NULL,
    WorkDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    WorkDescription TEXT NOT NULL,
    CONSTRAINT fk_worklogs_assign FOREIGN KEY (AssignID) REFERENCES Assignments(AssignID) ON DELETE CASCADE,
    INDEX idx_worklogs_assign (AssignID)
) ENGINE=InnoDB;

-- 11. Materials
CREATE TABLE Materials (
    MatID INT AUTO_INCREMENT PRIMARY KEY,
    LogID INT NOT NULL,
    MaterialName VARCHAR(150) NOT NULL,
    Qty INT NOT NULL DEFAULT 1,
    Cost DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT fk_materials_log FOREIGN KEY (LogID) REFERENCES WorkLogs(LogID) ON DELETE CASCADE,
    INDEX idx_materials_log (LogID)
) ENGINE=InnoDB;

-- 12. StatusHistory (Audit log populated automatically by DB Trigger)
CREATE TABLE StatusHistory (
    HistID INT AUTO_INCREMENT PRIMARY KEY,
    RequestID INT NOT NULL,
    OldStatus VARCHAR(50) NULL,
    NewStatus VARCHAR(50) NOT NULL,
    ChangedOn DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_history_request FOREIGN KEY (RequestID) REFERENCES Requests(RequestID) ON DELETE CASCADE,
    INDEX idx_history_request (RequestID)
) ENGINE=InnoDB;

-- 13. Feedback
CREATE TABLE Feedback (
    FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
    RequestID INT NOT NULL UNIQUE,
    UserID INT NOT NULL,
    Rating INT NOT NULL CHECK (Rating >= 1 AND Rating <= 5),
    Comments TEXT NULL,
    FeedbackDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_feedback_request FOREIGN KEY (RequestID) REFERENCES Requests(RequestID) ON DELETE CASCADE,
    CONSTRAINT fk_feedback_user FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE,
    INDEX idx_feedback_request (RequestID)
) ENGINE=InnoDB;

-- 14. LoginAttempts (Security: tracks failed logins and 15-min account lockouts)
CREATE TABLE IF NOT EXISTS LoginAttempts (
    AttemptID INT AUTO_INCREMENT PRIMARY KEY,
    Email VARCHAR(150) NOT NULL,
    IPAddress VARCHAR(45) NOT NULL,
    AttemptTime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    IsSuccess TINYINT(1) NOT NULL DEFAULT 0,
    INDEX idx_login_email_time (Email, AttemptTime),
    INDEX idx_login_ip_time (IPAddress, AttemptTime)
) ENGINE=InnoDB;

-- 15. AuditLog (Enterprise security audit trail: logins, assignments, status changes, user creations)
CREATE TABLE IF NOT EXISTS AuditLog (
    LogID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NULL,
    Action VARCHAR(100) NOT NULL,
    Details TEXT NULL,
    IP VARCHAR(45) NOT NULL,
    Timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE SET NULL,
    INDEX idx_audit_user (UserID),
    INDEX idx_audit_action (Action),
    INDEX idx_audit_time (Timestamp)
) ENGINE=InnoDB;

-- 16. Database Triggers for Automatic Status Change Logging
DROP TRIGGER IF EXISTS trg_requests_status_insert;
DROP TRIGGER IF EXISTS trg_requests_status_update;
DROP TRIGGER IF EXISTS trg_requests_insert_history;
DELIMITER $$
CREATE TRIGGER trg_requests_insert_history
AFTER INSERT ON Requests
FOR EACH ROW
BEGIN
    INSERT INTO StatusHistory (RequestID, OldStatus, NewStatus, ChangedOn)
    VALUES (NEW.RequestID, NULL, NEW.Status, NOW());
END$$
DELIMITER ;

DROP TRIGGER IF EXISTS trg_requests_update_history;
DELIMITER $$
CREATE TRIGGER trg_requests_update_history
AFTER UPDATE ON Requests
FOR EACH ROW
BEGIN
    IF OLD.Status <> NEW.Status THEN
        -- Forward-only validation: Open -> Assigned -> In Progress -> Resolved -> Closed
        IF NOT (
            (OLD.Status = 'Open' AND NEW.Status = 'Assigned') OR
            (OLD.Status = 'Assigned' AND NEW.Status = 'In Progress') OR
            (OLD.Status = 'In Progress' AND NEW.Status = 'Resolved') OR
            (OLD.Status = 'Resolved' AND NEW.Status = 'Closed')
        ) THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Invalid status transition. Status can only move forward: Open -> Assigned -> In Progress -> Resolved -> Closed';
        ELSE
            INSERT INTO StatusHistory (RequestID, OldStatus, NEWStatus, ChangedOn)
            VALUES (NEW.RequestID, OLD.Status, NEW.Status, NOW());
        END IF;
    END IF;
END$$
DELIMITER ;
