/** Place names, rendered the one correct way (SPEC §7.2, AC-4).
 *
 * No screen is allowed to read `place.name.primary.text` and print it itself.
 * Everything goes through here, because three things have to be right every
 * time and are easy to forget:
 *
 *  - the `lang` attribute, so a browser picks the right font and a screen
 *    reader the right voice;
 *  - `<bdi dir="rtl">` around Perso-Arabic names, so an Urdu name inside an
 *    English sentence does not reorder the text around it;
 *  - the small "auto" tag on a machine-transliterated name, so a guess is
 *    never presented as a fact.
 */
import type { NameBlockData, NameLine } from '../lib/types';

/** One line of a name, with its language and direction handled. */
export function Name({
  line,
  className,
}: {
  line: NameLine;
  className?: string;
}) {
  const content = line.rtl ? (
    <bdi dir="rtl" lang={line.lang}>
      {line.text}
    </bdi>
  ) : (
    <span lang={line.lang}>{line.text}</span>
  );

  return (
    <span className={className}>
      {content}
      {line.auto && (
        <>
          {' '}
          <span className="badge" title="Transliterated automatically, not checked by a person">
            auto
          </span>
        </>
      )}
    </span>
  );
}

/**
 * Both lines of a place name.
 *
 * `primaryClass` and `secondaryClass` take the reference's class names, so the
 * same component renders a deck card's 32 px display type (`pname`/`lname`), an
 * Explore row (`rname`/`rlname`) and a Place page heading (`pl-name`/`pl-lname`).
 */
export function NameBlock({
  name,
  primaryClass = 'rname',
  secondaryClass = 'rlname',
  as: Tag = 'div',
}: {
  name: NameBlockData;
  primaryClass?: string;
  secondaryClass?: string;
  as?: 'div' | 'h1' | 'h2' | 'h3' | 'span';
}) {
  return (
    <>
      <Tag className={primaryClass}>
        <Name line={name.primary} />
      </Tag>
      {name.secondary && (
        <div className={secondaryClass}>
          <Name line={name.secondary} />
        </div>
      )}
    </>
  );
}

/** The plain text of a name, for a title attribute or a share message. */
export function nameText(name: NameBlockData): string {
  return name.primary.text;
}
