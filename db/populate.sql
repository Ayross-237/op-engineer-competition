-- Sample data covering every table in db/schema.sql.
-- Assumes a clean DB (run db/reset.sql then db/schema.sql first) so that
-- GENERATED ALWAYS AS IDENTITY produces predictable IDs starting at 1.

-- Caterers → IDs 1..4
-- chef_email left NULL where the contact is also the chef (single point of contact).
INSERT INTO caterers (name, region, contact_email, chef_email, cc_chef) VALUES
    ('Lakehouse Victoria Point', 'Redlands',         'orders@lakehousevp.com.au',  'chef@lakehousevp.com.au', TRUE),
    ('Terrific Noodles',         'South Brisbane',   'hello@terrificnoodles.com',  NULL,                      FALSE),
    ('Kenko Sushi House',        'West Brisbane',    'orders@kenkosushi.com.au',   'kitchen@kenkosushi.com.au', TRUE),
    ('Guzman y Gomez',           'Central Brisbane', 'catering@gyg.com.au',        NULL,                      FALSE);

-- Pricing structures (1:1 with caterers)
INSERT INTO pricing_structures (caterer_id, price_per_item, flat_delivery_fee, per_trip_fee, per_school_fee) VALUES
    (1, 35.00, 0,     0,     0),
    (2, 20.50, 0,     0,     30.00),
    (3,  5.50, 0,     0,     10.00),
    (4, 15.00, 0,     50.00, 0);

-- Menu items. Source menus use VO ("vegetarian option") to mean the dish can be
-- prepared either way; each such item is split into a non-veg row and a (Vegetarian) row.
INSERT INTO items (caterer_id, name, dietary_tags) VALUES
    (1, 'Shrimp Fried Rice',                                '{GF,DF,H}'),
    (1, 'Spaghetti Bolognese + Garlic Bread',               '{NF,H}'),
    (1, 'Sweet and Sour Chicken',                           '{GF,DF,NF,H}'),
    (1, 'Japanese Chicken Curry',                           '{DF,NF,H}'),
    (1, 'Japanese Chicken Curry (Vegetarian)',              '{DF,NF,V,H}'),
    (2, 'Spicy Miso Udon',                                  '{DF,H}'),
    (2, 'Mie Goreng',                                       '{GF,DF,NF,H}'),
    (2, 'Mie Goreng (Vegetarian)',                          '{GF,DF,NF,V,H}'),
    (2, 'Beef Pad Thai',                                    '{H}'),
    (2, 'Lemongrass Grilled Beef and Noodles',              '{GF,DF,NF,H}'),
    (2, 'Lemongrass Grilled Beef and Noodles (Vegetarian)', '{GF,DF,NF,V,H}'),
    (3, 'Teriyaki Salmon rice bowl',                        '{GF,DF,NF,H}'),
    (3, 'Teriyaki Salmon rice bowl (Vegetarian)',           '{GF,DF,NF,V,H}'),
    (3, 'Chicken Karaage ricebowl',                         '{DF,NF,H}'),
    (3, 'Chicken Karaage ricebowl (Vegetarian)',            '{DF,NF,V,H}'),
    (3, 'Sweet and Sour Chicken',                           '{GF,DF,H}'),
    (4, 'Caesar Salad',                                     '{GF,DF,NF,H}'),
    (4, 'Caesar Salad (Vegetarian)',                        '{GF,DF,NF,V,H}'),
    (4, 'Chicken Enchilada',                                '{GF,DF,H}'),
    (4, 'Nachos',                                           '{GF,H}'),
    (4, 'Nachos (Vegetarian)',                              '{GF,V,H}'),
    (4, 'Pulled pork burrito bowl',                         '{GF,NF}'),
    (4, 'Pulled pork burrito bowl (Vegetarian)',            '{GF,NF,V,H}');

-- Schools → IDs 1..4 (each assigned a caterer)
INSERT INTO schools (name, region, caterer_id) VALUES
    ('Moreton Bay Boys'' College',      'Redlands',         1),
    ('John Paul College',               'South Brisbane',   2),
    ('Indooroopilly State High School', 'West Brisbane',    3),
    ('Loreto College',                  'Central Brisbane', 4);

-- Programs → IDs 1..4 (one program per school: the weekly recurring tutoring slot)
INSERT INTO programs (school_id, day_of_week, start_time, end_time, dinner_time, building, year_levels, manager_name, manager_mobile) VALUES
    (1, 'Tuesday', '16:00', '19:00', '17:30', 'Library',       '{12,11}',      'Triet',  '0469 420 067'),
    (2, 'Tuesday', '16:30', '19:30', '18:00', 'G Centre',      '{12,11,10,9}', 'Jessie', '0412 345 678'),
    (3, 'Monday',  '15:30', '18:30', '17:00', 'X Block',       '{12,11,10,9}', 'Lucian', '0412 233 445'),
    (4, 'Monday',  '15:30', '18:30', '17:00', 'Ella Building', '{12,11,10}',   'Claire', '0488 888 888');

-- Sessions → specific dated occurrences of a program.
-- sub_manager_* populated only when the regular manager is not running that session.
INSERT INTO sessions (program_id, date, sub_manager_name, sub_manager_mobile) VALUES
    (1, '2026-05-26', NULL,    NULL),
    (1, '2026-06-02', NULL,    NULL),
    (2, '2026-05-26', 'Mia C', '0455 111 222'),
    (2, '2026-06-02', NULL,    NULL),
    (3, '2026-06-01', NULL,    NULL),
    (4, '2026-06-01', NULL,    NULL);

