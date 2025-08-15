-- add humidity column to the ClimateData table
USE project_db;
ALTER TABLE ClimateData
    ADD COLUMN humidity FLOAT NOT NULL;
