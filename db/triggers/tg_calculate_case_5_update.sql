DROP TRIGGER IF EXISTS tg_calculate_case_5_update//

CREATE TRIGGER tg_calculate_case_5_update
BEFORE UPDATE ON `case_5`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;

    -- Tìm ID lớn nhất nhưng phải nhỏ hơn ID hiện tại của dòng đang sửa
    SELECT MAX(id) INTO last_id 
    FROM `case_5` 
    WHERE id < NEW.id;

    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;
        
        -- Kiểm tra ngưỡng 16 và cập nhật dead_flg
        IF NEW.count >= 16 THEN
            SET NEW.dead_flg = 1;
        ELSE
            SET NEW.dead_flg = NULL; -- Reset nếu sau khi sửa count lại nhỏ hơn 16
        END IF;
    ELSE
        -- Nếu dòng bị sửa lại là dòng có ID nhỏ nhất bảng
        SET NEW.count = 1;
    END IF;
END;
//

DELIMITER ;