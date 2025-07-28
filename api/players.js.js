// This is your serverless backend API (api/players.js)
export default function handler(request, response) {
  // In a real application, you would fetch this data from a database.
  // For now, we'll use the same mock data.
  const players = [
    { rank: 1, name: 'jukeyzfps', rp: 274126, change: 11736, level: 1571, status: 'Live', stream: { viewers: 296, game: 'Apex Legends' } },
    { rank: 2, name: 'ZeedoTV_', rp: 260650, change: 1102, level: 1820, status: 'Offline', stream: null },
    { rank: 3, name: 'anayayumi', rp: 212775, change: 11487, level: 4819, status: 'Live', stream: { viewers: 309, game: 'Apex Legends' } },
    { rank: 4, name: 'Player4', rp: 211545, change: -7477, level: 1932, status: 'Offline', stream: null },
    { rank: 5, name: 'Hawqeh', rp: 209442, change: 7029, level: 4566, status: 'Offline', stream: null },
    { rank: 6, name: 'Rogue', rp: 198868, change: -357, level: 3973, status: 'In-match', stream: null },
  ];

  response.status(200).json(players);
}

