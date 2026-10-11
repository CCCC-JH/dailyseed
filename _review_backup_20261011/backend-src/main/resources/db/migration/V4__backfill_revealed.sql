-- ============================================================
-- 回填：已留住的卡一律视为「已揭晓」
--
-- 为什么必需：V3 只加了 revealed_at 列，**没有回填**。而 V3 之前的旧代码是
-- 直接把卡面摊开的，根本不存在"卡背"这个状态 —— 所以那些行现在成了
-- `state='KEPT'` + `revealed_at IS NULL`，前端会画出一个**没有任何按钮的空白卡背**
-- （`!revealed` 画卡背、`revealed` 才画动作区），用户既翻不开也留不了，是死状态。
--
-- 语义上也应当如此：一张卡被留住了，说明用户看过它。
-- 时间取 kept_at（真留住的那一刻），没有就退回当前时间。
-- ============================================================

UPDATE daily_assignments
SET revealed_at = IFNULL(kept_at, CURRENT_TIMESTAMP(6))
WHERE state = 'KEPT'
  AND revealed_at IS NULL;
