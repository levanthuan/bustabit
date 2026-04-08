DELIMITER //
CREATE TRIGGER tg_calculate_count_case_10
BEFORE INSERT ON `case_10`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;
    SELECT MAX(id) INTO last_id FROM `case_10`;
    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;

        IF NEW.count >= 36 THEN
            SET NEW.dead_flg = 1;
        END IF;
    ELSE
        SET NEW.count = 1;
    END IF;
END;
//
DELIMITER ;