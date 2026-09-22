-- 005_restrict_content_update.sql — 收斂 content_update() 的 EXECUTE 授權
--
-- 背景：新建函式預設 PUBLIC 可 EXECUTE；本函式為 SECURITY INVOKER，
-- 內部寫入以呼叫者權限執行，故 phq_web_ro 呼叫只會權限不足失敗，
-- 不構成公開寫入漏洞。但公開／網站唯讀角色不需要此寫入入口。
-- 本檔只收函式執行權，不動任何資料表授權，不做全域 REVOKE。
--
-- 正式套用前需確認 Chat connector 實際身分（請規劃端提供 Chat 側
-- `SELECT current_user` 結果）：若為 neondb_owner，直接套用本檔；
-- 若為其他具寫入權角色，套用本檔後再對該角色補精確 signature 的 GRANT；
-- 若身分不明，不套用，先補資訊。
--
-- 回復：重新 GRANT 即可（見下註解行）；不刪函式、不動資料。

REVOKE ALL ON FUNCTION public.content_update(text,text,text,text,integer,text,text,text) FROM PUBLIC;

-- 維護者身分確認後，若非 owner，取消下行註解並填入實際角色名：
-- GRANT EXECUTE ON FUNCTION public.content_update(text,text,text,text,integer,text,text,text) TO <maintainer_role>;
