# PD One Google Sheets/Docs/Excel employee assistance

Use this when launching or operating the lightweight employee-facing PD One capability where employees share Google files and DM PD One for help with analysis, cleanup, summaries, translation, classification, formulas, consistency checks, and reports.

## Operating model

- This is an employee-facing **PD One** capability, not a PD Neo/Hermes-branded capability. Hermes/PD Neo may administer or execute behind the scenes, but shared-channel announcements and user instructions should name PD One as the helper.
- In the current Pro-Design setup, official Google Sheets/Docs are owned by `admin@prodesign-group.com` and shared to external users via Google Groups; there is no Google Workspace domain-wide add-on install path for all employee accounts.
- For a direct Sheet/Doc URL workflow, the file must be accessible to the Google identity used by the tooling, currently usually `admin@prodesign-group.com` via `gog`/admin Google access.
- Employee-created files therefore need to be shared with `admin@prodesign-group.com` before PD One can inspect or edit them.
- Company-related Google Sheets and Docs should use the naming convention `良器-部門-表格中文名字 English Name` going forward, for example `良器-業務-銷售線索 Sales Leads`.
- Excel files should normally be converted/imported into Google Sheets first, then shared and sent to PD One by link.

## Employee workflow

1. Prepare the file:
   - Google Sheet/Doc: open the file and use **Share / 共用**.
   - Excel method A: Google Drive → **New / 新增** → **File upload / 檔案上傳** → right-click/open Excel with Google Sheets → **Save as Google Sheets** when needed.
   - Excel method B: from any Google Sheets file, use **File / 檔案** → **Import / 匯入** → **Upload / 上傳** Excel → choose **Create new spreadsheet**, **Insert new sheet(s)**, or **Replace spreadsheet** as appropriate.
2. Share the Google file with `admin@prodesign-group.com`.
3. Choose permission:
   - **Viewer / 檢視者** = PD One can read, analyze, summarize, and provide suggestions only.
   - **Editor / 編輯者** = PD One can write results back into the file.
4. DM **PD One** with the file link, requested help, and whether editing is allowed.

## Safety wording

- PD One will not overwrite existing data unless the user clearly approves it.
- Treat `share` / `共用` in document-help threads as Google Drive access/link access, not email delivery. Do not email documents just because the user asked to share them.
- Emailing a document or link is a separate external-send action: require explicit email wording plus approved recipients/content. Prefer fail-closed wrappers/guards for Gmail send paths so accidental model/tool interpretation cannot deliver mail.
- For Sheets, results should usually go to a new tab, new columns, or a clearly labeled section.
- Ask users to share only necessary sensitive data.
- Tell users they can remove `admin@prodesign-group.com` access after the task is complete.
- If Excel formatting changes after conversion/import, users can ask PD One to clean up or check the converted Sheet.

## Announcement guidance

When announcing this in Mattermost or another employee channel:

1. Post as or through PD One/OpenClaw, not as Hermes/PD Neo, unless Andy explicitly asks otherwise.
2. Use Traditional Chinese first, then English. Keep it channel-native and concise; avoid formal memo framing unless requested.
3. Do not mention AppSheet unless Andy explicitly says this announcement is about AppSheet.
4. Include:
   - Google Sheet/Doc sharing steps;
   - both Excel conversion/import methods;
   - share target `admin@prodesign-group.com`;
   - Viewer vs Editor permission meaning;
   - DM PD One with the file link, requested help, and edit permission;
   - safety note that PD One will not overwrite existing data without approval.
5. If the target is the Mattermost AI channel, use the verified channel route. Known AI channel id from admin notes: `imj7bt6w4tdk5rsbttiga44agc`. Avoid ambiguous Hermes `mattermost` home target.
6. For an infographic/poster, use the official PD One avatar from the canonical Google Drive Media Assets avatar folder rather than drawing a temporary bucket/mascot in HTML/CSS. Download the chosen avatar to a durable artifact path before rendering/scheduling, and visually QA that Chinese text, the avatar, and the footer are not clipped.
7. If scheduling the announcement with an image, follow `references/mattermost-channel-posting.md` for the PD One file-upload + post-with-`file_ids` sequence, durable attachment path, and duplicate-prevention state.

## Chinese-first announcement template

**PD One Google 試算表 / 文件 / Excel 協助 — 試用服務**

我們正在測試新的 PD One 功能，可以協助同仁處理 Google Sheets、Google Docs，以及轉成 Google Sheets 的 Excel 檔案。

可以請 PD One 協助：摘要表格/文件、找重複資料、整理日期/電話/姓名、翻譯欄位、分類客戶訊息、產生公式、找缺漏或不一致資料、準備週報/月報。

使用方式：
1. Google Sheet / Doc：打開檔案 → **Share / 共用** → 分享給 `admin@prodesign-group.com`。
2. Excel 方法 A：Google Drive → **New / 新增** → **File upload / 檔案上傳** → 用 Google Sheets 開啟 → 需要時另存成 Google Sheets。
3. Excel 方法 B：任一 Google Sheets → **File / 檔案** → **Import / 匯入** → **Upload / 上傳** Excel → 選擇建立新試算表、插入新工作表，或取代試算表。
4. 權限：**Viewer / 檢視者** = 只能分析/摘要/提供建議；**Editor / 編輯者** = 可以把結果寫回檔案。
5. 私訊 **PD One**：檔案連結 + 需要協助的內容 + 是否允許編輯。

安全原則：未經明確同意，PD One 不會覆蓋原本資料；結果通常會寫到新的分頁或新欄位。敏感資料請只分享必要內容。任務完成後，可以移除 `admin@prodesign-group.com` 的權限。如果 Excel 轉換後格式跑掉，也可以請 PD One 協助檢查或整理。

---

**PD One Google Sheets / Docs / Excel Help — Trial Service**

We are testing a new PD One capability for Google Sheets, Google Docs, and Excel files converted/imported into Google Sheets.

PD One can help summarize, clean duplicates, normalize dates/phones/names, translate columns, classify messages, generate formulas, find missing/inconsistent data, and prepare weekly/monthly reports.

How to use it:
1. Google Sheet/Doc: open the file → **Share** → share with `admin@prodesign-group.com`.
2. Excel method A: Google Drive → **New** → **File upload** → open with Google Sheets → save as Google Sheets if needed.
3. Excel method B: Google Sheets → **File** → **Import** → **Upload** Excel → create new spreadsheet, insert new sheet(s), or replace spreadsheet.
4. Permission: **Viewer** = analysis/suggestions only; **Editor** = PD One can write results back.
5. DM **PD One** with the file link, your request, and whether editing is allowed.

Safety: PD One will not overwrite existing data unless clearly approved. Results usually go to new tabs or new columns. Share only necessary sensitive data, and remove access after completion if desired. If Excel formatting changes after conversion, ask PD One to check or clean it up.

## Implementation notes

- For standing approval that lets a specific employee ask PD One to edit a specific Google Sheets dashboard without repeat admin approval, use `references/scoped-google-dashboard-editor-grants.md`; it covers the extra PD One policy/cache, approval-ledger, bound-resource, any-origin DM reuse, and negative smoke-test steps beyond normal Drive sharing.
- This can be operated immediately as a manual MVP through PD One DMs plus admin Google access.
- A Google Sheets sidebar/add-on is a later enhancement. Without Workspace domain management, employees would need individual install/authorization, or we would use bound scripts in official templates.
- If a file is not accessible, ask the user to verify sharing to `admin@prodesign-group.com` rather than requesting broad exports first.
