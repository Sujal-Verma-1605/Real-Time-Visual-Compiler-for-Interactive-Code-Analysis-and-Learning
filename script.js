const codeInput = document.getElementById("code-input");
const lineNumbers = document.getElementById("line-numbers");
const runButton = document.getElementById("run-btn");
const clearButton = document.getElementById("clear-btn");
const tabs = document.querySelectorAll(".tab");
const panels = {
  tokens: document.getElementById("panel-tokens"),
  syntax: document.getElementById("panel-syntax"),
  semantic: document.getElementById("panel-semantic"),
  intermediate: document.getElementById("panel-intermediate"),
  optimization: document.getElementById("panel-optimization"),
  machine: document.getElementById("panel-machine"),
};

const API_URL = "http://127.0.0.1:5000/compile";

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function updateLineNumbers() {
  const lines = codeInput.value.split("\n").length;
  const numbers = Array.from({ length: Math.max(lines, 1) }, (_, i) => i + 1).join("\n");
  lineNumbers.textContent = numbers;
}

function syncScroll() {
  lineNumbers.scrollTop = codeInput.scrollTop;
}

function setActiveTab(tabName) {
  tabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  Object.entries(panels).forEach(([name, panel]) => {
    panel.classList.toggle("active", name === tabName);
  });
}

