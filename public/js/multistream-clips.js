// Enhanced Multistream Clip Integration
// Auto-link clips to streamers and Medal.tv import functionality

// --- NEW FUNCTION TO HIDE SIDEBAR BUTTONS ---
/**
 * @description Finds and hides the original, duplicate clip-related buttons in the main sidebar.
 * It uses a MutationObserver to handle dynamically loaded content, ensuring the buttons
 * stay hidden even in a single-page application. This prevents duplicate controls from showing.
 */
function hideSidebarClipButtons() {
    const normalizeText = (value) => {
        try {
            return (value || '')
                .toLowerCase()
                .replace(/[\u{1F300}-\u{1FAFF}]/gu, '') // strip emojis
                .replace(/[^a-z0-9\s\.]/g, ' ') // keep alnum and dots
                .replace(/medal\.tv/g, 'medal')
                .replace(/\s+/g, ' ')
                .trim();
        } catch (_) {
            return '';
        }
    };

    const shouldHideByText = (element) => {
        const candidates = [
            element.textContent,
            element.innerText,
            element.getAttribute('aria-label'),
            element.getAttribute('title')
        ];
        for (const raw of candidates) {
            const t = normalizeText(raw);
            if (!t) continue;
            if (t.includes('create clip') || t.includes('import medal') || t.includes('my clips')) {
                return true;
            }
        }
        return false;
    };

    const hideLogic = () => {
        // 1) Check obvious interactive elements
        const primary = document.querySelectorAll('button, a, [role="button"], [onclick], .btn, .button, [class*="btn" i]');
        // 2) Fallback: scan small set of generic elements that often hold label-only buttons
        const secondary = document.querySelectorAll('span, div');
        const elements = [...primary, ...secondary];

        elements.forEach((el) => {
            if (el.closest('.multistream-clip-controls')) return; // keep our injected controls
            if (el.closest('.medal-import-modal')) return; // keep modal elements
            if (el.closest('.my-clips-modal')) return; // keep modal elements
            if (el.closest('.streamer-clips-modal')) return; // keep modal elements
            if (el.closest('.modal-overlay')) return; // keep modal overlays
            if (el.closest('.modal-content')) return; // keep modal content
            if (el.dataset.hiddenByMultistream === '1') return; // already handled

            const computed = window.getComputedStyle(el);
            const looksClickable = ['pointer'].includes(computed.cursor) || el.hasAttribute('onclick') || el.tagName === 'A' || el.tagName === 'BUTTON' || el.getAttribute('role') === 'button';

            if (looksClickable && shouldHideByText(el)) {
                el.style.setProperty('display', 'none', 'important');
                el.dataset.hiddenByMultistream = '1';
            }
        });
    };

    // Run once and observe dynamic changes
    hideLogic();
    const observer = new MutationObserver(() => {
        // Debounce microtasks
        clearTimeout(observer._t);
        observer._t = setTimeout(hideLogic, 50);
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true });
}

