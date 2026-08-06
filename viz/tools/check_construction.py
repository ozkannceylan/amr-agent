#!/usr/bin/env python3
"""check_construction.py - the two static acceptance checks of viz/DESIGN.md.

    python3 viz/tools/check_construction.py            # both checks, verbose
    python3 viz/tools/check_construction.py --quiet     # verdict lines only

No ROS, no network, no running process. It reads files and reports.

CHECK A (DESIGN 8.2) - the entity-creating call names appear in exactly one
place in this layer's source: the forbidden-call list inside
`viz/monitor/subscribe_only.py`, which is the one module allowed to construct
rclpy objects at all.

THE LIST IS NOT DUPLICATED HERE, AND THAT IS THE DESIGN. This file carries no
literal copy of the names it searches for; it reads them out of the factory
module's own list. Two copies of a rule are how the copies come to disagree
(invariant 10), and a checker holding its own copy would also, absurdly, be a
second file in `viz/` naming the calls - failing the very check it runs.

SCOPE IS `*.py` UNDER `viz/`, deliberately. The rule is about what constructs
an entity, and a Markdown file constructs nothing. Prose that names a
forbidden call is a SPECIFICATION of this check rather than an instance of it -
`viz/DESIGN.md` section 2.1 is exactly that, and it is the document this
checker exists to serve.

CHECK B (DESIGN 8.6) - the read-only claim never appears in its unqualified
short form anywhere in `viz/`, in source or in prose. Its only admissible form
is the one recorded in DESIGN section 2:

    read-only by construction of the process and proven by test; not enforced
    by the middleware

THE SWEEP NORMALISES WHITESPACE BEFORE SEARCHING. A phrase this long sits
across a line break in any wrapped document, and a plain line-oriented grep
reports a file clean because the phrase it wants is split over two lines
(docs/LESSONS.md 2026-07-27). Blockquote and comment markers are stripped as
part of the same flattening, because a quoted claim wraps as `> ...` and a
docstring one as `# ...`.

EVERY OCCURRENCE IS PRINTED WITH ITS VERDICT, not only the failures. A check
that shows what it found can be disagreed with; one that prints PASS cannot.
"""

import argparse
import os
import re
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
VIZ_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
FACTORY = os.path.join(VIZ_DIR, 'monitor', 'subscribe_only.py')

_MARKER = re.compile(r'^\s*(?:#\s*)?forbidden-call:\s*(\S+)\s*$')

#: The claim, and the words that make it admissible. THE PHRASE IS ASSEMBLED
#: FROM PIECES ON PURPOSE. A checker whose source carried the short form
#: literally would be one more file in `viz/` carrying the short form - it
#: would report itself, and a check that must exempt itself is a check nobody
#: can read. Same discipline as the forbidden-call list: the rule lives in one
#: place, and this file is not a second instance of what it forbids.
CLAIM = 'read-only by' + ' construction'
QUALIFIER = 'of the process' + ' and proven by test'
#: A sentence that names the short form in order to forbid it is not an
#: instance of it. These are the words such a sentence carries.
PROHIBITION_WORDS = ('unqualified', 'never the', 'short form')


def read_forbidden_calls():
    """The one list, read from the one file that owns it."""
    names = []
    with open(FACTORY, 'r', encoding='utf-8') as handle:
        for line in handle:
            match = _MARKER.match(line)
            if match:
                names.append(match.group(1))
    if not names:
        raise RuntimeError(
            '{} carries no forbidden-call list. That list is the definition '
            'of DESIGN 8.2 and this checker has no second copy of it by '
            'design.'.format(FACTORY))
    return names


def _sources():
    for root, dirs, files in os.walk(VIZ_DIR):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for name in sorted(files):
            if name.endswith('.py'):
                yield os.path.join(root, name)


def _all_files():
    for root, dirs, files in os.walk(VIZ_DIR):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for name in sorted(files):
            if name.endswith(('.py', '.md', '.yaml', '.yml', '.html', '.js')):
                yield os.path.join(root, name)


