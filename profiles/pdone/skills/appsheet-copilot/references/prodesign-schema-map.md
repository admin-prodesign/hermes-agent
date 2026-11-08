# Pro-Design prototype schema map

- Source: `/home/prodesign/.openclaw/workspace/data/appsheet-definitions/f2073120-8c2e-4930-b13c-105838c5e4c3/latest/latest.json`
- Tables parsed: 35
- Columns parsed: 809
- Relationship hints: 128
- Slices parsed: 134

Use this as a relationship hint map, not gospel. It is built from the exported prototype app definition markdown, so some targets are inferred from Ref types, dereferences, Suggested_Values, LOOKUP(), SELECT(), and slice source/filter evidence.

## Slice collapse map

Use this section to collapse slice names back to their base tables before planning joins or export paths.

### Current User

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=[Appsheet Email] = USEREMAIL()` - **Columns**: `_RowNumber, Row ID, PersonID, Employment Status, Employee ID, Employee Photo, Name_ZH, Name_EN, Name_ZH_EN, Name_PINYIN, Name_Nickname, BU, Cell Phone, Company Email, A...`

### HR_Employees_Dropdown_IT_Technicians

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND( [Employment Status] = "Employed", ISNOTBLANK(INTERSECT([Appsheet Roles], {"IT_Technician", "IT_Manager", "IT_Admin"})) )` - **Columns**: `_RowNumber, PersonID, Name_ZH_EN, Employee ID, HR_Notes_Attachments_Cache...`

