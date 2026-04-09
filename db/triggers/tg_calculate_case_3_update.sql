DROP TRIGGER IF EXISTS tg_calculate_case_3_update//

CREATE TRIGGER tg_calculate_case_3_update
BEFORE UPDATE ON `case_3`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;

    -- Tìm ID lớn nhất mà nhỏ hơn ID đang update
    SELECT MAX(id) INTO last_id 
    FROM `case_3` 
    WHERE id < NEW.id;

    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;
        
        -- Cập nhật dead_flg dựa trên count mới
        IF NEW.count >= 8 THEN
            SET NEW.dead_flg = 1;
        ELSE
            SET NEW.dead_flg = NULL; -- Reset nếu count nhỏ hơn 8
        END IF;
    ELSE
        SET NEW.count = 1;
    END IF;
END;
//

DELIMITER ;