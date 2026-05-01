-- Multi-Agent Customer Support — Database Schema

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    phone       TEXT,
    tier        TEXT NOT NULL CHECK(tier IN ('bronze', 'silver', 'gold', 'platinum')),
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL CHECK(category IN ('electronics', 'clothing', 'home', 'books', 'sports', 'beauty', 'toys', 'food')),
    price       REAL NOT NULL CHECK(price > 0),
    stock       INTEGER NOT NULL CHECK(stock >= 0),
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    product_id    INTEGER NOT NULL REFERENCES products(id),
    quantity      INTEGER NOT NULL CHECK(quantity > 0),
    total         REAL NOT NULL CHECK(total >= 0),
    status        TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'returned')),
    order_date    TEXT NOT NULL,
    delivery_date TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_id    INTEGER REFERENCES orders(id),
    category    TEXT NOT NULL CHECK(category IN ('complaint', 'technical', 'billing', 'general')),
    priority    TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high')),
    status      TEXT NOT NULL CHECK(status IN ('open', 'in_progress', 'resolved', 'closed')),
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    amount     REAL NOT NULL CHECK(amount > 0),
    reason     TEXT NOT NULL CHECK(reason IN ('damaged', 'wrong_item', 'not_delivered', 'quality_issue', 'changed_mind')),
    status     TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'processed')),
    created_at TEXT NOT NULL
);
