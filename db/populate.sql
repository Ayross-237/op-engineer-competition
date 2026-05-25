-- Sample data covering every table in db/schema.sql.
-- Assumes a clean DB (run db/reset.sql then db/schema.sql first) so that
-- GENERATED ALWAYS AS IDENTITY produces predictable IDs starting at 1.

-- Caterers → IDs 1..4
INSERT INTO caterers (name, region) VALUES
    ('Lakehouse Victoria Point', 'Redlands'),
    ('Terrific Noodles',         'South Brisbane'),
    ('Kenko Sushi House',        'West Brisbane'),
    ('Guzman y Gomez',           'Central Brisbane');

-- Pricing structures (1:1 with caterers)
INSERT INTO pricing_structures (caterer_id, price_per_item, flat_delivery_fee, per_trip_fee, per_school_fee) VALUES
    (1, 35.00, 0,     0,     0),
    (2, 20.50, 0,     0,     30.00),
    (3,  5.50, 0,     0,     10.00),
    (4, 15.00, 0,     50.00, 0);

-- Menu items (sample of each caterer's menu, with dietary_tag enum)
INSERT INTO items (caterer_id, name, dietary_tags) VALUES
    (1, 'Shrimp Fried Rice',                   '{GF,DF}'),
    (1, 'Spaghetti Bolognese + Garlic Bread',  '{NF}'),
    (1, 'Sweet and Sour Chicken',              '{GF,DF,NF}'),
    (1, 'Japanese Chicken Curry',              '{DF,NF,V}'),
    (2, 'Spicy Miso Udon',                     '{DF}'),
    (2, 'Mie Goreng',                          '{GF,DF,NF,V}'),
    (2, 'Beef Pad Thai',                       '{}'),
    (2, 'Lemongrass Grilled Beef and Noodles', '{GF,DF,NF,V}'),
    (3, 'Teriyaki Salmon rice bowl',           '{GF,DF,NF,V}'),
    (3, 'Chicken Karaage ricebowl',            '{DF,NF,V}'),
    (3, 'Sweet and Sour Chicken',              '{GF,DF}'),
    (4, 'Caesar Salad',                        '{GF,DF,NF,V}'),
    (4, 'Chicken Enchilada',                   '{GF,DF}'),
    (4, 'Nachos',                              '{GF,V}'),
    (4, 'Pulled pork burrito bowl',            '{GF,NF,V}');

-- Schools → IDs 1..4 (each assigned a caterer)
INSERT INTO schools (name, region, caterer_id) VALUES
    ('Moreton Bay Boys'' College',      'Redlands',         1),
    ('John Paul College',               'South Brisbane',   2),
    ('Indooroopilly State High School', 'West Brisbane',    3),
    ('Loreto College',                  'Central Brisbane', 4);

-- Sessions → IDs 1..4 (one session per school)
INSERT INTO sessions (school_id, day_of_week, start_time, end_time, dinner_time, building, year_levels, manager_name, manager_mobile) VALUES
    (1, 'Tuesday', '16:00', '19:00', '17:30', 'Library',       '{12,11}',      'Triet',  '0469 420 067'),
    (2, 'Tuesday', '16:30', '19:30', '18:00', 'G Centre',      '{12,11,10,9}', 'Jessie', '0412 345 678'),
    (3, 'Monday',  '15:30', '18:30', '17:00', 'X Block',       '{12,11,10,9}', 'Lucian', '0412 233 445'),
    (4, 'Monday',  '15:30', '18:30', '17:00', 'Ella Building', '{12,11,10}',   'Claire', '0488 888 888');

-- Students → IDs 1..8 (mix of dietary requirements within the GF/DF/NF/V/H enum)
INSERT INTO students (name, year_level, dietary, student_email, parent_name, parent_email, parent_mobile) VALUES
    ('Henry Hill',      11, '{}',    'henryhill@mbbc.qld.edu.au',             'Ryan Hill',      'ryanhill@iinet.net.au',     '0478 813 748'),
    ('Noah Baker',      12, '{}',    'noahbaker@outlook.com',                 'Eliza Baker',    'elizabaker@iinet.net.au',   '0454 745 547'),
    ('Rashid Khalil',    9, '{H,V}', 'rashidkhalil@student.jpc.qld.edu.au',   'Fatima Khalil',  'fatimakhalil@iinet.net.au', '0487 414 081'),
    ('Benjamin Wilson', 12, '{}',    'benjaminwilson@student.jpc.qld.edu.au', 'Aria Wilson',    'ariawilson@live.com',       '0458 480 893'),
    ('Sara Abdallah',   10, '{H}',   'saraabdallah@gmail.com',                'Samir Abdallah', 'samirabdallah@live.com',    '0411 229 871'),
    ('Sophie Harris',   12, '{V}',   'sophieharris@eq.edu.au',                'Tristan Harris', 'tristanharris@hotmail.com', '0421 889 323'),
    ('Holly Hill',      10, '{}',    'hollyhill@gmail.com',                   'Benjamin Hill',  'benjaminhill@yahoo.com',    '0445 718 173'),
    ('Matilda Turner',  11, '{DF}',  'matildaturner@loreto.qld.edu.au',       'Phoebe Turner',  'phoebeturner@yahoo.com',    '0467 957 174');

-- Enrolments (student → session)
INSERT INTO enrolments (student_id, session_id) VALUES
    (1, 1),
    (2, 1),
    (3, 2),
    (4, 2),
    (5, 3),
    (6, 3),
    (7, 4),
    (8, 4);
