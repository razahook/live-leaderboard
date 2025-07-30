/**
 * Tests for utility functions
 */

const { getTwitchUrl } = require('./utils.js');

describe('getTwitchUrl', () => {
    test('should return empty string for null/undefined input', () => {
        expect(getTwitchUrl(null)).toBe('');
        expect(getTwitchUrl(undefined)).toBe('');
        expect(getTwitchUrl('')).toBe('');
        expect(getTwitchUrl('   ')).toBe('');
    });

    test('should return empty string for non-string input', () => {
        expect(getTwitchUrl(123)).toBe('');
        expect(getTwitchUrl({})).toBe('');
        expect(getTwitchUrl([])).toBe('');
    });

    test('should handle full HTTPS URLs correctly', () => {
        expect(getTwitchUrl('https://www.twitch.tv/Naughty')).toBe('https://www.twitch.tv/Naughty');
        expect(getTwitchUrl('https://twitch.tv/shroud')).toBe('https://twitch.tv/shroud');
        expect(getTwitchUrl('https://www.twitch.tv/testuser')).toBe('https://www.twitch.tv/testuser');
    });

    test('should handle HTTP URLs correctly', () => {
        expect(getTwitchUrl('http://www.twitch.tv/Naughty')).toBe('http://www.twitch.tv/Naughty');
        expect(getTwitchUrl('http://twitch.tv/shroud')).toBe('http://twitch.tv/shroud');
    });

    test('should add https:// to URLs missing protocol', () => {
        expect(getTwitchUrl('www.twitch.tv/Naughty')).toBe('https://www.twitch.tv/Naughty');
        expect(getTwitchUrl('twitch.tv/shroud')).toBe('https://twitch.tv/shroud');
    });

    test('should prefix usernames with full Twitch URL', () => {
        expect(getTwitchUrl('Naughty')).toBe('https://twitch.tv/Naughty');
        expect(getTwitchUrl('shroud')).toBe('https://twitch.tv/shroud');
        expect(getTwitchUrl('testuser123')).toBe('https://twitch.tv/testuser123');
    });

    test('should handle usernames with leading slashes', () => {
        expect(getTwitchUrl('/Naughty')).toBe('https://twitch.tv/Naughty');
        expect(getTwitchUrl('//shroud')).toBe('https://twitch.tv/shroud');
    });

    test('should trim whitespace', () => {
        expect(getTwitchUrl('  Naughty  ')).toBe('https://twitch.tv/Naughty');
        expect(getTwitchUrl('  https://www.twitch.tv/Naughty  ')).toBe('https://www.twitch.tv/Naughty');
    });

    test('should be case insensitive for domain matching', () => {
        expect(getTwitchUrl('HTTPS://WWW.TWITCH.TV/Naughty')).toBe('HTTPS://WWW.TWITCH.TV/Naughty');
        expect(getTwitchUrl('WWW.TWITCH.TV/Naughty')).toBe('https://WWW.TWITCH.TV/Naughty');
    });
});