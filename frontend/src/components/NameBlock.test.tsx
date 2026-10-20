/** How a place name renders (SPEC §7.2, AC-4).
 *
 * The server picks *which* names to show; this checks the three things the
 * client is responsible for: the `lang` attribute, RTL isolation, and the
 * "auto" tag on a machine transliteration.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Name, NameBlock, nameText } from './NameBlock';
import type { NameBlockData } from '../lib/types';

const GOLCONDA: NameBlockData = {
  primary: { text: 'Golconda Fort', lang: 'en', rtl: false, auto: false },
  secondary: {
    text: 'గోల్కొండ కోట',
    lang: 'te',
    rtl: false,
    auto: false,
  },
  langs: ['en', 'te', 'ur'],
};

describe('NameBlock', () => {
  it('renders both lines with the reference class names', () => {
    const { container } = render(<NameBlock name={GOLCONDA} />);
    expect(container.querySelector('.rname')).toHaveTextContent('Golconda Fort');
    expect(container.querySelector('.rlname')).toHaveTextContent(
      'గోల్కొండ కోట',
    );
  });

  it('puts a lang attribute on every name, so the right font is used', () => {
    const { container } = render(<NameBlock name={GOLCONDA} />);
    expect(container.querySelector('[lang="en"]')).not.toBeNull();
    expect(container.querySelector('[lang="te"]')).not.toBeNull();
  });

  it('renders only one line when there is no second name', () => {
    const { container } = render(
      <NameBlock name={{ ...GOLCONDA, secondary: null }} />,
    );
    expect(container.querySelector('.rlname')).toBeNull();
  });

  it('takes the class names the calling screen needs', () => {
    const { container } = render(
      <NameBlock name={GOLCONDA} primaryClass="pname" secondaryClass="lname" as="h3" />,
    );
    expect(container.querySelector('h3.pname')).not.toBeNull();
    expect(container.querySelector('.lname')).not.toBeNull();
  });
});

describe('right-to-left names', () => {
  it('wraps a Perso-Arabic name in <bdi dir="rtl">', () => {
    const { container } = render(
      <Name
        line={{
          text: 'گولکندہ قلعہ',
          lang: 'ur',
          rtl: true,
          auto: false,
        }}
      />,
    );
    const bdi = container.querySelector('bdi');
    expect(bdi).not.toBeNull();
    expect(bdi).toHaveAttribute('dir', 'rtl');
    expect(bdi).toHaveAttribute('lang', 'ur');
  });

  it('does not isolate a left-to-right name', () => {
    const { container } = render(
      <Name line={{ text: 'Golconda Fort', lang: 'en', rtl: false, auto: false }} />,
    );
    expect(container.querySelector('bdi')).toBeNull();
  });
});

describe('machine transliteration is labelled', () => {
  it('tags an auto name so a guess is never shown as a fact', () => {
    render(
      <Name line={{ text: 'అటో', lang: 'te', rtl: false, auto: true }} />,
    );
    expect(screen.getByText('auto')).toBeInTheDocument();
  });

  it('does not tag a human or imported name', () => {
    render(<Name line={{ text: 'Golconda Fort', lang: 'en', rtl: false, auto: false }} />);
    expect(screen.queryByText('auto')).toBeNull();
  });
});

describe('nameText', () => {
  it('gives the plain primary text, for a share message', () => {
    expect(nameText(GOLCONDA)).toBe('Golconda Fort');
  });
});
