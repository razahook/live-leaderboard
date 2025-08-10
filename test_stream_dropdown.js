// Test script to verify the dropdown functionality
// This simulates what happens in the browser

const fetch = require('node-fetch');

async function testStreamDropdown() {
    try {
        console.log('Fetching leaderboard data...');
        const response = await fetch('http://localhost:5000/api/leaderboard/PC');
        const data = await response.json();
        
        console.log('API Response Status:', response.ok);
        console.log('API Success:', data.success);
        
        if (data.success && data.data && data.data.players) {
            const allPlayers = data.data.players;
            console.log('Total players:', allPlayers.length);
            
            // Filter for live streamers - same logic as the webpage
            const liveStreamers = allPlayers.filter(player => {
                const twitchLive = player.twitch_live?.is_live === true;
                const hasUser = !!(player.stream?.twitchUser || player.canonical_twitch_username || player.twitch_link);
                return twitchLive && hasUser;
            });
            
            console.log('Live streamers found:', liveStreamers.length);
            
            // Show first 5 live streamers for verification
            console.log('\nFirst 5 live streamers:');
            liveStreamers.slice(0, 5).forEach((player, index) => {
                const twitchUsername = player.stream?.twitchUser || player.canonical_twitch_username;
                const viewerCount = player.stream?.viewers || 0;
                const playerName = player.player_name || player.name;
                
                console.log(`${index + 1}. ${playerName} (${twitchUsername}) - ${viewerCount} viewers`);
                console.log(`   Twitch Live: ${player.twitch_live?.is_live}`);
                console.log(`   Stream Data: ${JSON.stringify(player.stream)}`);
                console.log('');
            });
            
        } else {
            console.log('Invalid API response structure');
            console.log('Data keys:', Object.keys(data));
        }
        
    } catch (error) {
        console.error('Error testing dropdown:', error);
    }
}

testStreamDropdown();