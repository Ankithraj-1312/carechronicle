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
  });
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

// Helper: Typewriter effect
async function typeText(text, container) {
  // Enhanced Markdown-to-HTML parser
  let formattedText = text
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:1.05rem;font-weight:700;margin:0.5em 0 0.25em;color:var(--accent-primary);">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size:1.15rem;font-weight:800;margin:0.5em 0 0.25em;">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:rgba(0,230,153,0.1);padding:1px 5px;border-radius:3px;font-family:var(--font-mono);font-size:0.85em;">$1</code>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid var(--border-color);margin:0.75em 0;">')
    .replace(/^\d+\. (.+)$/gm, '<li style="margin-left:1.25em;list-style:decimal;">$1</li>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
  
  // Word-by-word typing
  const words = formattedText.split(' ');
  for (let i = 0; i < words.length; i++) {
    container.innerHTML += words[i] + ' ';
    await delay(22); // slightly faster type speed
  }
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

// Boot
window.onload = init;
