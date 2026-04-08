DELIMITER //
CREATE TRIGGER tg_calculate_count_case_7
BEFORE INSERT ON `case_7`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;
    SELECT MAX(id) INTO last_id FROM `case_7`;
    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;

        IF NEW.count >= 25 THEN
            SET NEW.dead_flg = 1;
        END IF;
    ELSE
        SET NEW.count = 1;
    END IF;
END;
//
DELIMITER ;