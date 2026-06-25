-- USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
);

-- HISTORY TABLE
CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    user_id INT,
    amount FLOAT,
    hour INT,
    fraud INT,
    risk TEXT,
    device_id TEXT,
    location TEXT,
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- BLACKLIST TABLE
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INT PRIMARY KEY,
    reason TEXT
);

-- DEFAULT USERS
INSERT INTO users (username,password,role)
VALUES
(
'admin',
'240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
'admin'
),
(
'analyst',
'240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
'analyst'
)
ON CONFLICT (username) DO NOTHING;