// Enhanced clip creation function
async function createClipForStreamer(streamerUsername, userId = null) {
    try {
        // Show loading state
        showClipLoading(streamerUsername);
        
        // Create the Twitch clip
        const response = await fetch(`/api/stream-clips/create/${streamerUsername}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getUserToken()}` // If using auth
            },
            body: JSON.stringify({
                broadcaster_login: streamerUsername,
                created_by_user_id: userId,
                creator_login: getCurrentUsername() // Get from session/auth
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Show success with easy access links
            showClipSuccess(result.data, streamerUsername);
        } else {
            showClipError(result.error);
        }
        
    } catch (error) {
        showClipError('Failed to create clip');
    }
}

// Success notification with easy access
function showClipSuccess(clipData, streamerName) {
    removeExistingNotifications();
    
    const notification = document.createElement('div');
    notification.className = 'clip-success-notification';
    notification.innerHTML = `
        <div class="clip-notification">
            <h4>✅ Clip Created!</h4>
            <p>Clip saved to <strong>${streamerName}</strong>'s highlights</p>
            
            <div class="clip-actions">
                <button onclick="window.open('${clipData.url}', '_blank')" class="btn-primary">
                    📺 Watch Clip
                </button>
                <button onclick="window.open('${clipData.edit_url}', '_blank')" class="btn-secondary">
                    ✂️ Edit Clip  
                </button>
                <button onclick="viewMyClips()" class="btn-outline">
                    📋 My Clips
                </button>
            </div>
            
            <div class="clip-info">
                <small>Clip ID: ${clipData.clip_id}</small>
            </div>
            
            <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 15 seconds
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.remove();
        }
    }, 15000);
}

// Medal.tv import functionality
function showMedalImportModal(currentStreamer) {
    // Remove any existing modal
    document.querySelector('.medal-import-modal')?.remove();
    
    const modal = document.createElement('div');
    modal.className = 'medal-import-modal modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h3>🏅 Import Medal.tv Clip</h3>
                <span class="close" onclick="closeMedalModal()">&times;</span>
            </div>
            <div class="modal-body">
                
                <form id="medalImportForm">
                    <div class="form-group">
                        <label>Medal.tv URL</label>
                        <input type="url" 
                               id="medalUrl" 
                               placeholder="https://medal.tv/clip/yourclipid"
                               required>
                        <small>Paste a Medal.tv clip URL to import</small>
                    </div>
                    
                    <div class="form-group">
                        <label>Link to Streamer</label>
                        <select id="streamerSelect" required>
                            <option value="${currentStreamer}" selected>
                                ${currentStreamer} (Currently Watching)
                            </option>
                            <option value="">Other Streamer...</option>
                        </select>
                    </div>
                    
                    <div class="form-group" id="customStreamerGroup" style="display: none;">
                        <label>Enter Streamer Name</label>
                        <input type="text" id="customStreamer" placeholder="streamer_name">
                    </div>
                    
                    <div class="form-actions">
                        <button type="submit" class="action-btn">
                            <span class="btn-text">Import Clip</span>
                            <span class="btn-loading" style="display: none;">Importing...</span>
                        </button>
                        <button type="button" onclick="closeMedalModal()" class="action-btn secondary">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Handle custom streamer selection
    document.getElementById('streamerSelect').addEventListener('change', (e) => {
        const customGroup = document.getElementById('customStreamerGroup');
        if (e.target.value === '') {
            customGroup.style.display = 'block';
            document.getElementById('customStreamer').focus();
        } else {
            customGroup.style.display = 'none';
        }
    });
    
    // Handle form submission
    document.getElementById('medalImportForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        await handleMedalImport(currentStreamer);
    });
    
    // Focus on URL input
    document.getElementById('medalUrl').focus();
}

async function handleMedalImport(currentStreamer) {
    const form = document.getElementById('medalImportForm');
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    
    // Show loading state
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    submitBtn.disabled = true;
    
    const medalUrl = document.getElementById('medalUrl').value;
    const streamerSelect = document.getElementById('streamerSelect').value;
    const customStreamer = document.getElementById('customStreamer').value;
    
    const targetStreamer = streamerSelect || customStreamer;
    
    try {
        const response = await fetch('/api/import-medal-clip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                medal_url: medalUrl,
                streamer_name: targetStreamer
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            closeMedalModal();
            showMedalImportSuccess(result.data, targetStreamer);
        } else {
            showError(result.error);
        }
    } catch (error) {
        showError('Failed to import Medal.tv clip');
    } finally {
        // Reset button state
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        submitBtn.disabled = false;
    }
}

function showMedalImportSuccess(clipData, streamerName) {
    removeExistingNotifications();
    
    const notification = document.createElement('div');
    notification.className = 'medal-success-notification';
    notification.innerHTML = `
        <div class="clip-notification medal-style">
            <h4>🏅 Medal.tv Clip Imported!</h4>
            <p><strong>"${clipData.clip.title}"</strong></p>
            <p>Linked to <strong>${streamerName}</strong></p>
            
            <div class="clip-actions">
                <button onclick="window.open('${clipData.clip.url}', '_blank')" class="btn-primary">
                    🎬 Watch on Medal.tv
                </button>
                <button onclick="viewStreamerClips('${streamerName}')" class="btn-outline">
                    📁 View ${streamerName}'s Clips
                </button>
            </div>
            
            <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.remove();
        }
    }, 12000);
}

