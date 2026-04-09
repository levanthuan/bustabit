DROP TRIGGER IF EXISTS tg_calculate_case_10_update//

CREATE TRIGGER tg_calculate_case_10_update
BEFORE UPDATE ON `case_10`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;

    -- Tìm ID lớn nhất nhưng nhỏ hơn dòng đang sửa
    SELECT MAX(id) INTO last_id 
    FROM `case_10` 
    WHERE id < NEW.id;

    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;
        
        -- Kiểm tra ngưỡng 36
        IF NEW.count >= 36 THEN
            SET NEW.dead_flg = 1;
        ELSE
            SET NEW.dead_flg = NULL; -- Reset nếu không còn thỏa điều kiện
        END IF;
    ELSE
        -- Nếu dòng này là dòng có ID nhỏ nhất
        SET NEW.count = 1;
    END IF;
END;
//

DELIMITER ;