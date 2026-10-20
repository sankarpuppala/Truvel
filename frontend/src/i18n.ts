/** i18next setup (SPEC §7.3).
 *
 * English is complete and is the only language switched on. Hindi and Telugu
 * exist as drafts and stay behind native review -- a machine translation is
 * never presented as reviewed (CLAUDE.md invariant 11), which is why they are
 * not registered here at all rather than registered and hidden.
 */
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './i18n/en.json';

void i18next.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18next;
