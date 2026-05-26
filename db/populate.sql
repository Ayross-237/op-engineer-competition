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
    (1, 'Shrimp Fried Rice',                                '{GF,DF}'),
    (1, 'Spaghetti Bolognese + Garlic Bread',               '{NF}'),
    (1, 'Sweet and Sour Chicken',                           '{GF,DF,NF}'),
    (1, 'Japanese Chicken Curry',                           '{DF,NF}'),
    (1, 'Japanese Chicken Curry (Vegetarian)',              '{DF,NF,V}'),
    (2, 'Spicy Miso Udon',                                  '{DF}'),
    (2, 'Mie Goreng',                                       '{GF,DF,NF}'),
    (2, 'Mie Goreng (Vegetarian)',                          '{GF,DF,NF,V}'),
    (2, 'Beef Pad Thai',                                    '{}'),
    (2, 'Lemongrass Grilled Beef and Noodles',              '{GF,DF,NF}'),
    (2, 'Lemongrass Grilled Beef and Noodles (Vegetarian)', '{GF,DF,NF,V}'),
    (3, 'Teriyaki Salmon rice bowl',                        '{GF,DF,NF}'),
    (3, 'Teriyaki Salmon rice bowl (Vegetarian)',           '{GF,DF,NF,V}'),
    (3, 'Chicken Karaage ricebowl',                         '{DF,NF}'),
    (3, 'Chicken Karaage ricebowl (Vegetarian)',            '{DF,NF,V}'),
    (3, 'Sweet and Sour Chicken',                           '{GF,DF}'),
    (4, 'Caesar Salad',                                     '{GF,DF,NF}'),
    (4, 'Caesar Salad (Vegetarian)',                        '{GF,DF,NF,V}'),
    (4, 'Chicken Enchilada',                                '{GF,DF}'),
    (4, 'Nachos',                                           '{GF}'),
    (4, 'Nachos (Vegetarian)',                              '{GF,V}'),
    (4, 'Pulled pork burrito bowl',                         '{GF,NF}'),
    (4, 'Pulled pork burrito bowl (Vegetarian)',            '{GF,NF,V}');

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
-- Holly Hill is opted out of catering (wants_catering = FALSE) to exercise that path.
INSERT INTO students (name, year_level, dietary, wants_catering, student_email, parent_name, parent_email, parent_mobile) VALUES
    ('Henry Hill',      11, '{}',    TRUE,  'henryhill@mbbc.qld.edu.au',             'Ryan Hill',      'ryanhill@iinet.net.au',     '0478 813 748'),
    ('Noah Baker',      12, '{}',    TRUE,  'noahbaker@outlook.com',                 'Eliza Baker',    'elizabaker@iinet.net.au',   '0454 745 547'),
    ('Rashid Khalil',    9, '{H,V}', TRUE,  'rashidkhalil@student.jpc.qld.edu.au',   'Fatima Khalil',  'fatimakhalil@iinet.net.au', '0487 414 081'),
    ('Benjamin Wilson', 12, '{}',    TRUE,  'benjaminwilson@student.jpc.qld.edu.au', 'Aria Wilson',    'ariawilson@live.com',       '0458 480 893'),
    ('Sara Abdallah',   10, '{H}',   TRUE,  'saraabdallah@gmail.com',                'Samir Abdallah', 'samirabdallah@live.com',    '0411 229 871'),
    ('Sophie Harris',   12, '{V}',   TRUE,  'sophieharris@eq.edu.au',                'Tristan Harris', 'tristanharris@hotmail.com', '0421 889 323'),
    ('Holly Hill',      10, '{}',    FALSE, 'hollyhill@gmail.com',                   'Benjamin Hill',  'benjaminhill@yahoo.com',    '0445 718 173'),
    ('Matilda Turner',  11, '{DF}',  TRUE,  'matildaturner@loreto.qld.edu.au',       'Phoebe Turner',  'phoebeturner@yahoo.com',    '0467 957 174');

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