-- Students → IDs 1..20 (mix of dietary requirements within the GF/DF/NF/V/H enum)
-- Holly Hill and Grace Stevenson are opted out of catering (wants_catering = FALSE) to exercise that path.
-- dietary_extra is populated only when the requirement can't be expressed by the GF/DF/NF/V/H tags
-- (e.g. a specific allergy outside the enum, or a non-vegetarian eating pattern).
INSERT INTO students (name, year_level, dietary, dietary_extra, wants_catering, student_email, parent_name, parent_email, parent_mobile) VALUES
    ('Henry Hill',       11, '{}',    NULL,                                       TRUE,  'henryhill@mbbc.qld.edu.au',              'Ryan Hill',       'ryanhill@iinet.net.au',       '0478 813 748'),
    ('Noah Baker',       12, '{}',    NULL,                                       TRUE,  'noahbaker@outlook.com',                  'Eliza Baker',     'elizabaker@iinet.net.au',     '0454 745 547'),
    ('Rashid Khalil',     9, '{H,V}', NULL,                                       TRUE,  'rashidkhalil@student.jpc.qld.edu.au',    'Fatima Khalil',   'fatimakhalil@iinet.net.au',   '0487 414 081'),
    ('Benjamin Wilson',  12, '{}',    NULL,                                       TRUE,  'benjaminwilson@student.jpc.qld.edu.au',  'Aria Wilson',     'ariawilson@live.com',         '0458 480 893'),
    ('Sara Abdallah',    10, '{H}',   'No shellfish',                             TRUE,  'saraabdallah@gmail.com',                 'Samir Abdallah',  'samirabdallah@live.com',      '0411 229 871'),
    ('Sophie Harris',    12, '{V}',   NULL,                                       TRUE,  'sophieharris@eq.edu.au',                 'Tristan Harris',  'tristanharris@hotmail.com',   '0421 889 323'),
    ('Holly Hill',       10, '{}',    NULL,                                       FALSE, 'hollyhill@gmail.com',                    'Benjamin Hill',   'benjaminhill@yahoo.com',      '0445 718 173'),
    ('Matilda Turner',   11, '{DF}',  NULL,                                       TRUE,  'matildaturner@loreto.qld.edu.au',        'Phoebe Turner',   'phoebeturner@yahoo.com',      '0467 957 174'),
    ('Oliver Bennett',   11, '{GF}',  NULL,                                       TRUE,  'oliverbennett@mbbc.qld.edu.au',          'Megan Bennett',   'meganbennett@outlook.com',    '0432 118 909'),
    ('Leo Marsh',        12, '{V}',   NULL,                                       TRUE,  'leomarsh@mbbc.qld.edu.au',               'Diana Marsh',     'dianamarsh@iinet.net.au',     '0498 332 415'),
    ('Ethan Mitchell',   11, '{NF}',  NULL,                                       TRUE,  'ethanmitchell@mbbc.qld.edu.au',          'Nina Mitchell',   'ninamitchell@gmail.com',      '0419 776 224'),
    ('Aisha Khan',       10, '{H}',   'Severe egg allergy',                       TRUE,  'aishakhan@student.jpc.qld.edu.au',       'Yasmin Khan',     'yasminkhan@hotmail.com',      '0488 102 553'),
    ('Lucas Nguyen',      9, '{}',    NULL,                                       TRUE,  'lucasnguyen@student.jpc.qld.edu.au',     'Minh Nguyen',     'minhnguyen@outlook.com',      '0426 519 880'),
    ('Mia Chen',         12, '{}',    'Pescatarian — fish only, no other meat',   TRUE,  'miachen@student.jpc.qld.edu.au',         'Hua Chen',        'huachen@gmail.com',           '0461 778 092'),
    ('Tom Whitfield',    11, '{DF}',  NULL,                                       TRUE,  'tomwhitfield@student.jpc.qld.edu.au',    'Greg Whitfield',  'gregwhitfield@iinet.net.au',  '0407 224 631'),
    ('Jackson O''Brien',  9, '{}',    NULL,                                       TRUE,  'jacksonobrien@eq.edu.au',                'Sean O''Brien',   'seanobrien@live.com',         '0421 045 992'),
    ('Ava Robinson',     11, '{DF}',  NULL,                                       TRUE,  'avarobinson@eq.edu.au',                  'Holly Robinson',  'hollyrobinson@yahoo.com',     '0418 663 207'),
    ('Liam Kowalski',    10, '{GF}',  NULL,                                       TRUE,  'liamkowalski@eq.edu.au',                 'Petra Kowalski',  'petrakowalski@outlook.com',   '0432 891 116'),
    ('Isla Thompson',    12, '{V,H}', NULL,                                       TRUE,  'islathompson@loreto.qld.edu.au',         'Claire Thompson', 'clairethompson@gmail.com',    '0429 553 110'),
    ('Grace Stevenson',  10, '{}',    NULL,                                       FALSE, 'gracestevenson@loreto.qld.edu.au',       'Adam Stevenson',  'adamstevenson@live.com',      '0455 002 174');

-- Enrolments (student → program: the weekly slot they signed up for)
INSERT INTO enrolments (student_id, program_id) VALUES
    -- Moreton Bay (program 1)
    (1, 1), (2, 1), (9, 1), (10, 1), (11, 1),
    -- John Paul College (program 2)
    (3, 2), (4, 2), (12, 2), (13, 2), (14, 2), (15, 2),
    -- Indooroopilly (program 3)
    (5, 3), (6, 3), (16, 3), (17, 3), (18, 3),
    -- Loreto (program 4)
    (7, 4), (8, 4), (19, 4), (20, 4);

-- Absences: students who won't be at a specific dated session of their program.
INSERT INTO absences (student_id, program_id, date) VALUES
    (2, 1, '2026-06-02'),  -- Noah Baker missing the second Moreton Bay session
    (5, 3, '2026-06-01');  -- Sara Abdallah missing Indooroopilly on 1 June