function renderList(items) {
  if (!items || items.length === 0) {
    return `<p class="muted">No items.</p>`;
  }
  return `<ul class="list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function renderCodeBlock(lines) {
  if (!lines || lines.length === 0) {
    return `<p class="muted">No code generated.</p>`;
  }
  return `<pre>${escapeHtml(lines.join("\n"))}</pre>`;
}

function getNodeLabel(node) {
  const nodeType = node.type || "Node";
  const details = [];
  if (node.name) details.push(node.name);
  if (node.identifier) details.push(node.identifier);
  if (node.operator) details.push(node.operator);
  if (node.var_type) details.push(node.var_type);
  if (typeof node.value === "number") details.push(String(node.value));
  if (node.return_type) details.push(`returns ${node.return_type}`);
  return details.length ? `${nodeType} (${details.join(", ")})` : nodeType;
}

function toParseTreeModel(node, label = "") {
  if (node === null || node === undefined) {
    return { label: label || "empty", children: [] };
  }
  if (typeof node !== "object") {
    return { label: String(node), children: [] };
  }

  const nodeLabel = label || getNodeLabel(node);
  const children = [];

  if (node.identifier) children.push({ label: `id: ${node.identifier}`, children: [] });
  if (node.name) children.push({ label: `name: ${node.name}`, children: [] });
  if (node.operator) children.push({ label: `op: ${node.operator}`, children: [] });
  if (typeof node.value === "number") children.push({ label: `num: ${node.value}`, children: [] });

  const childEntries = Object.entries(node).filter(([key, value]) => {
    if (
      ["type", "identifier", "var_type", "operator", "name", "value", "line", "return_type"].includes(key)
    ) {
      return false;
    }
    return value !== null && value !== undefined;
  });

  childEntries.forEach(([key, value]) => {
    if (Array.isArray(value)) {
      if (value.length === 0) {
        children.push({ label: `${key} -> empty`, children: [] });
      } else {
        const arrayNode = { label: key, children: value.map((item) => toParseTreeModel(item)) };
        children.push(arrayNode);
      }
      return;
    }
    children.push(toParseTreeModel(value, key));
  });

  return { label: nodeLabel, children };
}

function renderTreeModel(model) {
  const childrenHtml = model.children.map((child) => renderTreeModel(child)).join("");
  return `
    <div class="ptree-branch">
      <div class="ptree-node">${escapeHtml(model.label)}</div>
      ${model.children.length ? `<div class="ptree-children">${childrenHtml}</div>` : ""}
    </div>
  `;
}

function renderTokens(tokens) {
  if (!tokens || tokens.length === 0) {
    panels.tokens.innerHTML = "<p class='muted'>No tokens available.</p>";
    return;
  }
  const rows = tokens
    .map(
      (token) => `
      <tr>
        <td>${escapeHtml(token.type)}</td>
        <td>${escapeHtml(token.value)}</td>
        <td>${escapeHtml(token.line)}</td>
        <td>${escapeHtml(token.column)}</td>
      </tr>
    `
    )
    .join("");
  panels.tokens.innerHTML = `
    <h3>Lexical Tokens</h3>
    <p class="muted">Token stream from regex-based lexical analysis.</p>
    <table>
      <thead>
        <tr><th>Type</th><th>Value</th><th>Line</th><th>Column</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderSyntax(syntax) {
  const errors = syntax.errors || [];
  const statusClass = syntax.status === "valid" ? "" : "error";
  const hasTree = Boolean(syntax.tree && typeof syntax.tree === "object" && Object.keys(syntax.tree).length);
  const parseTreeModel = hasTree ? toParseTreeModel(syntax.tree, "Program") : null;
  const visualTree = hasTree
    ? `<div class="ptree-wrap">${renderTreeModel(parseTreeModel)}</div>`
    : "<p class='muted'>Parse tree unavailable.</p>";
  const rawTree = hasTree ? `<pre>${escapeHtml(JSON.stringify(syntax.tree, null, 2))}</pre>` : "";

  panels.syntax.innerHTML = `
    <h3>Syntax Result</h3>
    <p><strong>Status:</strong> <span class="${statusClass}">${escapeHtml(syntax.status || "unknown")}</span></p>
    ${errors.length ? `<p class="error"><strong>Errors:</strong></p>${renderList(errors)}` : "<p class='muted'>No syntax errors.</p>"}
    <h3>Parse Tree</h3>
    ${visualTree}
    ${hasTree ? `<h3>Parse Tree (Raw JSON)</h3>${rawTree}` : ""}
  `;
}

function renderSemantic(semantic) {
  const errors = semantic.errors || [];
  const warnings = semantic.warnings || [];
  const symbols = semantic.symbol_table || [];
  const symbolRows = symbols
    .map(
      (entry) => `
      <tr>
        <td>${escapeHtml(entry.name)}</td>
        <td>${escapeHtml(entry.type)}</td>
        <td>${entry.initialized ? "Yes" : "No"}</td>
      </tr>
    `
    )
    .join("");

  panels.semantic.innerHTML = `
    <h3>Semantic Analysis</h3>
    <p class="muted">Checks declarations, type consistency, and variable usage.</p>
    ${errors.length ? `<p class="error"><strong>Errors:</strong></p>${renderList(errors)}` : "<p class='muted'>No semantic errors.</p>"}
    ${warnings.length ? `<p><strong>Warnings:</strong></p>${renderList(warnings)}` : "<p class='muted'>No semantic warnings.</p>"}
    <h3>Symbol Table</h3>
    ${
      symbols.length
        ? `
      <table>
        <thead>
          <tr><th>Name</th><th>Type</th><th>Initialized</th></tr>
        </thead>
        <tbody>${symbolRows}</tbody>
      </table>
    `
        : "<p class='muted'>Symbol table is empty.</p>"
    }
  `;
}

function renderIntermediate(intermediateCode) {
  panels.intermediate.innerHTML = `
    <h3>Three Address Code (TAC)</h3>
    <p class="muted">Step-by-step expression breakdown with temporary variables.</p>
    ${renderCodeBlock(intermediateCode)}
  `;
}

function renderOptimization(optimization) {
  panels.optimization.innerHTML = `
    <h3>Optimization</h3>
    <p class="muted">Constant folding and simple dead temporary elimination.</p>
    <div class="split-view">
      <div>
        <h3>Before</h3>
        ${renderCodeBlock(optimization.before || [])}
      </div>
      <div>
        <h3>After</h3>
        ${renderCodeBlock(optimization.after || [])}
      </div>
    </div>
  `;
}

function renderMachineCode(machineCode) {
  panels.machine.innerHTML = `
    <h3>Simulated Machine Code</h3>
    <p class="muted">Instruction sequence logically generated from optimized TAC.</p>
    ${renderCodeBlock(machineCode)}
  `;
}

function clearPanels() {
  Object.values(panels).forEach((panel) => {
    panel.innerHTML = "<p class='muted'>Run the compiler to see this stage output.</p>";
  });
}

async function runCompiler() {
  const source = codeInput.value.trim();
  if (!source) {
    clearPanels();
    panels.tokens.innerHTML = "<p class='muted'>Please enter source code first.</p>";
    setActiveTab("tokens");
    return;
  }

  runButton.disabled = true;
  runButton.textContent = "Running...";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_code: source }),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const result = await response.json();
    renderTokens(result.tokens || []);
    renderSyntax(result.syntax || {});
    renderSemantic(result.semantic || {});
    renderIntermediate(result.intermediate_code || []);
    renderOptimization(result.optimized_code || { before: [], after: [] });
    renderMachineCode(result.machine_code || []);
    setActiveTab("syntax");
  } catch (error) {
    clearPanels();
    panels.tokens.innerHTML = `<p class="error">Compilation failed: ${escapeHtml(error.message)}</p>`;
    setActiveTab("tokens");
  } finally {
    runButton.disabled = false;
    runButton.textContent = "Run";
  }
}

function clearAll() {
  codeInput.value = "";
  updateLineNumbers();
  clearPanels();
  setActiveTab("tokens");
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => setActiveTab(tab.dataset.tab));
});

codeInput.addEventListener("input", updateLineNumbers);
codeInput.addEventListener("scroll", syncScroll);
runButton.addEventListener("click", runCompiler);
clearButton.addEventListener("click", clearAll);

clearPanels();
updateLineNumbers();
