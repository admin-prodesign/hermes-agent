(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const REG = window.__HERMES_PLUGINS__;
  if (!SDK || !REG) return;
  const React = SDK.React;
  const h = React.createElement;
  const useEffect = SDK.hooks.useEffect;
  const useMemo = SDK.hooks.useMemo;
  const useState = SDK.hooks.useState;

  function api(path) {
    return SDK.fetchJSON("/api/plugins/pd-one-ops" + path);
  }

  function fmt(value) {
    if (value === null || value === undefined || value === "") return "—";
    return String(value);
  }

  function Kpi(props) {
    return h("div", { className: "pdops-card" },
      h("div", { className: "pdops-kpi-value" }, fmt(props.value)),
      h("div", { className: "pdops-kpi-label" }, props.label)
    );
  }

  function Badge(props) {
    return h("span", { className: "pdops-badge " + (props.tone || "") }, props.children);
  }

  function Table(props) {
    return h("div", { style: { overflowX: "auto" } },
      h("table", { className: "pdops-table" },
        h("thead", null, h("tr", null, props.columns.map(c => h("th", { key: c.key }, c.label)))),
        h("tbody", null,
          props.rows.length ? props.rows.map((row, idx) => h("tr", { key: row.id || row.name || idx },
            props.columns.map(c => h("td", { key: c.key }, c.render ? c.render(row) : fmt(row[c.key])))))
          : h("tr", null, h("td", { colSpan: props.columns.length, className: "pdops-muted" }, "No rows"))
        )
      )
    );
  }

  function Section(props) {
    return h("section", { className: "pdops-section" },
      h("h2", null, props.title),
      props.children
    );
  }

  function PDOneOpsPage() {
    const [data, setData] = useState(null);
    const [err, setErr] = useState(null);
    const [query, setQuery] = useState("");
    const [tab, setTab] = useState("drift");

    const load = () => {
      setErr(null);
      api("/summary").then(setData).catch(e => setErr(String(e && e.message ? e.message : e)));
    };

    useEffect(() => { load(); }, []);

    const q = query.trim().toLowerCase();
    const filterRows = (rows) => !q ? rows : rows.filter(row => JSON.stringify(row).toLowerCase().includes(q));
    const counts = data ? data.counts : {};
    const cronRows = data ? filterRows(data.cron_jobs || []) : [];
    const driftRows = data ? filterRows(data.drift || []) : [];
    const skillRows = data ? filterRows(data.skills || []) : [];
    const supervisorRows = data ? filterRows(data.supervisor || []) : [];

    const activeRows = useMemo(() => {
      if (!data) return [];
      if (tab === "cron") return cronRows;
      if (tab === "supervisor") return supervisorRows;
      if (tab === "skills") return skillRows;
      return driftRows;
    }, [data, tab, query]);

    const columns = {
      drift: [
        { key: "severity", label: "Severity", render: r => h(Badge, { tone: r.severity }, r.severity) },
        { key: "kind", label: "Kind" },
        { key: "item", label: "Item", render: r => h("code", null, r.item) },
        { key: "message", label: "Message" },
      ],
      cron: [
        { key: "name", label: "Job" },
        { key: "enabled", label: "State", render: r => h(Badge, { tone: r.enabled ? "low" : "medium" }, r.enabled ? (r.state || "enabled") : (r.state || "disabled")) },
        { key: "schedule", label: "Schedule" },
        { key: "last_status", label: "Last" },
        { key: "next_run_at", label: "Next" },
        { key: "script", label: "Script", render: r => h("span", { className: "pdops-path" }, fmt(r.script)) },
      ],
      supervisor: [
        { key: "name", label: "Automation" },
        { key: "criticality", label: "Criticality", render: r => h(Badge, { tone: r.criticality === "high" ? "high" : r.criticality === "medium" ? "medium" : "low" }, fmt(r.criticality)) },
        { key: "touches_external_systems", label: "External", render: r => r.touches_external_systems ? "yes" : "no" },
        { key: "autorepair", label: "Autorepair" },
        { key: "alert_expectation", label: "Alert expectation" },
      ],
      skills: [
        { key: "name", label: "Skill" },
        { key: "category", label: "Category" },
        { key: "description", label: "Description" },
        { key: "path", label: "Path", render: r => h("span", { className: "pdops-path" }, r.path) },
      ],
    };

    return h("div", { className: "pdops-page" },
      h("div", null,
        h("h1", null, "PD One Ops"),
        h("p", { className: "pdops-muted" }, "Read-only MVP catalog for PD One automations, skills, policies, supervisor coverage, and drift signals.")
      ),
      err ? h("div", { className: "pdops-section pdops-error" }, "Failed to load: " + err) : null,
      !data ? h("div", { className: "pdops-section" }, "Loading PD One operations catalog…") : h(React.Fragment, null,
        h("div", { className: "pdops-kpis" },
          h(Kpi, { label: "Cron jobs", value: counts.cron_total }),
          h(Kpi, { label: "Enabled cron", value: counts.cron_enabled }),
          h(Kpi, { label: "Supervisor entries", value: counts.supervisor_total }),
          h(Kpi, { label: "External-touching", value: counts.supervisor_external }),
          h(Kpi, { label: "Skills", value: counts.skills_total }),
          h(Kpi, { label: "Drift signals", value: counts.drift_total })
        ),
        h("div", { className: "pdops-grid2" },
          h(Section, { title: "Supervisor criticality" },
            h("pre", { className: "pdops-small" }, JSON.stringify(data.supervisor_by_criticality, null, 2))
          ),
          h(Section, { title: "Skill categories" },
            h("pre", { className: "pdops-small" }, JSON.stringify(data.skills_by_category, null, 2))
          )
        ),
        h(Section, { title: "Inventory" },
          h("div", { className: "pdops-toolbar" },
            ["drift", "cron", "supervisor", "skills"].map(name => h("button", {
              key: name,
              className: "pdops-button",
              onClick: () => setTab(name),
              style: tab === name ? { outline: "2px solid currentColor" } : null,
            }, name)),
            h("input", { className: "pdops-input", value: query, placeholder: "Filter rows…", onChange: e => setQuery(e.target.value) }),
            h("button", { className: "pdops-button", onClick: load }, "Refresh")
          ),
          h("p", { className: "pdops-muted pdops-small" }, "Generated at " + data.generated_at + " from " + data.profile_home),
          h(Table, { rows: activeRows, columns: columns[tab] })
        ),
        h(Section, { title: "Policies and script counts" },
          h("p", null, "Policies: ", h(Badge, null, counts.policies_total), "  Scripts: ", h(Badge, null, counts.scripts_total)),
          h("p", { className: "pdops-muted pdops-small" }, "This MVP avoids displaying sensitive policy-cache, log, session, credential, or env contents.")
        )
      )
    );
  }

  REG.register("pd-one-ops", PDOneOpsPage);
})();
