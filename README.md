# 北基宜花金馬分署 班級報名總覽

顯示職業訓練整合網（course.taiwanjobs.gov.tw）查到的北基宜花金馬分署班級，含報名人數、名額、報名期間與甄試日。

## 檔案說明

- `index.html`：網頁本體，讀取 `data/classes.json` 顯示。
- `data/classes.json`：班級資料，由排程自動更新。
- `scripts/update.py`：抓取腳本，使用與整合網相同的查詢 API，再讀取各班明細頁的報名人數。
- `.github/workflows/update.yml`：排程設定，每天台灣時間 12:00 與 00:00 執行。

## 查詢範圍

與整合網預設查詢相同：訓練單位為北基宜花金馬分署，開課期間為「當月起四個月內」。例如 2026/10 執行時，範圍是 2026/10 至 2027/02。

## 在 GitHub 上設定

1. 建立新的 repository，把這個資料夾的檔案全部推上去。
2. 到 Settings → Pages，Source 選 `Deploy from a branch`，Branch 選 `main`，資料夾選 `/ (root)`。
3. 到 Actions 頁面，確認已啟用 workflow。也可以按 `Run workflow` 手動執行一次。

公開網址為 `https://<帳號>.github.io/<repo名稱>/`。

## 注意事項

- 網站改版或來源網站暫時無法連線時，腳本會保留上一次的資料，不會寫入空白結果。
- GitHub 排程可能延遲數分鐘。
- 報名人數與名額以原網站公告為準。
