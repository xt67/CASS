/**
 * =============================================================================
 * CASS Frontend - Main Application (Chartbrew-style UI)
 * =============================================================================
 */

import { streamChat, checkHealth, getSchema, apiFetch, setApiToken } from "./utils/sse.js";

// =============================================================================
// DOM Elements
// =============================================================================

// Sidebar
const btnConnection = document.getElementById("btn-connection");
const btnSchema = document.getElementById("btn-schema");
const btnAdd = document.getElementById("btn-add");

// SQL Editor
const sqlInput = document.getElementById("sql-input");
const lineNumbers = document.getElementById("line-numbers");
const btnRun = document.getElementById("btn-run");

// Chat
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const aiResponse = document.getElementById("ai-response");
const aiMessage = document.getElementById("ai-message");

// Results
const emptyState = document.getElementById("empty-state");
const dataTable = document.getElementById("data-table");
const tableHead = document.getElementById("table-head");
const tableBody = document.getElementById("table-body");
const jsonView = document.getElementById("json-view");
const resultsFooter = document.getElementById("results-footer");
const rowCount = document.getElementById("row-count");

// View toggles
const viewTable = document.getElementById("view-table");
const viewJson = document.getElementById("view-json");

// Status
const statusIndicator = document.getElementById("status-indicator");

// Schema Modal
const schemaModal = document.getElementById("schema-modal");
const schemaContent = document.getElementById("schema-content");
const closeSchema = document.getElementById("close-schema");

// =============================================================================
// State
// =============================================================================

let isLoading = false;
let currentResults = null;
let currentView = "table";

// =============================================================================
// Functions
// =============================================================================

/**
 * Update connection status
 */
function updateStatus(connected, message = "") {
  const dot = statusIndicator.querySelector(".status-dot");
  const text = statusIndicator.querySelector("span:last-child");
  
  if (connected) {
    dot.className = "status-dot bg-green-500";
    text.className = "text-green-600";
    text.textContent = message || "Connected";
  } else {
    dot.className = "status-dot bg-red-500";
    text.className = "text-red-600";
    text.textContent = message || "Disconnected";
  }
}

/**
 * Update line numbers in SQL editor
 */
function updateLineNumbers() {
  const lines = sqlInput.value.split("\n").length;
  lineNumbers.innerHTML = Array.from({ length: lines }, (_, i) => `<div>${i + 1}</div>`).join("");
}

/**
 * Set loading state
 */
function setLoading(loading) {
  isLoading = loading;
  btnRun.disabled = loading;
  sendBtn.disabled = loading;
  
  if (loading) {
    btnRun.innerHTML = `
      <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
      </svg>
      Running...
    `;
  } else {
    btnRun.innerHTML = `
      Run query
      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
        <path d="M8 5v14l11-7z"/>
      </svg>
    `;
  }
}

/**
 * Show AI response message
 */
function showAiMessage(message) {
  aiResponse.classList.remove("hidden");
  aiMessage.textContent = message;
}

/**
 * Hide AI response
 */
function hideAiMessage() {
  aiResponse.classList.add("hidden");
}

/**
 * Display results in table
 */
function displayResults(data) {
  currentResults = data;
  
  if (!data || data.length === 0) {
    emptyState.classList.remove("hidden");
    dataTable.classList.add("hidden");
    jsonView.classList.add("hidden");
    resultsFooter.classList.add("hidden");
    return;
  }
  
  emptyState.classList.add("hidden");
  resultsFooter.classList.remove("hidden");
  rowCount.textContent = data.length;
  
  // Build table
  const columns = Object.keys(data[0]);
  
  tableHead.innerHTML = `<tr>${columns.map(col => `<th>${escapeHtml(col)}</th>`).join("")}</tr>`;
  tableBody.innerHTML = data.map(row => 
    `<tr>${columns.map(col => `<td>${formatCell(row[col])}</td>`).join("")}</tr>`
  ).join("");
  
  // Build JSON
  jsonView.textContent = JSON.stringify(data, null, 2);
  
  // Show current view
  if (currentView === "table") {
    dataTable.classList.remove("hidden");
    jsonView.classList.add("hidden");
  } else {
    dataTable.classList.add("hidden");
    jsonView.classList.remove("hidden");
  }
}

/**
 * Format cell value
 */
