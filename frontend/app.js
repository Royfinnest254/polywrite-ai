// ============================================
// PolyWrite - Frontend Application
// ============================================

// Use relative path for production, localhost for local dev if needed
// Vercel serves both frontend and backend on same domain
const API_BASE = '';

// State
let authToken = localStorage.getItem('polywrite_token');
let currentUser = null;
let isSignUp = false;

// DOM Elements
const elements = {
    // Auth
    authBtn: document.getElementById('authBtn'),
    authModal: document.getElementById('authModal'),
    authForm: document.getElementById('authForm'),
    modalTitle: document.getElementById('modalTitle'),
    authSubmitBtn: document.getElementById('authSubmitBtn'),
    authSwitchText: document.getElementById('authSwitchText'),
    authSwitchLink: document.getElementById('authSwitchLink'),
    userEmail: document.getElementById('userEmail'),

    // Editor
    originalText: document.getElementById('originalText'),
    charCount: document.getElementById('charCount'),
    processBtn: document.getElementById('processBtn'),
    proposalOutput: document.getElementById('proposalOutput'),
    statusBadge: document.getElementById('statusBadge'),
    validationResults: document.getElementById('validationResults'),

    // Validation displays
    similarityValue: document.getElementById('similarityValue'),
    similarityBar: document.getElementById('similarityBar'),
    entityValue: document.getElementById('entityValue'),
    polarityValue: document.getElementById('polarityValue'),
    toneValue: document.getElementById('toneValue'),
    validationFlags: document.getElementById('validationFlags'),
    decisionBox: document.getElementById('decisionBox'),
    decisionValue: document.getElementById('decisionValue'),
    decisionReason: document.getElementById('decisionReason'),

    // Tabs
    navBtns: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),

    // Toast
    toastContainer: document.getElementById('toastContainer')
};

// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initEditor();
    initAuth();

    if (authToken) {
        checkAuth();
    }
});

// ============================================
// Tab Navigation
// ============================================

function initTabs() {
    elements.navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Update buttons
            elements.navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content
            elements.tabContents.forEach(tab => {
                tab.classList.remove('active');
                if (tab.id === `${tabId}-tab`) {
                    tab.classList.add('active');
                }
            });
        });
    });
}

// ============================================
// Editor
// ============================================

function initEditor() {
    // Character count
    elements.originalText.addEventListener('input', () => {
        const count = elements.originalText.value.length;
        elements.charCount.textContent = count;

        if (count > 1800) {
            elements.charCount.style.color = 'var(--danger)';
        } else if (count >= 20) {
            elements.charCount.style.color = 'var(--success)';
        } else {
            elements.charCount.style.color = 'var(--text-muted)';
        }
    });

    // Process button
    elements.processBtn.addEventListener('click', processText);
}

