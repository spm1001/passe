#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "mise-en-space @ file:///Users/modha/Repos/mise-en-space",
# ]
# ///
"""
Google Groups thread → clean markdown.

Pipeline:
1. Passe extracts structured JSON (per-message: from, date, body)
2. mise's talon strips standard sigs and quotes
3. This module strips Groups-specific residue
4. Assembles into mise-style thread markdown

Usage:
    uv run --script contrib/groups/clean.py <input.json> [output.md]
"""

import re
import sys
import json

from extractors.talon_signature import strip_signature_and_quotes


# --- Groups-specific cleaning patterns ---

# Corporate sig: "Name Surname | Title | ..." line and everything after
_RE_CORP_SIG = re.compile(
    r'\n\s*[A-Z][a-z]+\s+[A-Z][a-z]+\s*\|[^\n]+'  # "Ella Collis | Senior Legal..."
    r'(?:\n[^\n]*)*$',
)

# Multi-line sig block: blank line -> name -> title -> rest
_RE_MULTILINE_SIG = re.compile(
    r'\n[^\S\n]*\n'
    r'[^\S\n]*[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){0,2}[^\S\n]*\n'
    r'(?:[^\S\n]*\n){0,5}'
    r'[^\S\n]*(?:Marketing|Senior|Head[ \t]+of|Director|Manager|Lead|VP|Chief|'
    r'General[ \t]+Counsel|Legal[ \t]+Advisor|Associate|Analyst|Executive)[^\n]*\n'
    r'(?:[^\n]*\n){0,30}$',
    re.MULTILINE
)

# Sign-off + bare name at end of message
_RE_SIGNOFF_NAME = re.compile(
    r'\n\s*'
    r'(?:Ngā mihi (?:nui|maioha)|Kind regards|Warm regards|Many thanks|'
    r'With thanks|All the best|Best wishes|Best|Thanks!?|Cheers)'
    r'[,!]?\s*'
    r'(?:\s*\n)*'
    r'(?:\s*[A-Z][a-z]+\s*)?'
    r'\s*$',
    re.DOTALL
)

# Attachment filename lines
_RE_ATTACHMENT_LINE = re.compile(
    r'^\s+(?:[A-Z][\w]+[\s-]+){2,}[^\n]*(?:\.(?:docx|xlsx|pdf|pptx|csv|zip|png|jpg))?(?:\s*\(\d+\))?\s*$',
    re.MULTILINE
)

# Quoted reply chains: "From: Name <email>\nSent: ...\nTo: ...\nSubject: ..."
_RE_REPLY_CHAIN = re.compile(
    r'\nFrom:\s+[^\n]+\n'
    r'(?:\s*(?:Sent|Date|To|Cc|Subject|Bcc):\s+[^\n]+\n)+'
    r'(?:[^\n]*\n?)*$',
    re.MULTILINE | re.IGNORECASE
)

# CAUTION / external email banners
_RE_CAUTION = re.compile(
    r'CAUTION:\s+This email originated from outside[^\n]*(?:\n[^\n]*safe\.)?',
    re.IGNORECASE
)

# ITV-specific disclaimers
_RE_ITV_DISCLAIMER = re.compile(
    r'(?:ITV Broadcasting Limited[^\n]*|'
    r'ITV plc Head Office[^\n]*|'
    r'Please consider the environment[^\n]*|'
    r'This email and any attachments are intended solely[^\n]*(?:\n[^\n]*)*?(?:their own protection\.?)|'
    r'This email does not conclude a binding[^\n]*(?:\n[^\n]*)*?(?:those of ITV\.?)|'
    r'We reserve the right to monitor[^\n]*(?:\n[^\n]*)*?(?:regulations\.?)|'
    r'For details of how we process personal[^\n]*(?:\n[^\n]*)*?groupprivacy)',
    re.IGNORECASE | re.MULTILINE
)

# External email warning (Snoop etc.)
_RE_EXTERNAL_WARNING = re.compile(
    r'Please be cautious\s*\n+This email was sent from outside[^\n]*',
    re.IGNORECASE
)

# Phone/address/contact lines
_RE_BARE_CONTACT = re.compile(
    r'\n\s*(?:Tel|Phone|Mobile|Direct|Office|Mob)\s*[:.]?\s*\+?[\d\s\(\)\-]{7,}[^\n]*',
    re.IGNORECASE
)
_RE_ADDRESS = re.compile(
    r'\n\s*(?:ITV White City|201 Wood Lane|\d+\s+\w+\s+(?:Street|Road|Lane|Square|Avenue))[^\n]*',
    re.IGNORECASE
)
_RE_BARE_EMAIL_LINE = re.compile(r'^\s*[\w.+-]+@[\w.-]+\s*$', re.MULTILINE)

# Recipient "to X, Y, Z" line at message start
_RE_RECIPIENTS = re.compile(
    r'^to\s+(?:[A-Z][\w\s]+(?:,\s*)?)+(?:Measurement Innovation Team[,\s]*)?\n*',
    re.IGNORECASE
)

# FaceTime/WhatsApp contact lines
_RE_FACETIME = re.compile(r'FaceTime/WhatsApp[^\n]*', re.IGNORECASE)


def clean_groups_message(body: str) -> str:
    """Clean a single Google Groups message body."""
    if not body or not body.strip():
        return ''

    # Normalise: NBSP -> space, strip Google icon PUA chars
    body = body.replace('\xa0', ' ')
    body = re.sub(r'[\ue000-\uf8ff]', '', body)

    # Strip recipients line at start
    body = _RE_RECIPIENTS.sub('', body, count=1).strip()

    # mise's standard pipeline (> quotes, standard sigs, forwards)
    body = strip_signature_and_quotes(body)

    # Groups-specific cleaning (order matters)
    body = _RE_CAUTION.sub('', body)
    body = _RE_EXTERNAL_WARNING.sub('', body)
    body = _RE_REPLY_CHAIN.sub('', body)
    body = _RE_ITV_DISCLAIMER.sub('', body)
    body = _RE_CORP_SIG.sub('', body)
    body = _RE_MULTILINE_SIG.sub('', body)
    body = _RE_FACETIME.sub('', body)
    body = _RE_BARE_CONTACT.sub('', body)
    body = _RE_ADDRESS.sub('', body)
    body = _RE_ATTACHMENT_LINE.sub('', body)
    body = _RE_SIGNOFF_NAME.sub('', body)

    # Collapse excessive blank lines
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def format_thread(data: dict) -> str:
    """Format extracted thread data as mise-style markdown."""
    subject = data.get('subject', 'Untitled Thread')
    total = data['message_count']
    parts = [f"# {subject}\n"]

    for m in data['messages']:
        i = m['index']
        header = f"[{i+1}/{total}] From: {m['from']} | Date: {m['date']}"
        cleaned = clean_groups_message(m['body'])

        if i > 0:
            parts.append("\n---\n")
        parts.append(f"{header}\n")
        if cleaned:
            parts.append(cleaned)
        else:
            parts.append("*(empty)*")
        parts.append("")

    return '\n'.join(parts)


if __name__ == '__main__':
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    with open(input_path) as f:
        data = json.load(f)

    result = format_thread(data)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)

    # Stats to stderr
    raw_total = sum(len(m['body']) for m in data['messages'])
    total = data['message_count']
    print(f"Messages: {total} | Raw: {raw_total} chars -> Clean: {len(result)} chars | "
          f"Reduction: {100 - len(result) * 100 // max(raw_total, 1)}%", file=sys.stderr)

    if not output_path:
        print(result)
