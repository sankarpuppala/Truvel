/** Every language name/script name Truvel knows (SPEC §7.1), in one place.
 *
 * Each place-name language is stored as its ISO 639-1 code ("kn", "te") --
 * the standard two-letter tag HTML and i18next both expect, which is also
 * what goes in the `lang` attribute on every name so a screen reader
 * pronounces it correctly and `@fontsource`'s `unicode-range` picks the
 * right font (CLAUDE.md invariant 10). A person never has to read a raw code:
 * every picker shows the language's own name in its own script instead.
 */
export const LANGUAGES: { code: string; autonym: string; english: string; rtl?: boolean }[] = [
  { code: 'en', autonym: 'English', english: 'English' },
  { code: 'hi', autonym: 'हिन्दी', english: 'Hindi' },
  { code: 'te', autonym: 'తెలుగు', english: 'Telugu' },
  { code: 'ta', autonym: 'தமிழ்', english: 'Tamil' },
  { code: 'kn', autonym: 'ಕನ್ನಡ', english: 'Kannada' },
  { code: 'ml', autonym: 'മലയാളം', english: 'Malayalam' },
  { code: 'mr', autonym: 'मराठी', english: 'Marathi' },
  { code: 'bn', autonym: 'বাংলা', english: 'Bengali' },
  { code: 'gu', autonym: 'ગુજરાતી', english: 'Gujarati' },
  { code: 'pa', autonym: 'ਪੰਜਾਬੀ', english: 'Punjabi' },
  { code: 'or', autonym: 'ଓଡ଼ିଆ', english: 'Odia' },
  { code: 'as', autonym: 'অসমীয়া', english: 'Assamese' },
  { code: 'ur', autonym: 'اردو', english: 'Urdu', rtl: true },
  { code: 'ks', autonym: 'كٰشُر', english: 'Kashmiri', rtl: true },
  { code: 'sd', autonym: 'سنڌي', english: 'Sindhi', rtl: true },
  { code: 'gom', autonym: 'कोंकणी', english: 'Konkani' },
  { code: 'mai', autonym: 'मैथिली', english: 'Maithili' },
  { code: 'doi', autonym: 'डोगरी', english: 'Dogri' },
  { code: 'brx', autonym: 'बर’', english: 'Bodo' },
  { code: 'ne', autonym: 'नेपाली', english: 'Nepali' },
  { code: 'sa', autonym: 'संस्कृतम्', english: 'Sanskrit' },
  { code: 'sat', autonym: 'ᱥᱟᱱᱛᱟᱲᱤ', english: 'Santali' },
  { code: 'mni', autonym: 'ꯃꯤꯇꯩꯂꯣꯟ', english: 'Manipuri' },
];

/** "Kannada (ಕನ್ನಡ)", or the bare code if it is somehow not in the table. */
export function languageLabel(code: string): string {
  const entry = LANGUAGES.find((lang) => lang.code === code);
  return entry ? `${entry.english} (${entry.autonym})` : code;
}
