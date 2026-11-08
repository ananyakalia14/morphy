CREATE DATABASE morphy_fixture CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE morphy_fixture;
CREATE TABLE orders (id INT PRIMARY KEY, amount DECIMAL(9,2), region VARCHAR(40), private_note TEXT) ENGINE=InnoDB;
INSERT INTO orders VALUES (1,20,'APAC','private'), (2,999,'apac','private'), (3,900,'ÁPAC','private');
CREATE VIEW private_view AS SELECT private_note FROM orders;
CREATE USER 'morphy_reader'@'%' IDENTIFIED BY 'fixture-read-only';
GRANT SELECT ON morphy_fixture.* TO 'morphy_reader'@'%';
