-- =====================================================================
-- Campus Facility Maintenance Request Management System (Campus FMS)
-- Review 1 Seed Data for MySQL (campus_fms)
-- =====================================================================

USE campus_fms;

-- 1. Users
-- Passwords hashed using Werkzeug scrypt (student123, staff123, admin123, tech123, mgmt123)
INSERT INTO Users (UserID, Name, Email, Phone, PasswordHash, Role, Dept) VALUES
(1, 'Alex Chen', 'alex.student@campus.edu', '555-0101', 'scrypt:32768:8:1$ja8yIPuldOwjCK2X$a8bb84dc3752b9e8a8376ff9b8d825b9a54cddbbf1519c3484b263c1bbf8be5730946bf58fba04726915bfa8e105a03ba174c825e7667662fd4a769b13e7d6cc', 'student_staff', 'Computer Science'),
(2, 'Prof. Sarah Jenkins', 'sarah.faculty@campus.edu', '555-0102', 'scrypt:32768:8:1$p3B1TMTBPrSG2Pi7$9be75f387b2ec60e1a6346533354596bde4074eb209d8de71161b59fde542fdab451411633f86e7c61a74fba1ee6faca5f6bc6f51bedb438e8fa70824e403268', 'student_staff', 'Biological Sciences'),
(3, 'Marcus Vance', 'marcus.admin@campus.edu', '555-0201', 'scrypt:32768:8:1$AWlV0FNMWyp1YiAS$154c2803d3e815ae0678a2b2cb818de3e2e69305fdfa82391e013e4b50356206d04bf50f1bf9d9ff70b554f3e4160e48893a82edf62557e4bf2525d424ed5a8e', 'facility_admin', 'Campus Facilities'),
(4, 'Carlos Mendez', 'carlos.electrician@campus.edu', '555-0301', 'scrypt:32768:8:1$YukPEZOGeWAniOFo$e50d87e7c3bf661a221f00d7e904c8d5001ee5c24a543bc8aeb7025b797d23637c29852a12a4a4cc00b04982cc07a84f8371f14354442e30b5846bb84bf761b1', 'technician', 'Maintenance'),
(5, 'Elena Rostova', 'elena.plumber@campus.edu', '555-0302', 'scrypt:32768:8:1$njYBVAN5DNW01t0G$0f98e7a31b000fbb60b1e09e6146bf356369bd1e3376f00ea7e82899cb7958d6aec16691cb80fc83f3ab4ff7ab4ba71a7472f879f263168435888c880630cb0e', 'technician', 'Maintenance'),
(6, 'David Kim', 'david.network@campus.edu', '555-0303', 'scrypt:32768:8:1$LojyG12cq9yPIhas$09ef73890491846c285223ae346d0c35cf67fd4c59a1d6e961bfa6406c62d566525fa008e9018e427f90a0fe83d11d08898c057a580b16e838b4545603691e38', 'technician', 'IT Infrastructure'),
(7, 'Robert Green', 'robert.carpenter@campus.edu', '555-0304', 'scrypt:32768:8:1$ENFmFIasHChD9F8E$f0d90f7e02e3e04fa2a89f4048e337b0da41e060d9942be5c68cea17011f625bee551459ff489c58fb6a3afd7cb17cee34e9bf826c2247f0631f65c516466583', 'technician', 'Carpentry Workshop'),
(8, 'Dr. Arthur Reynolds', 'reynolds.mgmt@campus.edu', '555-0401', 'scrypt:32768:8:1$OYWE1ykteV7rgbWU$99c25397a383b9225e04f4ad376048e2ee2b7253094d3a051d964aa142061e3c316d3cbe5e21d24f55d8299fd29d1d250928aa6710df10e40ea7b12ec00e37bb', 'management', 'Administration');

-- 2. Buildings
INSERT INTO Buildings (BuildingID, BuildingName, Address) VALUES
(1, 'Engineering Block A', 'North Campus Zone 1'),
(2, 'Science Complex', 'Central Science Quad'),
(3, 'Main Academic Building', 'Main Campus Avenue'),
(4, 'Hostel Block 1', 'South Residential Area'),
(5, 'Central Library & Admin Tower', 'East Administrative Zone');

-- 3. Facilities
INSERT INTO Facilities (FacilityID, BuildingID, RoomNo, Floor, Type) VALUES
(1, 1, 'Room 304', '3rd Floor', 'Laboratory'),
(2, 1, 'Room 101', '1st Floor', 'Classroom'),
(3, 2, 'Bio Lab 112', '1st Floor', 'Laboratory'),
(4, 2, 'Lab 204', '2nd Floor', 'Research Lab'),
(5, 3, 'Lecture Hall 402', '4th Floor', 'Auditorium'),
(6, 4, 'Room 215', '2nd Floor', 'Hostel Room'),
(7, 4, 'Corridor 1st Fl', '1st Floor', 'Common Area'),
(8, 5, 'Study Room 108', '1st Floor', 'Study Room'),
(9, 5, 'Admin Office 501', '5th Floor', 'Office');

