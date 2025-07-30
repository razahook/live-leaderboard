/**
 * Utility functions for the live leaderboard application
 */

/**
 * Normalizes Twitch links to ensure proper formatting
 * @param {string} input - Either a full Twitch URL or just a username
 * @returns {string} - Normalized Twitch URL with https://twitch.tv/ prefix
 */
function getTwitchUrl(input) {
    if (!input || typeof input !== 'string') {
        return '';
    }
    
    const trimmed = input.trim();
    if (!trimmed) {
        return '';
    }
    
    // If it's already a full URL (contains protocol and domain), return as-is
    if (trimmed.match(/^https?:\/\/(www\.)?twitch\.tv\//i)) {
        return trimmed;
    }
    
    // If it contains twitch.tv but no protocol, add https://
    if (trimmed.match(/^(www\.)?twitch\.tv\//i)) {
        return `https://${trimmed}`;
    }
    
    // If it's just a username, prefix with https://twitch.tv/
    // Remove any leading slashes
    const username = trimmed.replace(/^\/+/, '');
    return `https://twitch.tv/${username}`;
}

// Export for testing (if running in Node.js environment)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { getTwitchUrl };
}