### ERP_Assets_Molds_Dropdown

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( STARTSWITH([品 號],"APD-"), STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, Friendly Name, Type, Equipment Type`

### ERP_Assets_Equipment_InjectionMachines_Dropdown

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( OR( STARTSWITH( [品 號], "AJW-" ), STARTSWITH( [品 號], "ASM-" ) ), STARTSWITH( [品質狀態], "S" ) )` - **Columns**: `_RowNumber, 品 號, Friendly Name, Type, Equipment Type`

### Lookup_Dropdown_Language

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Language",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Lookup_Dropdown_Status

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Category, Sub-Category, Sort Order, Updater, en, zh-tw, Status (Sorted), Reviewer, Editable Roles`

### ERP_Assets_Equipment_Forklifts_Dropdown

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( STARTSWITH([品 號],"APL-"), STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Last Reported Location, Latest_MoldMovement, 模具穴數, Related_ERP_Asset_Det...`

### HR_Employees_Logistics_ForkliftMaintenance

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND( [Employment Status]=TRUE, OR(ISBLANK([Hidden]),[Hidden]=FALSE), IN([Appsheet Roles], {"Logistics_ForkliftMaintenance_User","Logistics_ForkliftMaintenance_Manager","Logistics_ForkliftMaintenance_Admin"}))` - **Co...`

### Lookup_Dropdown_Type_Case

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Case",[Sub-Category]), ISBLANK([Sub-Category 2]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Standard_Lead_Time_Days, en, zh-tw, Reviewer`

### Lookup_Dropdown_Views_Menu

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Views",[Category]), ISNOTBLANK([Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Category, Sub-Category, Sub-Category 2, Sub-Category 3, Reviewer`

### Lookup_Dropdown_Type_ActivityLog

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("ActivityLog",[Sub-Category]), ISNOTBLANK([Sub-Category 2]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### Case_IT_MyCases

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( [Type] = "IT Ticket", ISBLANK([Parent Case ID]), OR( [Created By] = ANY(Current User[PersonID]), [Next Step Responsible Person] = ANY(Current User[PersonID]) ) )` - **Columns**: `_RowNumber, CaseID, Row ID, Type...`

### Lookup_Type_EmployeeNotes

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Type",[Category]), IN("Employee Notes",[Sub-Category]) )` - **Columns**: `_RowNumber, Row ID, Sort Order, zh-tw, en, Category, Translation, Sub-Category, Sub-Category 2, Sub-Category 3, Descri...`

### Lookup_Views_Home

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`, `Settings`
- Row filter: `=AND( [Active] = TRUE, IN("Views", [Category]), OR( IN([LookupID], ANY(Current User[Appsheet Views Access])), COUNT( INTERSECT( [Viewable Roles], SPLIT( SUBSTITUTE( SUBSTITUTE( CONCATENATE( TEXT(ANY(Current User[Combi...`

### Lookup_Dropdown_Type_CaseUpdate

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Update",[Sub-Category]), IN("Case",[Sub-Category 2]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Case_IT_Unassigned

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND([Type]="IT Ticket", ISBLANK([Next Step Responsible Person]) )` - **Columns**: `_RowNumber, Row ID, Type, Title, Title_en, Title_zh-tw, Description, Description_en, Description_zh-tw, Status, Created By, CaseID, S...`

### ActivityLog_MyRelatedActivity

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`, `HR_Employees`
- Row filter: `=OR( [Created By] = ANY(Current User[PersonID]), IN( [Created By], SELECT( HR_Employees[PersonID], [Manager 1] = ANY(Current User[PersonID]) ) ), IN(ANY(Current User[PersonID]),SPLIT([Employee],", ")), IN(ANY(Current ...`

### ActivityLog_Incident_All

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( [Category] = "Incident Report", ISBLANK([Parent ActivityLogID]) )` - **Columns**: `_RowNumber, Row ID, ActivityLogID, Timestamp, Category, Sub-Category, Equipment, Molds, Products, Employee, Description, Trouble...`

### Lookup_PersonStatus

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]), IN("Employment Status",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Row ID, Sort Order, zh-tw, en, Description_zh-tw, Description_en, Category, Sub-Category,...`

### Lookup_Dropdown_Appsheet_Role

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Appsheet Role",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Lookup_Frequency

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Frequency",[Category]) )` - **Columns**: `_RowNumber, Row ID, zh-tw, en, Category, Translation, Sub-Category, Sub-Category 2, IntervalDays, LookupID, Viewable Roles, Description_zh-tw, Descrip...`

### Lookup_Dropdown_Type_Maintenance

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Maintenance",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer, Initial Value, Initial Value 2`

### Maintenance_Sessions_CurrentUser

- Source table: `Maintenance_Sessions`
- Tables seen in slice filter: `HR_Employees`, `Maintenance_Sessions`
- Row filter: `=OR( [Performed By] = ANY(Current User[PersonID]), IN( [Performed By], SELECT(HR_Employees[PersonID], [Manager 1] = ANY(Current User[PersonID])) ) )` - **Columns**: `_RowNumber, MaintenanceSessionID, Maintenance Type,...`

### Lookup_Dropdown_Status_Maintenance

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]), IN("Maintenance",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### Maintenance_Items_Active

- Source table: `Maintenance_Items`
- Tables seen in slice filter: `Maintenance_Items`
- Row filter: `=[Active]=TRUE` - **Columns**: `_RowNumber, MaintenanceItemID, Row ID, Description_zh-tw, Description_en, Frequency, Active, Description, Maintenance Type, Sort Order, Location_zh-tw, Location_en, Location, Explanator...`

### Lookup_Certifications

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Employee Notes",[Sub-Category]), IN("Documents",[Sub-Category 2]), IN("Document_Certification",[Sub-Category 3]) )` - **Columns**: `_RowNumber, Active, LookupID, en, z...`

### Lookup_MyLookups

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=COUNT(INTERSECT(SPLIT([Editable Roles], ","), SPLIT(Current User[Appsheet Roles], ","))) > 0` - **Columns**: `_RowNumber, Row ID, LookupID, zh-tw, en, Category, Sub-Category, Sub-Category 2, Sort Order, Description_z...`

### HR_E_NA_WorkContracts

- Source table: `HR_Employees_NotesAttachments`
- Tables seen in slice filter: `HR_Employees_NotesAttachments`
- Row filter: `=[Category]="Work Contract"` - **Columns**: `_RowNumber, Row ID, Timestamp, EmployeeAttachmentID, PersonID, CreatedBy, Category, Description, Files, Images, Contract Start Date, Contract End Date, Label, Year_Month, T...`

### ERP_Assets_Equipment_Dropdown

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( [Type] = "Equipment", STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, Friendly Name, Type, Equipment Type`

### ERP_Assets_Products_Dropdown

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( [Type]="Product", STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, Friendly Name, Type, Equipment Type`

### Lookup_Dropdown_Type_ActivityLog_Category

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("ActivityLog",[Sub-Category]), ISBLANK([Sub-Category 2]), ISBLANK([Sub-Category 3]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Requires_Sub-Categ...`

### Lookup_Dropdown_Risk

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Risk",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### ActivityLog_InjectionMachineParameters

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Sub-Category] = "Injection Machine Parameters"` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, ActivityLogID, Equipment, Molds, Products, Description, Notification Group, Sub-Category, Created By, Related ...`

### HR_Employees_CurrentlyEmployed_BasicInfo

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND([Hidden] <> TRUE, [Employment Status] = "Employed")` - **Columns**: `_RowNumber, PersonID, Employee ID, Name_ZH_EN, Name_ZH, Name_PINYIN, Appsheet Email, Name_Nickname, Employee Photo, BU, Job Title, Certificatio...`

### HR_Employees_MyTeamMembers

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND( [Employment Status] = "Employed", OR(ISBLANK([Hidden]), [Hidden] = FALSE), OR( [Manager 1] = ANY(Current User[PersonID]), [Manager 2] = ANY(Current User[PersonID]), [Manager 3] = ANY(Current User[PersonID]) ) )`...`

### Case_Updates_MyTeam

- Source table: `Case_Updates`
- Tables seen in slice filter: `Case_Updates`, `HR_Employees`
- Row filter: `=OR( [Created By] = ANY(Current User[PersonID]), [New Next Step Responsible Person] = ANY(Current User[PersonID]), IN( [Created By], SELECT( HR_Employees[PersonID], [Manager 1] = ANY(Current User[PersonID]) ) ), IN( [...`

### Lookup_Dropdown_NotificationGroups

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Notification Group",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### HR_Employees_NotificationGroups

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND( [Employment Status] = "Employed", [Hidden]<>FALSE )` - **Columns**: `_RowNumber, PersonID, Name_ZH_EN, Appsheet Notification Group, Row ID, Employee ID, BU, Job Title, Employment Status, Manager 1, Job Level, Hi...`

### ActivityLog_Factory

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( ISBLANK([Parent ActivityLogID]), [Category]<>"5S Action", [Category]<>"Machine Parameters" )` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, Troubleshooting Actions, ActivityLogID, Equipment, Molds, Pr...`

### ActivityLog_5S

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( [Category] = "5S Action", ISBLANK([Parent ActivityLogID]), [Created By].[Employment Status] = "Employed" )` - **Columns**: `_RowNumber, Row ID, ActivityLogID, Timestamp, Category, Sub-Category, Equipment, Descri...`

### Lookup_Dropdown_Status_IncidentReport

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Status",[Category]), IN("Incident Report",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### Lookup_Dropdown_HR_TransportMethod

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Transport Method",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Case_My_NextStepPerson

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( IN([Next Step Responsible Person],Current User[PersonID]), [Status] <> "Completed", [Status] <> "Canceled" )` - **Columns**: `_RowNumber, Row ID, Parent ActivityLogID, Parent Case ID, CaseID, Created On, Title, ...`

### Lookup_Dropdown_Dashboards

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND([Active] = TRUE, IN("Dashboard", [Category]))` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Case_My_NeedsReview

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( IN([Next Step Responsible Person], Current User[PersonID]), IN([Status], { "Needs Review", "Status_WaitingForResponse"}) )` - **Columns**: `_RowNumber, Days Overdue, Parent Case ID, Sub-Cases, Related Case_Attac...`

### ActivityLog_Items_Active

- Source table: `ActivityLog_Items`
- Tables seen in slice filter: `ActivityLog_Items`
- Row filter: `=[Active] = TRUE` - **Columns**: `_RowNumber, Row ID, Active, Sort Order, ActivityLogItemID, Description_zh-tw, Detailed_Description_zh-tw, Description_en, Detailed_Description_en, Activity Log Type, Instruction Photo...`

### Lookup_Dropdown_Type_AttachmentCategory

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Attachment",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Sub-Category, Sub-Category 2, Reviewer`

### Case_Parent

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=ISBLANK([Parent Case ID])` - **Columns**: `_RowNumber, CaseID, Label, Parent ActivityLogID, Related Inventory_Mgmts, Latest_CaseUpdateID, Status (Sorted), Deadline, Type, Sub-Type, Parent Case ID, Created On, Last Up...`

### SuddenAbsenceRequests_Last24Hours

- Source table: `SuddenAbsenceRequests`
- Tables seen in slice filter: `SuddenAbsenceRequests`
- Row filter: `=[時間戳記] >= TODAY() - 1` - **Columns**: `_RowNumber, 時間戳記, 名字 Name ชื่อ, 部門 Department แผนก, 原因 Reason for requesting sudden leave เหตุผลขอลางานกะทันหัน, 請假日期 Date of requested leave วันที่ขอลางาน, 中文 Chinese, 英文 Engli...`

### ActivityLog_FAI

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Category]="First Article Inspection"` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, Troubleshooting Actions, ActivityLogID, Equipment, Molds, Products, Description, Notification Group, Employee, Sub-Categ...`

### ActivityLog_5S_MyTeam

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`, `HR_Employees`
- Row filter: `=AND([Category] = "5S Action", OR( [Created By] = ANY(Current User[PersonID]), IN( [Created By], SELECT( HR_Employees[PersonID], OR( [Manager 1] = ANY(Current User[PersonID]), [Manager 2] = ANY(Current User[PersonID])...`

### Lookup_Dropdown_ProductionShift

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Type",[Category]), IN("Type_Shift",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### Lookup_DateRanges_CurrentUser

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active]=TRUE, IN("Type",[Category]), IN("Data_Date_Range",[Sub-Category]), ISNOTBLANK( INTERSECT( SPLIT(Current User[Appsheet Roles],","), [Viewable Roles] ) ) )` - **Columns**: `_RowNumber, Row ID, LookupID, A...`

### ActivityLog_NG_Product_Weight

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Category]="NG_Product_Weight"` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, Description, ActivityLogID, Equipment, Molds, Products, Notification Group, Created By, Related ActivityLog_Attachments, Timest...`

### ActivityLog_Session_Items_NG_Product_Weight

- Source table: `ActivityLog_Session_Items`
- Tables seen in slice filter: `ActivityLog_Session_Items`
- Row filter: `=[ActivityLogItemID].[Activity Log Type]="NG_Product_Weight"` - **Columns**: `_RowNumber, Row ID, Timestamp, Performed By, ActivityLogID, ActivityLogItemID, Molds, Equipment, Products, Employees, Sort Order, Thumbnail...`

### ActivityLog_Attachments_5SPhotoAudit

- Source table: `ActivityLog_Attachments`
- Tables seen in slice filter: `ActivityLog_Attachments`
- Row filter: `=[ActivityLog Type] = "5S Action"` - **Columns**: `_RowNumber, Row ID, Timestamp, ActivityLogAttachmentID, ActivityLogID, ActivityLog Type, CreatedBy, Images, Description, Attachment Category, Sort Order, Label, Descr...`

### ActivityLog_EntryExitRecord

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( [Category]="Entry_Exit_Record", ISBLANK([Parent ActivityLogID]) )` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, ActivityLogID, Equipment, Molds, Products, Destination, Description, Notification Group...`

### Lookup_Dropdown_Status_EntryExitRecord

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]), IN("Entry_Exit_Record",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Reviewer`

### RefDocs_SIP_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active]=TRUE, [Doc Type]="RefDoc_SIP" )` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effective Date, Next R...`

### RefDocs_WorkManual_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active]=TRUE, [Doc Type]="RefDoc_WorkManual" )` - **Columns**: `_RowNumber, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, URL, Revision, Effective Date, Next Review Date, Molds, Equipment, Products,...`

### RefDocs_All_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=[Active] = TRUE` - **Columns**: `_RowNumber, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, URL, Revision, Effective Date, Next Review Date, Molds, Equipment, Products, Tags, Created By, File, Image, Title...`

### Lookup_Dropdown_Type_ReferenceDocuments

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Reference_Document",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, en, zh-tw, Reviewer, Viewable Roles, Editable Roles`

### Case_FacilitiesRepair_MyCases

- Source table: `Case`
- Tables seen in slice filter: `Case`, `Case_Updates`, `HR_Employees`
- Row filter: `=AND( [Type] = "Facilities Repair", ISBLANK([Parent Case ID]), OR( [Created By] = ANY(Current User[PersonID]), [Next Step Responsible Person] = ANY(Current User[PersonID]), IN( [Created By], SELECT( HR_Employees[Perso...`

### HR_Employees_NameWorkerNumber_ExportCSV

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=[Hidden]<>TRUE` - **Columns**: `_RowNumber, PersonID, Name_ZH_EN, Employee ID, Name_PINYIN, Updater, Related HR_Employees_NotesAttachments By PersonID, Name_Nickname, HR_Notes_Attachments_Cached, Current Operator Cod...`

### Case_TechDev_All

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=[Type] = "Tech Dev Case"` - **Columns**: `_RowNumber, Row ID, Created On, CaseID, Title, Description, Deadline, Completion Date, Equipment, Molds, Products, Type, Sub-Type, Status, Created By, Next Step Responsible P...`

### Case_IT_All

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( [Type] = "IT Ticket", ISBLANK([Parent Case ID]) )` - **Columns**: `_RowNumber, Row ID, Type, Title, Title_en, Title_zh-tw, Description, Description_en, Description_zh-tw, Status, Created By, CaseID, Sub-Type, Eq...`

### Case_My

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=OR( [Created By] = ANY( Current User[PersonID] ), [Next Step Responsible Person] = ANY( Current User[PersonID] ) )` - **Columns**: `_RowNumber, CaseID, Row ID, Type, Sub-Type, Title, Description, Status, Created By, ...`

### Case_Quality_All

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( [Type] = "Case_Quality", ISBLANK([Parent Case ID]) )` - **Columns**: `_RowNumber, Row ID, Type, Title, Description, Status, Created By, CaseID, Sub-Type, Equipment, Molds, Products, Related Case_Attachments, Nex...`

### Lookup_Dropdown_Type_InventoryMgmt

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("Type_SampleTracking",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, en, zh-tw, Reviewer`

### ActivityLog_Incident_FacilitiesRelated

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( [Category] = "Incident Report", OR( [Sub-Category] = "Incident_ProductionProblem_Equipment", [Sub-Category] = "Incident_ProductionProblem_Other", [Sub-Category] = "Incident_SafetyRisk", [Sub-Category] = "Inciden...`

### Lookup_Dropdown_Status_Inspection

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]), IN("Inspection",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### Case_RowCount_IT_MyCases_NotCompleted

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( [Type] = "IT Ticket", NOT( OR( [Status] = "Completed", [Status] = "Canceled" ) ), OR( [Created By] = ANY( Current User[PersonID] ), [Next Step Responsible Person] = ANY( Current User[PersonID] ) ) )` - **Columns...`

### Case_FacilitiesRepair_All

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( [Type]="Facilities Repair", ISBLANK([Parent Case ID]) )` - **Columns**: `_RowNumber, Row ID, Parent Case ID, CaseID, Created On, Title, Description, Type, Sub-Type, Created By, Equipment, Molds, Products, Status...`

### RefDocs_SOP_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active]=TRUE, [Doc Type]="RefDoc_SOP" )` - **Columns**: `_RowNumber, Label, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effective Date, Next Revi...`

### ERP_Assets_Molds_All

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=STARTSWITH([品 號],"APD-")` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Friendly Name, 品號分類, 模具編號, 主模-模號, 替代模2, Equipment Type, 品質狀態, Last Reported Location, Latest_MoldMoveme...`

### ERP_Assets_Products_All

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=[Type]="Product"` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Friendly Name, 品號分類, 模具編號, 主模-模號, 替代模2, Equipment Type, 品質狀態, Last Reported Location, Latest_MoldMovement, 模具穴數...`

### ActivityLog_MyTeam

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( NOT( [Category] = "5S Action" ), OR( [Created By] = ANY( Current User[PersonID] ), [Created By].[Manager 1] = ANY( Current User[PersonID] ) ) )` - **Columns**: `_RowNumber, Row ID, Timestamp, Category, Troublesh...`

### ActivityLog_IncidentReports_MyTeam

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( [Category] = "Incident Report", OR( [Created By] = ANY( Current User[PersonID] ), [Created By].[Manager 1] = ANY( Current User[PersonID] ), [Created By].[Manager 2] = ANY( Current User[PersonID] ), [Created By]....`

### Case_Dropdown_ReadOnly

- Source table: `Case`
- Tables seen in slice filter: `Case`

### HR_E_NA_MyTeam

- Source table: `HR_Employees_NotesAttachments`
- Tables seen in slice filter: `HR_Employees_NotesAttachments`
- Row filter: `=OR( [CreatedBy] = ANY(Current User[PersonID]), [PersonID].[Manager 1] = ANY(Current User[PersonID]), [PersonID].[Manager 2] = ANY(Current User[PersonID]), [PersonID].[Manager 3] = ANY(Current User[PersonID]) )` - **C...`

### RefDocs_MoldConnections

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active] = TRUE, [Doc Type] = "RefDoc_Mold_Connections" )` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effec...`

### RefDocs_MoldCoolingChannelDesigns

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active] = TRUE, [Doc Type] = "RefDoc_Mold_CoolingChannelDesign" )` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revisi...`

### ActivityLog_MoldMovement_MinInfo

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Category] = "Mold Movement"` - **Columns**: `_RowNumber, ActivityLogID, Timestamp, Equipment, Molds, Description, Description_en, Description_zh-tw, Sub-Category 2, RefDocs_Read_Check, Mold Repair Order Number, Labe...`

### RefDocs_EquipmentManual

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active] = TRUE, [Doc Type] = "RefDoc_EquipmentManual" )` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effect...`

### ExternalLinks_My

- Source table: `ExternalLinks`
- Tables seen in slice filter: `ExternalLinks`
- Row filter: `=AND( [Active] = TRUE, OR( ISBLANK([Viewable Roles]), ISNOTBLANK(INTERSECT([Viewable Roles],SPLIT(ANY(Current User[Combined Appsheet Roles]),","))) ) )` - **Columns**: `_RowNumber, Row ID, Timestamp, ExternalLinkID, C...`

### Lookup_Dropdown_Type_ExternalLink

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("External Link",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order`

### ExternalLinks_Active_Dashboards

- Source table: `ExternalLinks`
- Tables seen in slice filter: `ExternalLinks`
- Row filter: `=AND( [Active] = TRUE, [Type] = "ExternalLinks_Dashboard", OR( ISBLANK([Viewable Roles]), ISNOTBLANK(INTERSECT([Viewable Roles],SPLIT(ANY(Current User[Appsheet Roles]),","))), ISNOTBLANK(INTERSECT([Viewable Roles],SPL...`

### ActivityLog_Attachments_All

- Source table: `ActivityLog_Attachments`
- Tables seen in slice filter: `ActivityLog_Attachments`

### RefDocs_ISO_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active] = TRUE, [Doc Type] = "RefDoc_ISO" )` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effective Date, Ne...`

### RefDocs_ISO_All

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=[Doc Type] = "RefDoc_ISO"` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effective Date, Next Review Date, Tags, Cr...`

### ExternalLinks_All

- Source table: `ExternalLinks`
- Tables seen in slice filter: `ExternalLinks`

### Lookup_Dropdown_Type

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Category, Sub-Category, Sub-Category 2, Sub-Category 3, Reviewer`

### ActivityLog_All

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`

### HR_Employees_All

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`

### RefDocs_MyViewable

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Lookup`, `Reference_Documents`
- Row filter: `=OR( ISBLANK(LOOKUP([Doc Type], "Lookup", "LookupID", "Viewable Roles")), NOT( ISBLANK( INTERSECT( ANY(Current User[Combined Appsheet Roles]), LOOKUP([Doc Type], "Lookup", "LookupID", "Viewable Roles") ) ) ) )` - **Co...`

### Lookup_Dropdown_Status_ITTicket

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Status",[Category]), IN("IT Ticket",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order, Reviewer`

### ERP_Asset_Details_All

- Source table: `ERP_Asset_Details`
- Tables seen in slice filter: `ERP_Asset_Details`

### RefDocs_All

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`

### RefDocs_InjectionMolding_Active

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=AND( [Active] = TRUE, OR( [Doc Type] = "RefDoc_InjectionMolding_StandardSettings", [Doc Type] = "RefDoc_EquipmentManual", CONTAINS([Doc Type], "RefDoc_Mold"), [Doc Type] = "RefDoc_SIP", [Doc Type] = "RefDoc_SOP" ) )`...`

### RefDocs_InjectionMoldingParameters_All

- Source table: `Reference_Documents`
- Tables seen in slice filter: `Reference_Documents`
- Row filter: `=[Doc Type]="RefDoc_InjectionMolding_StandardSettings"` - **Columns**: `_RowNumber, Title_en, File, Row ID, Timestamp, ReferenceDocumentID, Active, Doc Type, Image, Products, Molds, Equipment, Revision, Effective Date...`

### Lookup_Active

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=[Active] = TRUE` - **Columns**: `_RowNumber, Row ID, LookupID, Active, en, zh-tw, Sort Order, Description_en, Description_zh-tw, IntervalDays, Viewable Roles, Editable Roles, Initial Value, Category, Sub-Category, Su...`

### Maintenance_Items_All

- Source table: `Maintenance_Items`
- Tables seen in slice filter: `Maintenance_Items`

### ERP_Assets_Molds

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( STARTSWITH([品 號],"APD-"), STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, Last Reported Location, 產品名稱, Latest_MoldMovement, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Friendly Name, 品號分類, 模具編號, ...`

### ERP_Assets_Products

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( [Type]="Product", STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Friendly Name, 品號分類, 模具編號, 主模-模號, 替代模2, Equipment Type, Last Reported Location, ...`

### ERP_Assets_Equipment

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( [Type] = "Equipment", STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號分類, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, 模具編號, 主模-模號, 替代模2, Friendly Name, Type, Equipment Type, Last Reported Locati...`

### ERP_Assets_Equipment_Forklifts

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( STARTSWITH([品 號],"APL-"), STARTSWITH([品質狀態],"S") )` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, Last Reported Location, Latest_MoldMovement, 模具穴數, Related_ERP_Asset_Det...`

### ERP_Assets_Equipment_InjectionMachines

- Source table: `ERP_Data_Combined`
- Tables seen in slice filter: `ERP_Data_Combined`
- Row filter: `=AND( OR( STARTSWITH( [品 號], "AJW-" ), STARTSWITH( [品 號], "ASM-" ) ), STARTSWITH( [品質狀態], "S" ) )` - **Columns**: `_RowNumber, 品 號, 產品名稱, 品號細分類, 主要廠商, 簡 稱, 建立日期, 主要儲位, 主要倉庫, 倉庫簡稱, Type, 品號分類, 模具編號, 主模-模號, 替代模2, Friend...`

### Lookup_Dropdown_Type_HR_E_PR_Role

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Type",[Category]), IN("HR_E_PR_Role",[Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation, Sort Order`

### ActivityLog_MoldRepair

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Category] = "ActivityLog_MoldRepair"` - **Columns**: `_RowNumber, Row ID, ActivityLogID, Timestamp, Category, Sub-Category, Equipment, Molds, Products, Description, Troubleshooting Actions, Created By, Related Activ...`

### ActivityLog__Bot_HourlyMaintenance

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND( [Timestamp] > ( NOW() - "003:00:00" ), [Timestamp] < ( NOW() - "000:10:00" ), OR( ISBLANK([ActivityLog_Children_Cached]), ISBLANK([...`

### AL_S_I__Bot_NG_Product_Weight_Empty

- Source table: `ActivityLog_Session_Items`
- Tables seen in slice filter: `ActivityLog_Session_Items`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND( [ActivityLogID].[Category] = "NG_Product_Weight", ISBLANK([Amount]), ISBLANK([Thumbnail]), NOW() - [Timestamp] >= "168:00:00", ISBL...`

### AL_S_I_A__Bot_Untranslated

- Source table: `ActivityLog_Session_Items_Attachments`
- Tables seen in slice filter: `ActivityLog_Session_Items_Attachments`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND( ISNOTBLANK([Description]), OR(ISBLANK([Description_en]), ISBLANK([Description_zh-tw])) ) )` - **Columns**: `_RowNumber, Row ID, Tim...`

### Case__Bot_DailyMaintenance

- Source table: `Case`
- Tables seen in slice filter: `Case`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), NOW() - [Last Updated] < "168:00:00" )` - **Columns**: `_RowNumber, Row ID, Created On, Created On - Month, Last Updated, CaseID, Parent...`

### Case_Updates__Bot_DailyMaintenance

- Source table: `Case_Updates`
- Tables seen in slice filter: `Case_Updates`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), OR( AND( ISNOTBLANK([Update Description]), ISNOTBLANK([Update_Description_en]), ISNOTBLANK([Update_Description_zh-tw]) ), AND( ISNOTBLAN...`

### HR_E__Bot_DailyMaintenance

- Source table: `HR_Employees`
- Tables seen in slice filter: `HR_Employees`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), OR( [Employment Status] = "Employed", [Employment Status] = "Unpaid Leave of Absence", AND( [Employment Status] = "Not Employed", TODAY(...`

### HR_E_NA__Bot_CheckTranslations

- Source table: `HR_Employees_NotesAttachments`
- Tables seen in slice filter: `HR_Employees_NotesAttachments`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), OR( AND(ISNOTBLANK([Title]), OR(ISBLANK([Title_en]), ISBLANK([Title_zh-tw]))), AND( ISNOTBLANK([Description]), OR(ISBLANK([Description_e...`

### HRS_Data__Bot_NewEmployees

- Source table: `HRS_Data`
- Tables seen in slice filter: `HRS_Data`, `HR_Employees`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND(NOT(IN([員工編號], HR_Employees[Employee ID])), ISNOTBLANK([#])) )` - **Columns**: `_RowNumber, #, 員工編號, 姓名, 英文姓名, 護照姓名, 最近入境日期, 最近出境日期,...`

### HRS_Data_MasterNames__Bot_NoLongerEmployedEmployees

- Source table: `HRS_Data_MasterNames`
- Tables seen in slice filter: `HRS_Data_MasterNames`, `HR_Employees_CurrentlyEmployed_BasicInfo`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), ISBLANK( LOOKUP( [_THISROW].[PersonID], "HR_Employees_CurrentlyEmployed_BasicInfo", "PersonID", "PersonID" ) ) )` - **Columns**: `_RowNu...`

### Inventory_Mgmt__Bot_NeedsTranslation

- Source table: `Inventory_Mgmt`
- Tables seen in slice filter: `Inventory_Mgmt`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), OR( AND( ISNOTBLANK([Sample Retention Purpose]), OR(ISBLANK([Purpose_en]), ISBLANK([Purpose_zh-tw])) ), AND( ISNOTBLANK([Sample Existenc...`

### Inventory_Mgmt__Bot_NonZeroInventories

- Source table: `Inventory_Mgmt`
- Tables seen in slice filter: `Inventory_Mgmt`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), [Sample Current Quantity PCS] <> 0 )` - **Columns**: `_RowNumber, Row ID, InventoryTrackingID, Inventory Tracking Type, Timestamp, Times...`

### Lookup__Bot_Type_ALorCase

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND( IN("Type", [Category]), OR(IN("Case", [Sub-Category]), IN("ActivityLog", [Sub-Category])) ) )` - **Columns**: `_RowNumber, Row ID, ...`

### Lookup__Bot_RequiresSubcategory

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), AND( IN("Type", [Category]), ISBLANK([Sub-Category 2]), OR(IN("Case", [Sub-Category]), IN("ActivityLog", [Sub-Category])) ) )` - **Colum...`

### SuddenAbsenceRequests__Bot_NeedsTranslation

- Source table: `SuddenAbsenceRequests`
- Tables seen in slice filter: `GoogleTranslate`, `SuddenAbsenceRequests`
- Row filter: `=AND( OR(CONTEXT("Host") = "Server", USEREMAIL() = "admin@prodesign-group.com"), ISNOTBLANK([原因 Reason for requesting sudden leave เหตุผลขอลางานกะทันหัน]), ISNOTBLANK([Reason_GoogleTranslateID]), OR(ISBLANK([英文 Englis...`

### Lookup_Dropdown_UnitsOfMeasure

- Source table: `Lookup`
- Tables seen in slice filter: `Lookup`
- Row filter: `=AND( [Active] = TRUE, IN("Units", [Sub-Category]) )` - **Columns**: `_RowNumber, LookupID, Translation`

### Current User Settings

- Source table: `HR_Employees_AppSheet_Settings`
- Tables seen in slice filter: `HR_Employees_AppSheet_Settings`
- Row filter: `=[Appsheet Email] = USEREMAIL()` - **Columns**: `_RowNumber, Row ID, PersonID, Appsheet Email, Language, Team Members, Appsheet Dashboard Type, Appsheet Data Access Mode, Appsheet Views Access, Appsheet Navigation Bar...`

### PQ_TranslateRequest_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "translate_request", IN([Status], { "Queued", "Retry"}), OR(ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW()) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJobKey, Priority...`

### PQ_TranslateCollect_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "translate_collect", IN([Status], { "Queued", "Retry"}), OR(ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW()) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJobKey, Priority...`

### PQ_Notify_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( IN([JobType], {"notify", "notify_activitylog"}), IN([Status], {"Queued", "Retry"}), OR(ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW()) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJ...`

### PQ_Thumbnail_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "thumbnail_attachment", IN([Status], {"Queued", "Retry"}), OR( AND( ISNOTBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW() ), AND( ISBLANK([NextAttemptAt]), OR( ISBLANK([DelayMinutes]), (UTCNOW() -...`

### PQ_ThumbnailPush_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "thumbnail_push", IN([Status], {"Queued", "Retry"}), OR( ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW() ) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJobKey, Priority, ...`

### ActivityLog_Inspection_Warehouse

- Source table: `ActivityLog`
- Tables seen in slice filter: `ActivityLog`
- Row filter: `=[Sub-Category] = "ActivityLog_Inspection_Warehouse"` - **Columns**: `_RowNumber, Row ID, ActivityLogID, Timestamp, Category, Equipment, Molds, Products, Description, Troubleshooting Actions, Risk, Notification Group,...`

### ActivityLog_Session_Items_WarehouseInspection

- Source table: `ActivityLog_Session_Items`
- Tables seen in slice filter: `ActivityLog_Session_Items`
- Row filter: `=[ActivityLogID].[Sub-Category] = "ActivityLog_Inspection_Warehouse"` - **Columns**: `_RowNumber, Row ID, Timestamp, Performed By, ActivityLogID, ActivityLogItemID, Molds, Equipment, Products, Employees, Sort Order, T...`

### PQ_ActivityLog_Init_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "activitylog_init", IN([Status], {"Queued", "Retry"}), OR( ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW() ) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJobKey, Priority...`

### PQ_ActivityLog_GenerateItems_Ready

- Source table: `ProcessingQueue`
- Tables seen in slice filter: `ProcessingQueue`
- Row filter: `=AND( [JobType] = "activitylog_generate_items", IN([Status], {"Queued", "Retry"}), OR( ISBLANK([NextAttemptAt]), [NextAttemptAt] <= UTCNOW() ) )` - **Columns**: `_RowNumber, QueueID, SourceTable, JobType, ScopedJobKey...`

## HR_Employees

- Columns: 52
- Relationship hints: 13
- Notable columns with relationship evidence:
  - `Annual Review Preliminary`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Annual Review Stage 1`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Annual Review Stage 2`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Appsheet Menu Items`: suggested-values -> Lookup; suggested-values -> Lookup_Views_Home
  - `Appsheet Navigation Bar`: suggested-values -> Lookup; suggested-values -> Lookup_Views_Home
  - `Appsheet Views Access`: suggested-values -> Lookup; suggested-values -> Lookup_Dropdown_Views_Menu
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Current Operator Code`: lookup-formula -> HR_OperatorCodes
  - `Employee ID`: deref-usage -> UNKNOWN
  - `Name_ZH`: lookup-formula -> HRS_Data

## Lookup

- Columns: 35
- Relationship hints: 8
- Notable columns with relationship evidence:
  - `Category`: suggested-values -> Lookup_Dropdown_Type
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Last Modified By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Reviewer`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `RowCount_Realtime`: lookup-formula -> RowCount
  - `Sub-Category`: suggested-values -> Lookup_Dropdown_Type
  - `Sub-Category 2`: suggested-values -> Lookup_Dropdown_Type
  - `Sub-Category 3`: suggested-values -> Lookup_Dropdown_Type

## ActivityLog

- Columns: 64
- Relationship hints: 14
- Notable columns with relationship evidence:
  - `ActivityLog Status`: suggested-values -> Lookup_Dropdown_Status_EntryExitRecord; suggested-values -> Lookup_Dropdown_Status_IncidentReport
  - `Category`: deref-usage -> UNKNOWN; suggested-values -> Lookup_Dropdown_Type_ActivityLog_Category
  - `Created By`: deref-usage -> HR_Employees; deref-usage -> HR_Employees_CurrentlyEmployed_BasicInfo; suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Latest Child ActivityLog`: ref-type -> UNKNOWN
  - `Notification Group`: suggested-values -> Lookup_Dropdown_NotificationGroups
  - `Parent ActivityLogID`: deref-usage -> UNKNOWN; ref-type -> ActivityLog
  - `Sub-Category`: deref-usage -> UNKNOWN; suggested-values -> Lookup
  - `Sub-Category 2`: suggested-values -> Lookup

## Case

- Columns: 42
- Relationship hints: 11
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Customers`: suggested-values -> Customers
  - `Next Step Responsible Person`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Parent ActivityLogID`: suggested-values -> ActivityLog
  - `Parent Case ID`: deref-usage -> HR_Employees_CurrentlyEmployed_BasicInfo; deref-usage -> UNKNOWN; ref-type -> Case; suggested-values -> Case
  - `Status`: deref-usage -> UNKNOWN
  - `Sub-Type`: deref-usage -> UNKNOWN
  - `Type`: deref-usage -> UNKNOWN

## Case_Attachments

- Columns: 15
- Relationship hints: 5
- Notable columns with relationship evidence:
  - `Attachment Category`: suggested-values -> Lookup
  - `CaseID`: deref-usage -> UNKNOWN; ref-type -> Case; suggested-values -> Case
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Case_Updates_Attachments

- Columns: 14
- Relationship hints: 4
- Notable columns with relationship evidence:
  - `Attachment Category`: suggested-values -> Lookup_Dropdown_Type_AttachmentCategory
  - `CaseUpdateID`: deref-usage -> UNKNOWN; ref-type -> CaseUpdate
  - `CreatedBy Key`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Case_Updates

- Columns: 34
- Relationship hints: 9
- Notable columns with relationship evidence:
  - `CaseID`: deref-usage -> UNKNOWN; ref-type -> Case; suggested-values -> Case
  - `Created By`: deref-usage -> HR_Employees; deref-usage -> HR_Employees_CurrentlyEmployed_BasicInfo; suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `New Next Step Responsible Person`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `New Status`: suggested-values -> Lookup_Dropdown_Status
  - `Update Type`: suggested-values -> Lookup_Dropdown_Type_CaseUpdate

## HR_Employees_NotesAttachments

- Columns: 27
- Relationship hints: 4
- Notable columns with relationship evidence:
  - `Category`: deref-usage -> UNKNOWN
  - `Category 2`: deref-usage -> UNKNOWN
  - `EmployeeAttachmentID_Ref`: ref-type -> UNKNOWN
  - `PersonID`: ref-type -> Person

## ActivityLog_Attachments

- Columns: 27
- Relationship hints: 5
- Notable columns with relationship evidence:
  - `ActivityLog Type`: suggested-values -> Lookup
  - `ActivityLogID`: deref-usage -> UNKNOWN; ref-type -> ActivityLog
  - `Attachment Category`: suggested-values -> Lookup_Dropdown_Type_AttachmentCategory
  - `CreatedBy`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Maintenance_Items

- Columns: 25
- Relationship hints: 2
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Frequency`: suggested-values -> Lookup_Frequency

## Maintenance_Session_Items

- Columns: 25
- Relationship hints: 4
- Notable columns with relationship evidence:
  - `Employees`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `MaintenanceItemID`: deref-usage -> UNKNOWN
  - `MaintenanceSessionID`: ref-type -> MaintenanceSession
  - `Performed By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Maintenance_Sessions

- Columns: 16
- Relationship hints: 5
- Notable columns with relationship evidence:
  - `EquipmentID`: deref-usage -> UNKNOWN; suggested-values -> ERP_Data_Combined
  - `Maintenance Type`: deref-usage -> UNKNOWN
  - `Overall Status`: suggested-values -> Lookup_Dropdown_Status_Maintenance
  - `Performed By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## ActivityLog_Items

- Columns: 25
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## ERP_Data_Combined

- Columns: 24
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Related_RefDoc_Cached`: suggested-values -> RefDocs_All_Active

## Maintenance_Session_Items_Attachments

- Columns: 13
- Relationship hints: 3
- Notable columns with relationship evidence:
  - `Attachment Category`: suggested-values -> Lookup
  - `CreatedBy Key`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `MaintenanceSessionID`: ref-type -> MaintenanceSession

## ERP_Asset_Details

- Columns: 20
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## ActivityLog_Session_Items

- Columns: 26
- Relationship hints: 7
- Notable columns with relationship evidence:
  - `ActivityLogID`: deref-usage -> HR_Employees_CurrentlyEmployed_BasicInfo; deref-usage -> UNKNOWN; ref-type -> ActivityLog
  - `ActivityLogItemID`: deref-usage -> UNKNOWN
  - `Employees`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Performed By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Unit of Measure`: suggested-values -> Lookup_Dropdown_UnitsOfMeasure

## ActivityLog_Session_Items_Attachments

- Columns: 16
- Relationship hints: 4
- Notable columns with relationship evidence:
  - `ActivityLogSessionsItemID`: deref-usage -> UNKNOWN; ref-type -> ActivityLogSessionsItem
  - `Attachment Category`: suggested-values -> Lookup
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## HRS_Data

- Columns: 28
- Relationship hints: 0
- No relationship hints detected.

## GoogleTranslate

- Columns: 15
- Relationship hints: 0
- No relationship hints detected.

## GoogleForm_SuddenAbsenceRequests

- Columns: 8
- Relationship hints: 0
- No relationship hints detected.

## SuddenAbsenceRequests

- Columns: 16
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Reference_Documents

- Columns: 32
- Relationship hints: 3
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Doc Type`: deref-usage -> UNKNOWN
  - `Products`: suggested-values -> ERP_Assets_Products_All

## HR_Employees_PerformanceRecords

- Columns: 17
- Relationship hints: 6
- Notable columns with relationship evidence:
  - `ActivityLogID`: deref-usage -> UNKNOWN; ref-type -> ActivityLog
  - `PersonID`: deref-usage -> UNKNOWN; suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `Role`: deref-usage -> UNKNOWN; suggested-values -> Lookup_Dropdown_Type_HR_E_PR_Role

## Inventory_Mgmt

- Columns: 30
- Relationship hints: 4
- Notable columns with relationship evidence:
  - `CaseID`: ref-type -> Case
  - `Inventory Tracking Type`: suggested-values -> Lookup_Dropdown_Type_InventoryMgmt
  - `Product`: deref-usage -> UNKNOWN
  - `Sample Retention Personnel`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Inventory_WithdrawalRecord

- Columns: 18
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Withdrawn By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo

## Inventory_WithdrawalRecord_Attachments

- Columns: 14
- Relationship hints: 2
- Notable columns with relationship evidence:
  - `Created By`: suggested-values -> HR_Employees_CurrentlyEmployed_BasicInfo
  - `WithdrawalRecordID`: ref-type -> WithdrawalRecord

## ExternalLinks

- Columns: 20
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `Type`: suggested-values -> Lookup_Dropdown_Type_ExternalLink

## HRS_Data_MasterNames

- Columns: 16
- Relationship hints: 0
- No relationship hints detected.

## HeartBeat

- Columns: 3
- Relationship hints: 0
- No relationship hints detected.

## RowCount

- Columns: 5
- Relationship hints: 0
- No relationship hints detected.

## HR_Employees_AppSheet_Settings

- Columns: 29
- Relationship hints: 8
- Notable columns with relationship evidence:
  - `Appsheet Dashboard Type`: suggested-values -> Lookup_Dropdown_Dashboards
  - `Appsheet Menu Items`: suggested-values -> Lookup_Dropdown_Views_Menu
  - `Appsheet Navigation Bar`: suggested-values -> Lookup_Dropdown_Views_Menu
  - `Appsheet Notification Group`: suggested-values -> Lookup_Dropdown_NotificationGroups
  - `Appsheet Roles`: suggested-values -> Lookup_Dropdown_Appsheet_Role
  - `Appsheet Views Access`: suggested-values -> Lookup_Dropdown_Views_Menu
  - `Language`: suggested-values -> Lookup_Dropdown_Language
  - `PersonID`: deref-usage -> UNKNOWN

## API_Target_Queue

- Columns: 5
- Relationship hints: 0
- No relationship hints detected.

## Customer_Details

- Columns: 7
- Relationship hints: 0
- No relationship hints detected.

## ProcessingQueue

- Columns: 46
- Relationship hints: 1
- Notable columns with relationship evidence:
  - `ReadyTranslationCount`: lookup-formula -> GoogleTranslate