async function processText() {
    const text = elements.originalText.value.trim();
    const intent = document.querySelector('input[name="intent"]:checked').value;

    // Validation
    if (text.length < 20) {
        showToast('Text must be at least 20 characters', 'error');
        return;
    }

    if (text.length > 1800) {
        showToast('Text must be less than 1800 characters', 'error');
        return;
    }

    if (!authToken) {
        showToast('Please sign in to use PolyWrite', 'warning');
        openModal();
        return;
    }

    // Update UI
    setStatus('processing', 'Processing');
    elements.processBtn.disabled = true;
    elements.proposalOutput.innerHTML = '<div class="empty-state"><div class="empty-icon">⏳</div><p>Processing your text...</p></div>';

    try {
        const response = await fetch(`${API_BASE}/api/rewrite`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                selected_text: text,
                intent: intent
            })
        });

        if (response.status === 401) {
            authToken = null;
            localStorage.removeItem('polywrite_token');
            updateAuthUI();
            showToast('Session expired. Please sign in again.', 'error');
            return;
        }

        if (response.status === 429) {
            const error = await response.json();
            showToast(`Rate limit exceeded. Try again in ${error.detail.retry_after_seconds || 60}s`, 'error');
            setStatus('ready', 'Ready');
            return;
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }

        const result = await response.json();
        displayResult(result);

    } catch (error) {
        showToast(error.message, 'error');
        setStatus('ready', 'Ready');
        elements.proposalOutput.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><p>${error.message}</p></div>`;
    } finally {
        elements.processBtn.disabled = false;
    }
}

function displayResult(result) {
    // Set status based on decision
    if (result.decision === 'allowed') {
        setStatus('allowed', 'Allowed');
    } else if (result.decision === 'blocked') {
        setStatus('blocked', 'Blocked');
    } else {
        setStatus('warning', 'Warning');
    }

    // Display proposed text
    elements.proposalOutput.innerHTML = `
        <div class="proposal-text">${escapeHtml(result.proposed_text)}</div>
        <div class="proposal-explanation">
            <strong>AI Explanation:</strong> ${escapeHtml(result.explanation_summary)}
        </div>
    `;

    // Show validation results
    elements.validationResults.style.display = 'block';

    // Similarity
    const similarity = (result.similarity_score * 100).toFixed(1);
    elements.similarityValue.textContent = `${similarity}%`;
    elements.similarityBar.style.width = `${similarity}%`;

    if (result.similarity_score >= 0.85) {
        elements.similarityValue.className = 'validation-value success';
    } else if (result.similarity_score >= 0.60) {
        elements.similarityValue.className = 'validation-value warning';
    } else {
        elements.similarityValue.className = 'validation-value danger';
    }

    // Entity preservation
    const entityPreserved = result.entity_preserved !== false;
    elements.entityValue.textContent = entityPreserved ? '✓ OK' : '✗ Changed';
    elements.entityValue.className = `validation-value ${entityPreserved ? 'success' : 'danger'}`;

    // Polarity
    const polarityOk = !result.polarity_flip;
    elements.polarityValue.textContent = polarityOk ? '✓ OK' : '✗ Flipped';
    elements.polarityValue.className = `validation-value ${polarityOk ? 'success' : 'danger'}`;

    // Tone
    if (result.tone_analysis) {
        const toneOk = result.tone_analysis.preserved !== false;
        elements.toneValue.textContent = toneOk ? '✓ OK' : '⚠ Shifted';
        elements.toneValue.className = `validation-value ${toneOk ? 'success' : 'warning'}`;
    } else {
        elements.toneValue.textContent = '--';
        elements.toneValue.className = 'validation-value';
    }

    // Validation flags
    elements.validationFlags.innerHTML = '';
    if (result.validation_flags && result.validation_flags.length > 0) {
        result.validation_flags.forEach(flag => {
            const flagEl = document.createElement('span');
            flagEl.className = 'validation-flag';
            flagEl.textContent = `⚠ ${flag}`;
            elements.validationFlags.appendChild(flagEl);
        });
    }

    // Decision
    elements.decisionBox.className = `decision-box ${result.decision === 'allowed' ? 'allowed' : result.decision === 'blocked' ? 'blocked' : 'warning'}`;
    elements.decisionValue.textContent = result.decision.replace('_', ' ');
    elements.decisionReason.textContent = result.decision_reason;
}

function setStatus(type, text) {
    elements.statusBadge.className = `status-badge ${type}`;
    elements.statusBadge.textContent = text;
}

// ============================================
// Authentication
// ============================================

function initAuth() {
    elements.authBtn.addEventListener('click', () => {
        if (authToken) {
            logout();
        } else {
            openModal();
        }
    });

    elements.authForm.addEventListener('submit', handleAuth);
}

function openModal() {
    elements.authModal.classList.add('active');
}

function closeModal() {
    elements.authModal.classList.remove('active');
}

function toggleAuthMode(e) {
    e.preventDefault();
    isSignUp = !isSignUp;

    elements.modalTitle.textContent = isSignUp ? 'Sign Up' : 'Sign In';
    elements.authSubmitBtn.textContent = isSignUp ? 'Sign Up' : 'Sign In';
    elements.authSwitchText.textContent = isSignUp ? 'Already have an account?' : "Don't have an account?";
    elements.authSwitchLink.textContent = isSignUp ? 'Sign In' : 'Sign Up';
}

async function handleAuth(e) {
    e.preventDefault();

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    const endpoint = isSignUp ? '/auth/signup' : '/auth/signin';

    try {
        elements.authSubmitBtn.disabled = true;
        elements.authSubmitBtn.textContent = 'Loading...';

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Authentication failed');
        }

        if (isSignUp) {
            showToast('Account created! Please sign in.', 'success');
            isSignUp = false;
            toggleAuthMode({ preventDefault: () => { } });
        } else {
            authToken = data.access_token;
            localStorage.setItem('polywrite_token', authToken);
            currentUser = data.user;
            updateAuthUI();
            closeModal();
            showToast('Signed in successfully!', 'success');
        }

    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.authSubmitBtn.disabled = false;
        elements.authSubmitBtn.textContent = isSignUp ? 'Sign Up' : 'Sign In';
    }
}

async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (response.ok) {
            currentUser = await response.json();
            updateAuthUI();
        } else {
            authToken = null;
            localStorage.removeItem('polywrite_token');
            updateAuthUI();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('polywrite_token');
    updateAuthUI();
    showToast('Signed out', 'success');
}

function updateAuthUI() {
    if (authToken && currentUser) {
        elements.userEmail.textContent = currentUser.email;
        elements.authBtn.textContent = 'Sign Out';
    } else {
        elements.userEmail.textContent = 'Not logged in';
        elements.authBtn.textContent = 'Sign In';
    }
}

// ============================================
// Validator Tests (Client-side simulation)
// ============================================

function testEntityValidator() {
    const original = document.getElementById('entityOriginal').value;
    const proposed = document.getElementById('entityProposed').value;
    const resultEl = document.getElementById('entityResult');

    if (!original || !proposed) {
        resultEl.textContent = 'Please enter both original and proposed text';
        return;
    }

    // Client-side entity extraction (simplified)
    const extractEntities = (text) => {
        const numbers = text.match(/\d+(?:\.\d+)?%?/g) || [];
        const years = text.match(/\b(?:19|20)\d{2}\b/g) || [];
        return { numbers, years };
    };

    const origEntities = extractEntities(original);
    const propEntities = extractEntities(proposed);

    const result = {
        original_entities: origEntities,
        proposed_entities: propEntities,
        preserved: JSON.stringify(origEntities) === JSON.stringify(propEntities)
    };

    resultEl.textContent = JSON.stringify(result, null, 2);
}

function testPolarityDetector() {
    const original = document.getElementById('polarityOriginal').value;
    const proposed = document.getElementById('polarityProposed').value;
    const resultEl = document.getElementById('polarityResult');

    if (!original || !proposed) {
        resultEl.textContent = 'Please enter both original and proposed text';
        return;
    }

    const negationWords = ['not', 'no', 'never', 'neither', 'nor', 'none', "n't", "cannot"];

    const hasNegation = (text) => {
        const lower = text.toLowerCase();
        return negationWords.some(word => lower.includes(word));
    };

    const origNegated = hasNegation(original);
    const propNegated = hasNegation(proposed);
    const polarityFlip = origNegated !== propNegated;

    const result = {
        original_negated: origNegated,
        proposed_negated: propNegated,
        polarity_flip: polarityFlip,
        status: polarityFlip ? '⚠️ POLARITY REVERSED' : '✓ Polarity preserved'
    };

    resultEl.textContent = JSON.stringify(result, null, 2);
}

function testClaimValidator() {
    const text = document.getElementById('claimText').value;
    const resultEl = document.getElementById('claimResult');

    if (!text) {
        resultEl.textContent = 'Please enter text to analyze';
        return;
    }

    const claims = [];

    // Statistics
    if (/\d+(?:\.\d+)?%/.test(text)) {
        claims.push({ type: 'statistic', text: 'Contains percentage' });
    }

    // Causation
    if (/\b(causes?|leads?\s+to|results?\s+in)\b/i.test(text)) {
        claims.push({ type: 'causation', text: 'Contains causal claim' });
    }

    // Authority
    if (/\b(studies?\s+show|research\s+indicates?|experts?\s+say)\b/i.test(text)) {
        claims.push({ type: 'authority', text: 'Contains authority claim' });
    }

    // Citations
    const citations = text.match(/\([A-Z][a-z]+,?\s*\d{4}\)|\[\d+\]/g) || [];

    const result = {
        claims_detected: claims.length,
        claims: claims,
        citations_found: citations.length,
        citations: citations,
        needs_review: claims.length > 0 && citations.length === 0
    };

    resultEl.textContent = JSON.stringify(result, null, 2);
}

function testToneAnalyzer() {
    const original = document.getElementById('toneOriginal').value;
    const proposed = document.getElementById('toneProposed').value;
    const resultEl = document.getElementById('toneResult');

    if (!original || !proposed) {
        resultEl.textContent = 'Please enter both original and proposed text';
        return;
    }

    const analyzeTone = (text) => {
        const lower = text.toLowerCase();

        const formalWords = ['therefore', 'furthermore', 'hereby', 'pursuant'];
        const casualWords = ['gonna', 'wanna', 'kinda', 'yeah', 'ok'];

        const formalCount = formalWords.filter(w => lower.includes(w)).length;
        const casualCount = casualWords.filter(w => lower.includes(w)).length;
        const contractions = (text.match(/n't|'ll|'ve|'re|'d/g) || []).length;

        let tone = 'neutral';
        if (formalCount > 0) tone = 'formal';
        if (casualCount > 0 || contractions > 2) tone = 'casual';

        return { tone, formal: formalCount, casual: casualCount + contractions };
    };

    const origTone = analyzeTone(original);
    const propTone = analyzeTone(proposed);

    const result = {
        original_tone: origTone,
        proposed_tone: propTone,
        tone_preserved: origTone.tone === propTone.tone,
        status: origTone.tone === propTone.tone ? '✓ Tone preserved' : `⚠️ Tone shifted: ${origTone.tone} → ${propTone.tone}`
    };

    resultEl.textContent = JSON.stringify(result, null, 2);
}

function testDocumentScanner() {
    const text = document.getElementById('documentText').value;
    const resultEl = document.getElementById('documentResult');

    if (!text || text.length < 50) {
        resultEl.textContent = 'Please enter at least 50 characters';
        return;
    }

    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 10);
    const words = text.split(/\s+/).length;

    const analysis = {
        sentence_count: sentences.length,
        word_count: words,
        avg_sentence_length: Math.round(words / sentences.length),
        issues: []
    };

    // Check for long sentences
    sentences.forEach((s, i) => {
        if (s.split(/\s+/).length > 40) {
            analysis.issues.push(`Sentence ${i + 1}: Too long (${s.split(/\s+/).length} words)`);
        }
    });

    // Check for passive voice
    const passiveCount = (text.match(/\b(is|are|was|were|been|being)\s+\w+ed\b/g) || []).length;
    if (passiveCount > 2) {
        analysis.issues.push(`Excessive passive voice (${passiveCount} instances)`);
    }

    // Check for logical connectors
    const connectors = (text.match(/\b(therefore|however|furthermore|moreover)\b/gi) || []).length;
    if (connectors > 0) {
        analysis.strengths = [`Good use of logical connectors (${connectors})`];
    }

    const score = 100 - (analysis.issues.length * 10);
    analysis.overall_score = Math.max(0, score) + '%';

    resultEl.textContent = JSON.stringify(analysis, null, 2);
}

// ============================================
// Audit Log
// ============================================

async function loadAuditLogs() {
    if (!authToken) {
        showToast('Please sign in to view audit logs', 'warning');
        return;
    }

    const tbody = document.getElementById('auditTableBody');
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Loading...</td></tr>';

    try {
        const response = await fetch(`${API_BASE}/api/audit-logs?limit=50`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (!response.ok) throw new Error('Failed to load logs');

        const logs = await response.json();

        if (logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">No audit logs yet</td></tr>';
            return;
        }

        tbody.innerHTML = logs.map(log => `
            <tr>
                <td>${new Date(log.created_at).toLocaleString()}</td>
                <td>${log.action_type || 'rewrite'}</td>
                <td>${(log.similarity_score * 100).toFixed(1)}%</td>
                <td><span class="status-badge ${log.risk_label}">${log.risk_label}</span></td>
                <td><span class="status-badge ${log.decision}">${log.decision}</span></td>
            </tr>
        `).join('');

    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-cell">${error.message}</td></tr>`;
    }
}

// ============================================
// Utilities
// ============================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal on outside click
elements.authModal.addEventListener('click', (e) => {
    if (e.target === elements.authModal) {
        closeModal();
    }
});

// Escape key closes modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && elements.authModal.classList.contains('active')) {
        closeModal();
    }
});