// Main integration functions
function createClipForCurrentStream() {
    const currentStreamer = getCurrentStreamFocus();
    const userId = getCurrentUserId();
    
    if (!currentStreamer) {
        showError('Please select a stream to clip');
        return;
    }
    
    createClipForStreamer(currentStreamer, userId);
}

function openMedalImport() {
    const currentStreamer = getCurrentStreamFocus();
    
    if (!currentStreamer) {
        showError('Please select a stream first');
        return;
    }
    
    showMedalImportModal(currentStreamer);
}

function viewMyClips() {
    // Load user's clips in a modal
    showMyClipsModal();
}

function viewStreamerClips(streamerName) {
    // Show clips for specific streamer
    loadClipsForStreamer(streamerName);
}

// Helper functions
function getCurrentStreamFocus() {
    // Try multiple methods to get current focused stream
    const focused = document.querySelector('.stream-focused, .stream-selected, [data-selected="true"]');
    if (focused) {
        return focused.dataset.username || focused.dataset.streamer;
    }
    
    // Check multistream dropdowns for selected streamers (thy specific IDs)
    const streamSelects = ['streamer1', 'streamer2', 'streamer3'];
    for (const selectId of streamSelects) {
        const select = document.getElementById(selectId);
        if (select && select.value && select.value !== '' && select.value !== 'none') {
            return select.value;
        }
    }
    
    // Check any select with streamSelect in ID
    const streamSelectElements = document.querySelectorAll('select[id*="stream"]');
    for (const select of streamSelectElements) {
        if (select.value && select.value !== '' && select.value !== 'none') {
            return select.value;
        }
    }
    
    // Try to get from any visible stream container with data attributes
    const streamContainers = document.querySelectorAll('[data-streamer], [data-username]');
    for (const container of streamContainers) {
        const streamer = container.dataset.streamer || container.dataset.username;
        if (streamer && streamer !== 'none' && streamer !== '') {
            return streamer;
        }
    }
    
    // Fallback: try to get from URL or other sources
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('streamer') || 'Please select a streamer first';
}

function getCurrentUserId() {
    return localStorage.getItem('userId') || sessionStorage.getItem('userId') || null;
}

function getCurrentUsername() {
    return localStorage.getItem('username') || sessionStorage.getItem('username') || 'anonymous';
}

function getUserToken() {
    return localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token') || null;
}

function closeMedalModal() {
    document.querySelector('.medal-import-modal')?.remove();
}

