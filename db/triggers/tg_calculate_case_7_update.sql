DROP TRIGGER IF EXISTS tg_calculate_case_7_update//

CREATE TRIGGER tg_calculate_case_7_update
BEFORE UPDATE ON `case_7`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;

    -- Tìm ID lớn nhất nhưng phải nhỏ hơn ID hiện tại của dòng đang được sửa
    SELECT MAX(id) INTO last_id 
    FROM `case_7` 
    WHERE id < NEW.id;

    IF last_id IS NOT NULL THEN
        SET NEW.count = NEW.id - last_id;
        
        -- Cập nhật trạng thái dead_flg dựa trên ngưỡng 25
        IF NEW.count >= 25 THEN
            SET NEW.dead_flg = 1;
        ELSE
            SET NEW.dead_flg = NULL; -- Reset về 0 nếu count không còn đạt ngưỡng
        END IF;
    ELSE
        -- Nếu dòng này sau khi sửa trở thành dòng có ID nhỏ nhất bảng
        SET NEW.count = 1;
    END IF;
END;
//

DELIMITER ;