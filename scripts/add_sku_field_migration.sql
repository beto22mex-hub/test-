-- Migration to add SKU field to serials_authorizedpart table
-- This script adds the SKU field that will be used in CSV exports

ALTER TABLE serials_authorizedpart 
ADD COLUMN sku VARCHAR(50) NOT NULL DEFAULT '';

-- Update existing records with default SKU values based on part_number
UPDATE serials_authorizedpart 
SET sku = CASE 
    WHEN part_number LIKE 'PCB%' THEN CONCAT('SKU-', part_number, '-PCB')
    WHEN part_number LIKE 'CAP%' THEN CONCAT('SKU-', part_number, '-CAP')
    WHEN part_number LIKE 'RES%' THEN CONCAT('SKU-', part_number, '-RES')
    ELSE CONCAT('SKU-', part_number)
END
WHERE sku = '';

-- Remove the default constraint after updating existing records
ALTER TABLE serials_authorizedpart 
ALTER COLUMN sku DROP DEFAULT;