function showError(message) {
    removeExistingNotifications();
    
    const notification = document.createElement('div');
    notification.className = 'error-notification';
    notification.innerHTML = `
        <div class="clip-notification error-style">
            <h4>❌ Error</h4>
            <p>${message}</p>
            <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => {
        if (document.body.contains(notification)) {
            notification.remove();
        }
    }, 8000);
}

function showClipLoading(streamerName) {
    removeExistingNotifications();
    
    const notification = document.createElement('div');
    notification.className = 'clip-loading-notification';
    notification.innerHTML = `
        <div class="clip-notification loading-style">
            <h4>⏳ Creating Clip...</h4>
            <p>Creating clip for <strong>${streamerName}</strong></p>
            <div class="loading-spinner"></div>
        </div>
    `;
    
    document.body.appendChild(notification);
}

function removeExistingNotifications() {
    // Remove any existing notifications
    const existing = document.querySelectorAll('.clip-success-notification, .medal-success-notification, .error-notification, .clip-loading-notification');
    existing.forEach(el => el.remove());
}

function showMyClipsModal() {
    const modal = document.createElement('div');
    modal.className = 'my-clips-modal modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h3>📋 My Clips</h3>
                <span class="close" onclick="closeMyClipsModal()">&times;</span>
            </div>
            <div class="modal-body">
                <div id="myClipsContent">
                    <div class="loading-spinner"></div>
                    <p>Loading your clips...</p>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    loadMyClips();
}

async function loadMyClips() {
    try {
        const response = await fetch('/api/my-clips');
        const result = await response.json();
        
        const content = document.getElementById('myClipsContent');
        if (result.success && result.data.clips.length > 0) {
            content.innerHTML = result.data.clips.map(clip => `
                <div class="clip-item">
                    <h4>${clip.title || 'Untitled Clip'}</h4>
                    <p>Streamer: <strong>${clip.broadcaster_login}</strong></p>
                    <p>Created: ${new Date(clip.created_at).toLocaleDateString()}</p>
                    <div class="clip-actions">
                        <button onclick="window.open('${clip.url}', '_blank')" class="btn-primary">Watch</button>
                        ${clip.edit_url ? `<button onclick="window.open('${clip.edit_url}', '_blank')" class="btn-secondary">Edit</button>` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            content.innerHTML = `
                <div class="no-clips">
                    <h4>No clips yet</h4>
                    <p>${result.data.message || 'You haven\'t created any clips yet.'}</p>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById('myClipsContent').innerHTML = `
            <div class="error">
                <h4>Failed to load clips</h4>
                <p>Please try again later.</p>
            </div>
        `;
    }
}

function closeMyClipsModal() {
    document.querySelector('.my-clips-modal')?.remove();
}

async function loadClipsForStreamer(streamerName) {
    try {
        const response = await fetch(`/api/saved-clips/${streamerName}`);
        const result = await response.json();
        
        if (result.success) {
            // You can implement a modal or sidebar to show these clips
            showStreamerClipsModal(streamerName, result.data.clips);
        }
    } catch (error) {
        console.error('Failed to load streamer clips:', error);
    }
}

function showStreamerClipsModal(streamerName, clips) {
    const modal = document.createElement('div');
    modal.className = 'streamer-clips-modal modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h3>📁 ${streamerName}'s Clips</h3>
                <span class="close" onclick="closeStreamerClipsModal()">&times;</span>
            </div>
            <div class="modal-body">
                <div class="clips-grid">
                    ${clips.length > 0 ? clips.map(clip => `
                        <div class="clip-item">
                            <h4>${clip.title || 'Untitled Clip'}</h4>
                            <p>Source: ${clip.source}</p>
                            <p>Views: ${clip.view_count || 0}</p>
                            <div class="clip-actions">
                                <button onclick="window.open('${clip.url}', '_blank')" class="action-btn">Watch</button>
                            </div>
                        </div>
                    `).join('') : '<p>No clips found for this streamer.</p>'}
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function closeStreamerClipsModal() {
    document.querySelector('.streamer-clips-modal')?.remove();
}

// Initialize clip controls when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // --- MODIFICATION ---
    // Run the function to hide the original sidebar buttons as soon as the page is ready.
    hideSidebarClipButtons();

    // Auto-inject clip controls if multistream container exists (but not on the dedicated stream page)
    const multistreamContainer = document.querySelector('.multistream-container, .streams-container, .multistream-modal');
    if (multistreamContainer && !window.location.pathname.includes('/stream')) {
        injectClipControls(multistreamContainer);
    }
    
    // Watch for multistream modal to open and inject controls
    const multiStreamModal = document.getElementById('multiStreamModal');
    if (multiStreamModal) {
        // Use MutationObserver to detect when modal becomes visible
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    const modal = mutation.target;
                    if (modal.style.display !== 'none' && !modal.querySelector('.multistream-clip-controls')) {
                        // Modal is now visible, inject controls
                        setTimeout(() => {
                            const modalContent = modal.querySelector('.modal-content');
                            if (modalContent) {
                                injectClipControlsInModal(modalContent);
                            }
                        }, 100);
                    }
                }
            });
        });
        observer.observe(multiStreamModal, { attributes: true, attributeFilter: ['style'] });
    }
});

function injectClipControls(container) {
    // Check if controls already exist
    if (container.querySelector('.multistream-clip-controls')) {
        return;
    }
    
    const controls = document.createElement('div');
    controls.className = 'multistream-clip-controls';
    controls.innerHTML = `
        <button id="createClipBtn" class="clip-btn" onclick="createClipForCurrentStream()">
            📹 Create Clip
        </button>
        
        <button id="medalImportBtn" class="clip-btn medal-btn" onclick="openMedalImport()">
            🏅 Import Medal.tv
        </button>
        
        <button id="myClipsBtn" class="clip-btn" onclick="viewMyClips()">
            📋 My Clips
        </button>
    `;
    
    // Insert at the top of the container
    container.insertBefore(controls, container.firstChild);
}

function injectClipControlsInModal(modalContent) {
    // Check if controls already exist
    if (modalContent.querySelector('.multistream-clip-controls')) {
        return;
    }
    
    
    
    // Try to find the header more aggressively
    let header = modalContent.querySelector('h2');
    if (!header) {
        header = modalContent.querySelector('.flex.justify-between.items-center');
        if (!header) {
            header = modalContent.firstElementChild;
        }
    }
    
    if (!header) {
        console.error('Could not find header to inject controls after');
        return;
    }
    
    // Create clip controls with VERY explicit positioning
    const clipControls = document.createElement('div');
    clipControls.className = 'multistream-clip-controls';
    clipControls.style.cssText = `
        position: relative !important;
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 20px 0 !important;
        padding: 24px !important;
        background: linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(30, 41, 59, 0.9)) !important;
        border-radius: 16px !important;
        border: 2px solid rgba(148, 163, 184, 0.3) !important;
        text-align: center !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
        clear: both !important;
        z-index: 1000 !important;
    `;
    
    clipControls.innerHTML = `
        <div style="margin-bottom: 20px;">
            <h3 style="color: #ffffff; font-size: 22px; font-weight: 800; margin: 0 0 6px 0; text-align: center; text-shadow: 0 2px 4px rgba(0,0,0,0.3);">
                🎬 Clip Management
            </h3>
            <p style="color: #e2e8f0; font-size: 13px; margin: 0; text-align: center; opacity: 0.9;">
                Create and manage clips for your selected streamers
            </p>
        </div>
        <div style="display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; align-items: center;">
            <button id="createClipBtn" class="clip-btn" onclick="createClipForCurrentStream()" 
                    style="min-width: 140px; font-size: 13px; font-weight: 600; padding: 14px 18px; 
                           background: linear-gradient(135deg, #10b981, #059669); 
                           border: none; border-radius: 8px; color: white; cursor: pointer;
                           box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
                           transition: all 0.2s ease;">
                📹 Create Clip
            </button>
            <button id="medalImportBtn" class="clip-btn medal-btn" onclick="openMedalImport()" 
                    style="min-width: 140px; font-size: 13px; font-weight: 600; padding: 14px 18px;
                           background: linear-gradient(135deg, #f59e0b, #d97706);
                           border: none; border-radius: 8px; color: white; cursor: pointer;
                           box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
                           transition: all 0.2s ease;">
                🏅 Import Medal.tv
            </button>
            <button id="myClipsBtn" class="clip-btn" onclick="viewMyClips()" 
                    style="min-width: 140px; font-size: 13px; font-weight: 600; padding: 14px 18px;
                           background: linear-gradient(135deg, #8b5cf6, #7c3aed);
                           border: none; border-radius: 8px; color: white; cursor: pointer;
                           box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
                           transition: all 0.2s ease;">
                📋 My Clips
            </button>
        </div>
    `;
    
    // Insert immediately after header with maximum force
    if (header.nextSibling) {
        header.parentNode.insertBefore(clipControls, header.nextSibling);
    } else {
        header.parentNode.appendChild(clipControls);
    }
    
    
    
    // Force visibility check after a brief delay
    setTimeout(() => {
        const injectedControls = modalContent.querySelector('.multistream-clip-controls');
        if (!injectedControls) {
            console.error('Controls not found in DOM after injection!');
        }
    }, 100);
}


// Export functions for global access
window.createClipForCurrentStream = createClipForCurrentStream;
window.openMedalImport = openMedalImport;
window.viewMyClips = viewMyClips;
window.closeMedalModal = closeMedalModal;
window.closeMyClipsModal = closeMyClipsModal;
window.closeStreamerClipsModal = closeStreamerClipsModal;
window.injectClipControlsInModal = injectClipControlsInModal;