def _rel(path):
    return os.path.relpath(path, os.path.dirname(VIZ_DIR)).replace('\\', '/')


def check_entity_calls(verbose=True):
    names = read_forbidden_calls()
    hits = {name: [] for name in names}
    for path in _sources():
        with open(path, 'r', encoding='utf-8') as handle:
            for lineno, line in enumerate(handle, 1):
                for name in names:
                    if name in line:
                        hits[name].append((path, lineno, line.rstrip()))

    failures = []
    if verbose:
        print('CHECK A - entity-creating calls, {} names, scope viz/**/*.py'
              .format(len(names)))
    for name in names:
        found = hits[name]
        allowed = [h for h in found
                   if os.path.abspath(h[0]) == os.path.abspath(FACTORY)
                   and _MARKER.match(h[2] + '\n')]
        stray = [h for h in found if h not in allowed]
        verdict = 'ok' if (len(allowed) == 1 and not stray) else 'FAIL'
        if verdict == 'FAIL':
            failures.append(name)
        if verbose:
            print('  {:<18} {:<4} {} hit(s): {}'.format(
                name, verdict, len(found),
                ', '.join('{}:{}'.format(_rel(p), n) for p, n, _ in found)
                or 'none'))
        for path, lineno, text in stray:
            if verbose:
                print('      STRAY  {}:{}  {}'.format(
                    _rel(path), lineno, text.strip()))
    return failures


def _flatten(text):
    """One line, markers stripped, whitespace collapsed, literals rejoined.

    Three wrappings hide the same phrase from a line-oriented grep, and all
    three occur in this layer: a Markdown blockquote wraps as `> ...`, a Python
    comment as `# ...`, and a long Python string wraps as ADJACENT LITERALS -
    `'... of the process ' 'and proven by test ...'` - which puts a quote, a
    space and a quote in the middle of the sentence. Undoing all three is what
    makes the sweep a sweep of the claim rather than of its formatting
    (docs/LESSONS.md 2026-07-27).
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        while stripped[:1] in ('>', '#'):
            stripped = stripped[1:].strip()
        lines.append(stripped)
    flat = re.sub(r'\s+', ' ', ' '.join(lines))
    return re.sub(r"(['\"])\s+\1", '', flat)


def check_claim_phrasing(verbose=True):
    failures = []
    occurrences = 0
    if verbose:
        print('\nCHECK B - the read-only claim, whitespace-normalised, '
              'scope viz/**')
    for path in _all_files():
        with open(path, 'r', encoding='utf-8') as handle:
            flat = _flatten(handle.read())
        start = 0
        while True:
            idx = flat.find(CLAIM, start)
            if idx < 0:
                break
            start = idx + len(CLAIM)
            occurrences += 1
            tail = flat[idx + len(CLAIM):idx + len(CLAIM) + 60].lower()
            head = flat[max(0, idx - 200):idx].lower()
            if tail.lstrip().startswith(QUALIFIER):
                verdict = 'qualified'
            elif any(word in head for word in PROHIBITION_WORDS):
                verdict = 'prohibition notice'
            else:
                verdict = 'BARE'
                failures.append((path, idx))
            if verbose:
                print('  {:<12} {}'.format(verdict, _rel(path)))
                print('      ...{}...'.format(
                    flat[max(0, idx - 60):idx + len(CLAIM) + 80]))
    if verbose:
        print('  {} occurrence(s) examined'.format(occurrences))
    return failures


def run(verbose=True):
    a = check_entity_calls(verbose)
    b = check_claim_phrasing(verbose)
    if verbose:
        print('\nCHECK A {}   CHECK B {}'.format(
            'PASS' if not a else 'FAIL ({})'.format(a),
            'PASS' if not b else 'FAIL ({})'.format(
                [_rel(p) for p, _ in b])))
    return not a and not b


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args(argv)
    ok = run(verbose=not args.quiet)
    print('CONSTRUCTION CHECKS {}'.format('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
