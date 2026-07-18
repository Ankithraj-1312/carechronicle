const byId = (id) => document.getElementById(id);

// App State
let currentPatientId = 'patient-001';
let patientsList = [];

// DOM Elements
const patientSelect = byId('patient-select');
const patientName = byId('patient-name');
const patientIdLabel = byId('patient-id-label');
const patientAvatar = byId('patient-avatar');
const patientConditions = byId('patient-conditions');
const patientMedications = byId('patient-medications');
const patientTests = byId('patient-tests');
const timeline = byId('timeline');
const suggestionsBox = byId('suggestions-box');
const queryInput = byId('query');
const askButton = byId('ask-button');
const answerContainer = byId('answer-container');
const answerContent = byId('answer');
const safetyCard = byId('safety-card');
const safetyText = byId('safety-text');
const sourcesWrapper = byId('sources-wrapper');
const sourcesList = byId('sources-list');
const refreshButton = byId('refresh-button');
const dropZone = byId('drop-zone');
const filePicker = byId('file-picker');
const filenameInput = byId('filename');

// Modal Elements
const recordModal = byId('record-modal');
const modalTitle = byId('modal-title');
const modalCode = byId('modal-code');
const closeModal = byId('close-modal');

// New Patient Modal Elements
const newPatientModal = byId('new-patient-modal');
const newPatientBtn = byId('new-patient-btn');
const closeNewPatientModal = byId('close-new-patient-modal');
const newPatientName = byId('new-patient-name');
const newPatientStatus = byId('new-patient-status');
const createPatientBtn = byId('create-patient-btn');
const deletePatientBtn = byId('delete-patient-btn');



// Initial setup
async function init() {
  await loadPatients();
  setupEventListeners();
}

// Event Listeners
function setupEventListeners() {
  // Patient Selector Change
  patientSelect.addEventListener('change', (e) => {
    currentPatientId = e.target.value;
    loadPatientDashboard();
  });

  // Query Ask button
  askButton.addEventListener('click', askQuestion);
  queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') askQuestion();
  });

  // Refresh Timeline
  refreshButton.addEventListener('click', () => {
    loadPatientDashboard(true);
  });

  // Drag and Drop files
  dropZone.addEventListener('click', () => filePicker.click());
  filePicker.addEventListener('change', handleFileSelect);

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      processIngestedFile(files[0]);
    }
  });

  // Modal close
  closeModal.addEventListener('click', () => {
    recordModal.style.display = 'none';
  });
  window.addEventListener('click', (e) => {
    if (e.target === recordModal) {
      recordModal.style.display = 'none';
    }
    if (e.target === newPatientModal) {
      newPatientModal.style.display = 'none';
    }
  });

  // New Patient Listeners
  newPatientBtn.addEventListener('click', () => {
    newPatientModal.style.display = 'flex';
    newPatientName.focus();
  });
  closeNewPatientModal.addEventListener('click', () => {
    newPatientModal.style.display = 'none';
  });
  createPatientBtn.addEventListener('click', registerNewPatient);
  newPatientName.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') registerNewPatient();
  });
  deletePatientBtn.addEventListener('click', deleteCurrentPatient);
}



// Load Patients List from Server
async function loadPatients() {
  try {
    const res = await fetch('/api/patients');
    const data = await res.json();
    patientsList = data.patients || [];
    
    patientSelect.innerHTML = patientsList.map(p => 
      `<option value="${p.id}">${p.name} (${p.id})</option>`
    ).join('');

    if (patientsList.length > 0) {
      currentPatientId = patientsList[0].id;
      loadPatientDashboard();
    }
  } catch (err) {
    console.error('Failed to load patients list:', err);
  }
}

// Load dynamic suggestions based on patient selection
function populateSuggestions() {
  let suggestions = [];
  if (currentPatientId === 'patient-001') {
    suggestions = [
      "What was my latest hemoglobin result?",
      "When was paracetamol recorded?",
      "Show my discharge summary details"
    ];
  } else if (currentPatientId === 'patient-002') {
    suggestions = [
      "What is my fasting glucose level?",
      "Show my metformin prescription schedule",
      "List medications prescribed by Dr. Patel"
    ];
  } else {
    suggestions = [
      "Show my recent lab records",
      "Which medications am I taking?",
      "Summarize patient timeline"
    ];
  }

  suggestionsBox.innerHTML = suggestions.map(q => 
    `<button data-question="${q}">${q.split(' ').slice(0, 3).join(' ')}...</button>`
  ).join('');

  // Add click listeners to suggestions
  suggestionsBox.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.dataset.question;
      askQuestion();
    });
  });
}