-- 4. Categories
INSERT INTO Categories (CategoryID, CategoryName, Description) VALUES
(1, 'Electrical', 'Lighting, circuit breakers, power outlets, generators'),
(2, 'Plumbing', 'Leaking pipes, faucets, drainage, washroom fixtures'),
(3, 'HVAC / AC', 'Air conditioning, central heating, ventilation ducts'),
(4, 'Carpentry', 'Doors, locks, desks, windows, furniture repair'),
(5, 'IT / Network Infrastructure', 'Ethernet ports, Wi-Fi access points, projector cables'),
(6, 'Civil / Painting', 'Wall damage, ceiling tiles, masonry, paint touch-ups');

-- 5. Priorities
INSERT INTO Priorities (PriorityID, Label, SLAHours) VALUES
(1, 'Low', 72),
(2, 'Medium', 48),
(3, 'High', 24),
(4, 'Urgent', 12);

-- 6. Assets
INSERT INTO Assets (AssetID, AssetName, CategoryID, FacilityID, Status) VALUES
(1, 'Main Power Distribution Panel', 1, 1, 'Operational'),
(2, 'Central Sink Water Supply Valve', 2, 3, 'Under Maintenance'),
(3, 'Split HVAC AC Unit 2.0 Ton', 3, 6, 'Operational'),
(4, 'Cisco 48-Port Gigabit Switch', 5, 5, 'Operational'),
(5, 'Heavy-Duty Brass Mortise Lock', 4, 8, 'Operational');

-- 7. Technicians (Supports multiple skills per technician)
INSERT INTO Technicians (TechID, UserID, Skill, Available) VALUES
(1, 4, 'Electrical', TRUE),
(2, 4, 'HVAC / AC', TRUE),
(3, 5, 'Plumbing', TRUE),
(4, 5, 'Civil / Painting', TRUE),
(5, 6, 'IT / Network Infrastructure', TRUE),
(6, 7, 'Carpentry', TRUE);

-- 8. Requests (Initial Seed)
-- Note: Trigger will populate StatusHistory on each insert!
INSERT INTO Requests (RequestID, UserID, FacilityID, CategoryID, PriorityID, Description, Status, RequestDate) VALUES
(1, 1, 1, 1, 3, 'Overhead lighting flickering severely and burning smell from ceiling panel.', 'Resolved', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2, 2, 3, 2, 4, 'Severe water leakage beneath central sink creating slipping hazard.', 'In Progress', DATE_SUB(NOW(), INTERVAL 18 HOUR)),
(3, 1, 6, 3, 2, 'Room AC unit is blowing warm air and making loud clicking sound.', 'Assigned', DATE_SUB(NOW(), INTERVAL 10 HOUR)),
(4, 2, 5, 5, 3, 'Podium network switch and ceiling projector disconnected from intranet.', 'Open', DATE_SUB(NOW(), INTERVAL 3 HOUR)),
(5, 1, 8, 4, 1, 'Main door lock cylinder sticking; difficult to latch properly.', 'Open', DATE_SUB(NOW(), INTERVAL 1 HOUR)),
(6, 2, 7, 6, 2, 'Plaster flaking and moisture stains on ceiling near water fountain.', 'Closed', DATE_SUB(NOW(), INTERVAL 5 DAY));

-- 9. Assignments (Multiple technicians per request supported)
INSERT INTO Assignments (AssignID, RequestID, TechID, AssignedOn) VALUES
(1, 1, 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(2, 2, 3, DATE_SUB(NOW(), INTERVAL 18 HOUR)),
(3, 3, 2, DATE_SUB(NOW(), INTERVAL 10 HOUR)),
(4, 6, 4, DATE_SUB(NOW(), INTERVAL 5 DAY));

-- 10. WorkLogs
INSERT INTO WorkLogs (LogID, AssignID, WorkDate, WorkDescription) VALUES
(1, 1, DATE_SUB(NOW(), INTERVAL 1 DAY), 'Replaced blown ballast with modern high-efficiency LED driver. Tested circuit safety.'),
(2, 2, DATE_SUB(NOW(), INTERVAL 8 HOUR), 'Isolated wet lab main line valve and clamped pipe. Sourcing replacement elbow fitting.'),
(3, 4, DATE_SUB(NOW(), INTERVAL 3 DAY), 'Scraped damaged plaster, applied sealant primer and two coats of wall paint.');

-- 11. Materials (Realistic Indian rupee costs)
INSERT INTO Materials (MatID, LogID, MaterialName, Qty, Cost) VALUES
(1, 1, 'Philips 9W LED Bulb', 2, 150.00),
(2, 1, 'Havells 16A MCB Single Pole', 1, 600.00),
(3, 2, 'Astral CPVC Pipe Fitting & PTFE Tape', 1, 400.00),
(4, 2, 'Anchor Modular Electrical Switch 10A', 2, 250.00),
(5, 3, 'Asian Paints Interior Wall Paint 4L', 1, 1800.00);

-- 12. Feedback
INSERT INTO Feedback (FeedbackID, RequestID, UserID, Rating, Comments, FeedbackDate) VALUES
(1, 1, 1, 5, 'Remarkable service! Technician Carlos responded swiftly and the lab lighting is crystal clear now.', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(2, 6, 2, 4, 'Neat finish. Took slightly longer due to paint curing time, but very professional.', DATE_SUB(NOW(), INTERVAL 3 DAY));
