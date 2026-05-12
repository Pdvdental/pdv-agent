-- Migration: multi-doctor architecture

CREATE TABLE IF NOT EXISTS doctors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    calendar_id TEXT NOT NULL,
    hours_start TEXT NOT NULL DEFAULT '09:00',
    hours_end TEXT NOT NULL DEFAULT '20:00',
    working_days INTEGER[] NOT NULL,
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS doctor_services (
    doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    service_slug TEXT NOT NULL,
    PRIMARY KEY (doctor_id, service_slug)
);

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS doctor_id INTEGER REFERENCES doctors(id),
    ADD COLUMN IF NOT EXISTS calendar_id TEXT;

-- Seed doctors
INSERT INTO doctors (name, slug, calendar_id, hours_start, hours_end, working_days, slot_duration_minutes) VALUES
('Aina Olivart',           'aina',   '389g89qklvl6o86apaknhl7ijc@group.calendar.google.com',                                                           '15:00', '20:00', ARRAY[3],   30),
('Laurys Arab',            'laurys', '34mng6dhkcmfl6ggskthene0hk@group.calendar.google.com',                                                            '08:00', '17:30', ARRAY[2,4], 30),
('María Milagros Cardozo', 'mila',   '1157ae5d5382bdeb5691a475a7ec4b5c3b2a7ca9d61364fbc28b74cf9fb60811@group.calendar.google.com', '10:00', '21:00', ARRAY[2,3], 30)
ON CONFLICT (slug) DO NOTHING;

-- Seed services
INSERT INTO doctor_services (doctor_id, service_slug)
SELECT id, unnest(ARRAY['ortodoncia'])
FROM doctors WHERE slug = 'aina'
ON CONFLICT DO NOTHING;

INSERT INTO doctor_services (doctor_id, service_slug)
SELECT id, unnest(ARRAY['odontologia-general','limpieza','revision','caries','endodoncia'])
FROM doctors WHERE slug = 'laurys'
ON CONFLICT DO NOTHING;

INSERT INTO doctor_services (doctor_id, service_slug)
SELECT id, unnest(ARRAY['odontologia-general','limpieza','revision','caries'])
FROM doctors WHERE slug = 'mila'
ON CONFLICT DO NOTHING;