// Load Patient Profile Dashboard
async function loadPatientDashboard(silent = false) {
  if (!silent) {
    patientName.textContent = 'Loading...';
    patientIdLabel.textContent = `ID: ${currentPatientId}`;
    patientAvatar.textContent = '..';
    patientConditions.innerHTML = '<li>Loading...</li>';
    patientMedications.innerHTML = '<li>Loading...</li>';
    patientTests.innerHTML = '<li>Loading...</li>';
    timeline.innerHTML = '<p style="padding: 20px; text-align:center; color:var(--text-muted);">Indexing timeline records...</p>';
  }

  try {
    const res = await fetch(`/api/profile?patientId=${currentPatientId}`);
    const profile = await res.json();
    
    // Update Sidebar
    patientName.textContent = profile.name;
    patientIdLabel.textContent = `ID: ${profile.patientId}`;
    
    // Initials for avatar
    const initials = profile.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    patientAvatar.textContent = initials;

    // Conditions
    patientConditions.innerHTML = profile.conditions.map(c => `<li>${escapeHtml(c)}</li>`).join('');

    // Medications
    patientMedications.innerHTML = profile.medications.length 
      ? profile.medications.map(m => `<li><strong>${escapeHtml(m.name)}</strong><br><span style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(m.detail)}</span></li>`).join('')
      : '<li>No active medications</li>';

    // Tests
    patientTests.innerHTML = profile.tests.length 
      ? profile.tests.map(t => `<li><strong>${escapeHtml(t.name)}</strong>: ${escapeHtml(t.value)}<br><span style="font-size:0.7rem; color:var(--text-muted);">${escapeHtml(t.date)}</span></li>`).join('')
      : '<li>No diagnostic tests recorded</li>';

    // Timeline
    renderTimeline(profile.timeline);

    // Suggestions
    populateSuggestions();
  } catch (err) {
    console.error('Failed to load patient profile:', err);
  }
}

