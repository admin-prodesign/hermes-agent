# Employee onboarding thread start

Open the onboarding thread from safe HRS columns only. The probe omits
private columns and returns a withheld_fields count. Do not reconstruct
withheld columns from memory or an earlier tool result.

Use `read_file` on this reference and copy the template. Post both
languages with the same facts. Stop after the template.

## When this applies

- A new employee record was confirmed from HRS_Data or HRS_Data_MasterNames.
- The destination is not an HR-only room, so private columns stay withheld.
- Fill only the placeholders below. Add no other column.

## Output template

Copy this template. Fill placeholders from the probe. Leave a placeholder
blank rather than adding any other field.

English:
Welcome {name_en} ({name}) to {department}.
Title: {title}
Start date: {start_date}
Manager: {manager}
Seat / extension: {seat} / {extension}

繁體中文:
歡迎 {name}（{name_en}）加入 {department}。
職稱：{title}
到職日：{start_date}
主管：{manager}
座位／分機：{seat}／{extension}
