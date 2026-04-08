DELIMITER //

DROP TRIGGER IF EXISTS tg_calculate_count_case_3//

CREATE TRIGGER tg_calculate_count_case_3
BEFORE INSERT ON `case_3`
FOR EACH ROW
BEGIN
    DECLARE last_id INT;

    -- 1. Lấy ID lớn nhất hiện tại trong bảng
    SELECT MAX(id) INTO last_id FROM `case_3`;

    -- 2. Kiểm tra nếu bảng đã có dữ liệu
    IF last_id IS NOT NULL THEN
        -- Tính toán giá trị count
        SET NEW.count = NEW.id - last_id;
        
        -- Logic mới: Nếu count >= 8 thì set dead_flg = 1
        IF NEW.count >= 8 THEN
            SET NEW.dead_flg = 1;
        END IF;
        
    ELSE
        -- 3. Xử lý dòng đầu tiên
        SET NEW.count = 1;      -- Theo ý bạn muốn dòng đầu là 1
    END IF;
END;
//

DELIMITER ;