// Render Timeline
function renderTimeline(timelineEvents) {
  if (!timelineEvents || timelineEvents.length === 0) {
    timeline.innerHTML = '<p style="padding: 20px; text-align:center; color:var(--text-muted);">No medical records in patient repository.</p>';
    return;
  }

  timeline.innerHTML = timelineEvents.map(event => {
    return `
      <div class="timeline-item ${escapeHtml(event.type)}">
        <div class="timeline-dot"></div>
        <div class="timeline-date">${escapeHtml(event.date)}</div>
        <div class="timeline-card">
          <div class="timeline-card-content">
            <h4>${escapeHtml(event.title)}</h4>
            <p>${escapeHtml(event.excerpt)}</p>
            <div class="timeline-meta">
              <span>ID: ${escapeHtml(event.id)}</span>
              ${event.hospital ? `<span>Facility: ${escapeHtml(event.hospital)}</span>` : ''}
              ${event.doctor ? `<span>MD: ${escapeHtml(event.doctor)}</span>` : ''}
            </div>
          </div>
          <div class="timeline-card-action">
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.7rem;" onclick="viewRecordRaw('${escapeHtml(event.id)}')">
              Preview OKF
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// View Raw Record in Modal
async function viewRecordRaw(recordId) {
  try {
    const res = await fetch(`/api/records?patientId=${currentPatientId}`);
    const data = await res.json();
    const records = data.records || [];
    
    // Find record by ID (wait, we need to fetch the full markdown, let's look for matching record file)
    const matchedRecord = records.find(r => r.meta.id === recordId);
    
    if (matchedRecord) {
      // Reconstruct the markdown from meta and body:
      const frontmatter = Object.entries(matchedRecord.meta)
        .map(([key, val]) => Array.isArray(val) ? `${key}:\n${val.map(v => `  - ${v}`).join('\n')}` : `${key}: "${val}"`)
        .join('\n');
      
      const fullMarkdown = `---\n${frontmatter}\n---\n\n${matchedRecord.body}`;
      
      modalTitle.textContent = `OKF Markdown: ${matchedRecord.meta.id}`;
      modalCode.textContent = fullMarkdown;
      recordModal.style.display = 'flex';
    }
  } catch (err) {
    console.error('Error previewing record:', err);
  }
}
window.viewRecordRaw = viewRecordRaw; // Make it global so inline onclick works

// Handle File Selection
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) {
    processIngestedFile(file);
  }
}

// Process Ingested File with beautiful simulated animations
async function processIngestedFile(file) {
  filenameInput.value = file.name;
  
  const stepOcr = byId('step-ocr');
  const stepOkf = byId('step-okf');
  const stepDb = byId('step-db');
  const ingestSteps = byId('ingest-steps');
  const statusMsg = byId('convert-status');
  
  // Show steps
  ingestSteps.style.display = 'flex';
  statusMsg.textContent = '';
  
  // Set all to waiting
  [stepOcr, stepOkf, stepDb].forEach(el => {
    el.className = 'step-item';
    el.querySelector('.step-spinner').style.display = 'inline-block';
  });

  try {
    // Convert file to Base64
    const base64 = await fileToBase64(file);

    // Step 1: Ingest & Extract
    stepOcr.classList.add('active');
    await delay(1200);
    stepOcr.classList.remove('active');
    stepOcr.classList.add('success');

    // Step 2: OKF Conversion
    stepOkf.classList.add('active');
    await delay(1000);
    stepOkf.classList.remove('active');
    stepOkf.classList.add('success');

    // Step 3: DB Indexing
    stepDb.classList.add('active');
    
    // Perform API call
    const response = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        content: base64,
        patientId: currentPatientId
      })
    });

    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Server error during upload');
    }

    await delay(600);
    stepDb.classList.remove('active');
    stepDb.classList.add('success');

    statusMsg.textContent = `✓ Ingested successfully. Record ID: ${data.id}`;
    loadPatientDashboard(true); // reload without full page spinner
    
    // Hide steps after brief delay
    setTimeout(() => {
      ingestSteps.style.display = 'none';
      filenameInput.value = '';
    }, 4000);
  } catch (err) {
    statusMsg.textContent = `✖ Ingestion failed: ${err.message}`;
    // Reset steps
    [stepOcr, stepOkf, stepDb].forEach(el => {
      el.className = 'step-item';
    });
  }
}

// Ask Question with LLM retrieval and typing effect
async function askQuestion() {
  const query = queryInput.value.trim();
  if (!query) return;

  answerContainer.className = 'answer-box';
  answerContent.innerHTML = '<span class="step-spinner"></span> Retrieving relevant OKF records through MCP & query planning...';
  safetyCard.style.display = 'none';
  sourcesWrapper.style.display = 'none';

  try {
    const response = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, patientId: currentPatientId })
    });
    
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Server failed to return response');
    }

    // Typing effect for the answer
    answerContent.innerHTML = '';
    await typeText(data.answer, answerContent);

    // Show safety disclaimer
    safetyText.textContent = data.safety;
    safetyCard.style.display = 'flex';

    // Show Citations
    if (data.sources && data.sources.length > 0) {
      sourcesList.innerHTML = data.sources.map(src => {
        return `
          <li>
            <div>
              <a onclick="viewRecordRaw('${escapeHtml(src.id)}')">${escapeHtml(src.id)}</a>
              <div class="source-meta">File: ${escapeHtml(src.source)} · Date: ${escapeHtml(src.date)}</div>
            </div>
            <span style="font-size:0.7rem; color:var(--text-muted); font-style:italic;">"${escapeHtml(src.excerpt)}"</span>
          </li>
        `;
      }).join('');
      sourcesWrapper.style.display = 'block';
    }
  } catch (err) {
    answerContent.innerHTML = `<span style="color:var(--text-danger)">Error: ${escapeHtml(err.message)}</span>`;
  }
}

// Helper: Convert File to Base64
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      const base64String = reader.result.split(',')[1];
      resolve(base64String);
    };
    reader.onerror = error => reject(error);
  });
}

// Helper: Simulates delay
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Helper: Convert markdown string to clean HTML
function markdownToHtml(text) {
  const lines = text.split('\n');
  const result = [];
  let inUl = false;
  let inOl = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // Close lists if current line is not a list item
    const isUlItem = /^[-*] (.+)$/.test(line);
    const isOlItem = /^\d+\. (.+)$/.test(line);

    if (inUl && !isUlItem) { result.push('</ul>'); inUl = false; }
    if (inOl && !isOlItem) { result.push('</ol>'); inOl = false; }

    // Headers
    if (/^#### (.+)$/.test(line)) {
      result.push(`<h4 class="md-h4">${line.replace(/^#### /, '')}</h4>`);
    } else if (/^### (.+)$/.test(line)) {
      result.push(`<h3 class="md-h3">${line.replace(/^### /, '')}</h3>`);
    } else if (/^## (.+)$/.test(line)) {
      result.push(`<h2 class="md-h2">${line.replace(/^## /, '')}</h2>`);
    } else if (/^# (.+)$/.test(line)) {
      result.push(`<h1 class="md-h1">${line.replace(/^# /, '')}</h1>`);
    // Horizontal rule
    } else if (/^---$/.test(line.trim())) {
      result.push('<hr class="md-hr">');
    // Unordered list
    } else if (isUlItem) {
      if (!inUl) { result.push('<ul class="md-ul">'); inUl = true; }
      result.push(`<li>${line.replace(/^[-*] /, '')}</li>`);
    // Ordered list
    } else if (isOlItem) {
      if (!inOl) { result.push('<ol class="md-ol">'); inOl = true; }
      result.push(`<li>${line.replace(/^\d+\. /, '')}</li>`);
    // Blank line
    } else if (line.trim() === '') {
      result.push('<div class="md-spacer"></div>');
    // Normal paragraph line
    } else {
      result.push(`<p class="md-p">${line}</p>`);
    }
  }

  // Close any open lists
  if (inUl) result.push('</ul>');
  if (inOl) result.push('</ol>');

  // Join and apply inline formatting
  return result.join('\n')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '<span class="md-cite">[$1]</span>');
}

// Helper: Render answer with smooth reveal animation
async function typeText(text, container) {
  const html = markdownToHtml(text);
  container.innerHTML = `<div class="answer-reveal">${html}</div>`;
}


// Helper: Escape HTML strings
function escapeHtml(unsafe) {
  if (unsafe === undefined || unsafe === null) return '';
  return String(unsafe)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Register New Patient
async function registerNewPatient() {
  const name = newPatientName.value.trim();
  if (!name) {
    newPatientStatus.textContent = "✖ Please enter a patient name.";
    newPatientStatus.style.color = "var(--text-danger)";
    return;
  }

  newPatientStatus.textContent = "Registering patient...";
  newPatientStatus.style.color = "var(--text-muted)";
  createPatientBtn.disabled = true;

  try {
    const res = await fetch('/api/patients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.error || 'Failed to register patient');
    }

    newPatientStatus.textContent = "✓ Registered successfully!";
    newPatientStatus.style.color = "var(--text-safe)";
    newPatientName.value = "";

    // Reload patients dropdown list
    await loadPatients();

    // Select the new patient automatically
    currentPatientId = data.id;
    patientSelect.value = data.id;
    await loadPatientDashboard();

    setTimeout(() => {
      newPatientModal.style.display = 'none';
      newPatientStatus.textContent = "";
      createPatientBtn.disabled = false;
    }, 800);

  } catch (err) {
    newPatientStatus.textContent = `✖ Error: ${err.message}`;
    newPatientStatus.style.color = "var(--text-danger)";
    createPatientBtn.disabled = false;
  }
}

// Delete Current Patient
async function deleteCurrentPatient() {
  const patientNameText = patientName.textContent;
  const confirmDelete = confirm(`Are you sure you want to delete patient "${patientNameText}" and all of their ingested medical records? This action cannot be undone.`);
  
  if (!confirmDelete) return;

  try {
    const res = await fetch(`/api/patients?patientId=${currentPatientId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.error || 'Failed to delete patient');
    }
    
    alert(`Successfully deleted patient profile: ${patientNameText}`);
    
    // Reload patient registry list
    await loadPatients();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// Boot
window.onload = init;


