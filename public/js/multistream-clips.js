// Enhanced Multistream Clip Integration
// Auto-link clips to streamers and Medal.tv import functionality

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
    modal.className = 'medal-import-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeMedalModal()">
            <div class="modal-content" onclick="event.stopPropagation()">
                <h3>🏅 Import Medal.tv Clip</h3>
                
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
                    
                    <div class="modal-actions">
                        <button type="submit" class="btn-primary">
                            <span class="btn-text">Import Clip</span>
                            <span class="btn-loading" style="display: none;">Importing...</span>
                        </button>
                        <button type="button" onclick="closeMedalModal()" class="btn-secondary">Cancel</button>
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
    modal.className = 'my-clips-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeMyClipsModal()">
            <div class="modal-content large-modal" onclick="event.stopPropagation()">
                <h3>📋 My Clips</h3>
                <div id="myClipsContent">
                    <div class="loading-spinner"></div>
                    <p>Loading your clips...</p>
                </div>
                <button class="close-btn" onclick="closeMyClipsModal()">×</button>
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
            console.log(`Clips for ${streamerName}:`, result.data);
            // You can implement a modal or sidebar to show these clips
            showStreamerClipsModal(streamerName, result.data.clips);
        }
    } catch (error) {
        console.error('Failed to load streamer clips:', error);
    }
}

function showStreamerClipsModal(streamerName, clips) {
    const modal = document.createElement('div');
    modal.className = 'streamer-clips-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeStreamerClipsModal()">
            <div class="modal-content large-modal" onclick="event.stopPropagation()">
                <h3>📁 ${streamerName}'s Clips</h3>
                <div class="clips-grid">
                    ${clips.length > 0 ? clips.map(clip => `
                        <div class="clip-item">
                            <h4>${clip.title || 'Untitled Clip'}</h4>
                            <p>Source: ${clip.source}</p>
                            <p>Views: ${clip.view_count || 0}</p>
                            <div class="clip-actions">
                                <button onclick="window.open('${clip.url}', '_blank')" class="btn-primary">Watch</button>
                            </div>
                        </div>
                    `).join('') : '<p>No clips found for this streamer.</p>'}
                </div>
                <button class="close-btn" onclick="closeStreamerClipsModal()">×</button>
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
    // Auto-inject clip controls if multistream container exists
    const multistreamContainer = document.querySelector('.multistream-container, #multistream, .streams-container, .multistream-modal');
    if (multistreamContainer) {
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
    
    // Get the header and all content after it
    const header = modalContent.querySelector('.flex.justify-between.items-center.mb-6');
    if (!header) return;
    
    // Get all content after the header
    const allContentAfterHeader = [];
    let nextSibling = header.nextElementSibling;
    while (nextSibling) {
        allContentAfterHeader.push(nextSibling);
        nextSibling = nextSibling.nextElementSibling;
    }
    
    // Remove all content after header temporarily
    allContentAfterHeader.forEach(el => el.remove());
    
    // Create the unified content wrapper
    const unifiedWrapper = document.createElement('div');
    unifiedWrapper.style.cssText = `
        background: rgba(17, 24, 39, 0.6);
        border-radius: 16px;
        border: 1px solid rgba(75, 85, 99, 0.3);
        padding: 24px;
        margin-top: 16px;
    `;
    
    // Create clip controls section
    const clipControls = document.createElement('div');
    clipControls.className = 'multistream-clip-controls';
    clipControls.style.cssText = `
        text-align: center;
        margin-bottom: 32px;
        padding: 20px;
        background: rgba(30, 41, 59, 0.8);
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.2);
    `;
    clipControls.innerHTML = `
        <h3 style="color: #f1f5f9; font-size: 18px; font-weight: 700; margin: 0 0 8px 0;">
            🎬 Clip Management
        </h3>
        <p style="color: #cbd5e1; font-size: 14px; margin: 0 0 20px 0;">
            Create and manage clips for your selected streamers
        </p>
        <div style="display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;">
            <button id="createClipBtn" class="clip-btn" onclick="createClipForCurrentStream()" style="min-width: 140px;">
                📹 Create Clip
            </button>
            <button id="medalImportBtn" class="clip-btn medal-btn" onclick="openMedalImport()" style="min-width: 140px;">
                🏅 Import Medal.tv
            </button>
            <button id="myClipsBtn" class="clip-btn" onclick="viewMyClips()" style="min-width: 140px;">
                📋 My Clips
            </button>
        </div>
    `;
    
    // Add clip controls to wrapper
    unifiedWrapper.appendChild(clipControls);
    
    // Add all original content back to wrapper
    allContentAfterHeader.forEach(el => {
        // Remove any existing margin-bottom from sections to avoid double spacing
        if (el.classList.contains('mb-6')) {
            el.classList.remove('mb-6');
            el.classList.add('mb-8');
        }
        unifiedWrapper.appendChild(el);
    });
    
    // Insert the unified wrapper after header
    header.parentNode.insertBefore(unifiedWrapper, header.nextSibling);
}

// Export functions for global access
window.createClipForCurrentStream = createClipForCurrentStream;
window.openMedalImport = openMedalImport;
window.viewMyClips = viewMyClips;
window.closeMedalModal = closeMedalModal;
window.closeMyClipsModal = closeMyClipsModal;
window.closeStreamerClipsModal = closeStreamerClipsModal;