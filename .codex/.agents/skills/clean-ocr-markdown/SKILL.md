---
name: clean-ocr-markdown
description: Conservatively clean Markdown transcribed from phone photos or OCR scans while preserving meaning and Markdown structure. Use when Markdown has spelling mistakes, broken words, overlapping or repeated OCR text, garbled punctuation, and mixed prose/code, especially when the cleaned result will be consumed by an LLM.
---

# Clean OCR Markdown

Produce a minimally changed Markdown document that is easier for an LLM to read. Treat the source as evidence: repair only what is clear from the local text and never improve, summarize, reorganize, or infer missing meaning.

## Protect first

1. Preserve YAML front matter, headings, links, image paths, block quotes, tables, lists, HTML, and Markdown delimiters unless an OCR error makes the syntax clearly invalid.
2. Copy fenced code blocks, indented code, inline code, commands, filenames, URLs, identifiers, literals, and stack traces verbatim. Do not spell-check, reformat, deduplicate, or repair them.
3. Preserve deliberate repetition: repeated instructions, emphasis, refrains, examples, table rows, list entries, and non-adjacent material can be meaningful.
4. Do not add facts, resolve ambiguous wording by guesswork, translate, modernize style, or convert the document into a summary.

## Clean conservatively

Make only high-confidence, local corrections:

- Fix unmistakable OCR substitutions and spelling errors when the intended token is evident from the same sentence or a nearby unambiguous occurrence.
- Restore spaces in plainly merged words and remove spaces in plainly split words.
- Normalize accidental repeated punctuation and obvious punctuation-recognition errors when this does not alter meaning.
- Repair a broken Markdown delimiter only when its intended structure is unambiguous.
- Keep paragraph and list order unchanged. Retain original wording and capitalization except for the smallest required correction.

For uncertain text, retain the source text and make the uncertainty explicit with `[OCR unclear: <source>]`. Do not replace it with a speculative correction. If the uncertainty is already obvious from the source, leave it unchanged rather than adding a marker.

## Remove accidental duplicates

Remove a duplicate only when all of these are true:

1. It is adjacent or part of an immediately overlapping OCR fragment.
2. Its text is exact or differs only in OCR noise, whitespace, or punctuation.
3. The retained occurrence contains every unique word or meaningful symbol.
4. It is outside protected code and does not alter a list, table, or quoted source.

Safe examples include a heading repeated on the next line, a sentence duplicated by an overlapping photograph, or a repeated word such as `the the` when clearly accidental. When overlap leaves competing readings, preserve both and mark the affected fragment as unclear rather than deleting either one.

## Work in passes

1. Identify protected regions and keep them unchanged.
2. Compare adjacent prose lines and paragraphs for exact or near-exact OCR duplication; remove only qualified duplicates.
3. Apply high-confidence local corrections to the remaining prose.
4. Re-read the result against the source and reverse any change that depends on interpretation rather than evidence.
5. Check that Markdown fences, list nesting, tables, links, and front matter still balance.

## Return format

Return the cleaned Markdown by default, without a rewrite explanation embedded in the document. If the requester asks for an audit, provide a separate concise list of removals, corrections, and unresolved `[OCR unclear: ...]` markers.