function formatCell(value) {
  if (value === null || value === undefined) {
    return '<span class="text-gray-400">NULL</span>';
  }
  if (typeof value === "object") {
    return escapeHtml(JSON.stringify(value));
  }
  if (typeof value === "number") {
    return `<span class="text-cyan-600 font-medium">${value.toLocaleString()}</span>`;
  }
  return escapeHtml(String(value));
}

/**
 * Escape HTML
 */
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/**
 * Run SQL query directly
 */
async function runQuery() {
  const sql = sqlInput.value.trim();
  if (!sql || isLoading) return;
  
  setLoading(true);
  hideAiMessage();
  
  try {
    const response = await apiFetch("/sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Query failed");
    }
    
    const result = await response.json();
    displayResults(result.data);
  } catch (error) {
    showAiMessage(`Error: ${error.message}`);
    displayResults([]);
  } finally {
    setLoading(false);
  }
}

/**
 * Handle chat submission (AI generates SQL)
 */
async function handleChat(event) {
  event.preventDefault();
  
  const message = messageInput.value.trim();
  if (!message || isLoading) return;
  
  messageInput.value = "";
  setLoading(true);
  showAiMessage("I tried to generate a query based on your question. If it's not what you want, you can ask for clarification or try a different question.");
  
  try {
    // Use streaming to generate SQL
    let resultData = null;
    
    await new Promise((resolve, reject) => {
      streamChat(message, {
        onSql(sql) {
          sqlInput.value = sql;
          updateLineNumbers();
        },
        onData(data) {
          resultData = data;
        },
        onError(error) {
          reject(new Error(error));
        },
        onEnd() {
          resolve();
        }
      });
    });
    
    if (resultData) {
      displayResults(resultData);
    }
    
  } catch (error) {
    showAiMessage(`Error: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

/**
 * Show schema modal
 */
async function showSchemaModal() {
  try {
    const schema = await getSchema();
    schemaContent.textContent = schema;
    schemaModal.classList.remove("hidden");
  } catch (error) {
    alert("Failed to load schema: " + error.message);
  }
}

/**
 * Check backend connection
 */
async function checkConnection() {
  try {
    const status = await checkHealth();
    updateStatus(true, status.message || "Connected");
  } catch {
    updateStatus(false, "Backend offline");
  }
}

// =============================================================================
// Event Listeners
// =============================================================================

// SQL Editor
sqlInput.addEventListener("input", updateLineNumbers);
sqlInput.addEventListener("keydown", (e) => {
  // Tab key inserts spaces
  if (e.key === "Tab") {
    e.preventDefault();
    const start = sqlInput.selectionStart;
    const end = sqlInput.selectionEnd;
    sqlInput.value = sqlInput.value.substring(0, start) + "  " + sqlInput.value.substring(end);
    sqlInput.selectionStart = sqlInput.selectionEnd = start + 2;
    updateLineNumbers();
  }
  // Ctrl+Enter runs query
  if (e.key === "Enter" && e.ctrlKey) {
    e.preventDefault();
    runQuery();
  }
});

// Run button
btnRun.addEventListener("click", runQuery);

// Chat form
chatForm.addEventListener("submit", handleChat);

// View toggles
viewTable.addEventListener("click", () => {
  currentView = "table";
  viewTable.classList.add("active");
  viewJson.classList.remove("active");
  if (currentResults) {
    dataTable.classList.remove("hidden");
    jsonView.classList.add("hidden");
  }
});

viewJson.addEventListener("click", () => {
  currentView = "json";
  viewJson.classList.add("active");
  viewTable.classList.remove("active");
  if (currentResults) {
    dataTable.classList.add("hidden");
    jsonView.classList.remove("hidden");
  }
});

// Schema modal
btnSchema.addEventListener("click", showSchemaModal);
closeSchema.addEventListener("click", () => schemaModal.classList.add("hidden"));
schemaModal.querySelector(".modal-backdrop").addEventListener("click", () => schemaModal.classList.add("hidden"));

// New query
btnAdd.addEventListener("click", () => {
  sqlInput.value = "";
  updateLineNumbers();
  hideAiMessage();
  displayResults([]);
});

// =============================================================================
// Initialize
// =============================================================================

updateLineNumbers();
checkConnection();
setInterval(checkConnection, 30000);

console.log("🗃️ CASS Frontend loaded (Chartbrew-style)");

btnConnection.addEventListener("click", () => {
  const token = window.prompt("API access token (leave blank for explicitly enabled local development)");
  if (token !== null) { setApiToken(token); checkConnection(); }
});
