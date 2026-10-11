-- ============================================================
-- 「抽」的形式（设计文档 §1 / 核心循环：抽卡 → 去做 → 留着 → 毕业）
--
-- 这一版把「今天那张卡」从**直接摊开**改成**点一下才揭晓**，并允许按配额重抽。
-- 幂等前提没有变：daily_assignments 仍然一天一行（UNIQUE(user_id, assigned_date)），
-- 重抽只是把那一行的 card_id 换掉——没留住的旧卡直接丢，符合"不喜欢的就丢"。
-- ============================================================

ALTER TABLE daily_assignments
    -- NULL = 还是卡背（没揭晓）；非空 = 这张已经翻开给用户看过
    -- 存后端而不是 localStorage：刷新、换设备都保持"已翻开"，不会重复揭晓
    ADD COLUMN revealed_at DATETIME(6) NULL AFTER state,
    -- 今天抽了几次（含第一次）。配额判断以它为准，这样"上限 N 次"也能直接用。
    -- 0 = 还没抽过（懒生成前的初始态）
    ADD COLUMN draw_count INT NOT NULL DEFAULT 0 AFTER revealed_at;
