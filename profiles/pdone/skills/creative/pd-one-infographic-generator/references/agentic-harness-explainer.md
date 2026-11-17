# Agentic Harness Explainer Infographics

Use this reference when creating PD One visuals that compare a normal chatbot with PD One or explain how the agentic harness works.

## Recommended structure

For an employee/admin-friendly architecture explainer, use a portrait comparison poster with:

1. **Top comparison**
   - Traditional Chatbot: `User Message → LLM Reply`
   - PD One Agent: `Message → Harness → Tools → Verified Reply`
   - Keep the difference clear: chatbot replies; PD One routes through policy, tools, and verification.

2. **Agentic harness layers**
   Show these as an 8-step pipeline or two-row grid:
   1. `Channel Adapter` — `Mattermost / Telegram`
   2. `Identity Resolver` — `exact sender ID`
   3. `Policy Gate` — `OpenClaw scope`
   4. `Context Builder` — `thread + allowed data`
   5. `Skill Loader` — `runbooks + procedures`
   6. `Planner` — `decide next action`
   7. `Tool Router` — `approved tools only`
   8. `Verifier` — `evidence before reply`

3. **Safety controls side stack**
   Use concise chips:
   - `Approval gates`
   - `Dry-run first`
   - `Sensitive data filter`
   - `No out-of-scope writes`
   - `Review log when needed`

4. **Bottom formula**
   `PD One = LLM reasoning + Hermes tool harness + Hermes PD One policy + skills + verification`

5. **Capability strip/table**
   Keep rows short and readable:
   - `Access`: chatbot broad/minimal checks; PD One scoped to identity & policy
   - `Action`: chatbot suggests; PD One executes via approved tools
   - `Safety`: chatbot basic filters; PD One multi-layer controls
   - `Memory`: chatbot short chat context; PD One thread + allowed data + skills
   - `Proof`: chatbot limited/none; PD One receipts & verification

## Prompting notes

- Ask for **large typography** and **short labels**. The harness diagram has many elements; avoid paragraphs.
- Place the PD One avatar on the right or header area and keep it visible/unclipped.
- If exact architecture text matters, prefer deterministic HTML/SVG/Pillow compositing over image-model text rendering.
- If using image generation, QA for: correct title, visible avatar, the 8 harness layers, safety controls, bottom formula, no watermark, and major text errors.
