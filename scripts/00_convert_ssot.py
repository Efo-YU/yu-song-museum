#!/usr/bin/env python3
"""
Convert an SSoT MusicXML (full combined score) into pipeline-ready parts.

Outputs:
  projects/<song>/vocal.musicxml  — NEUTRINO-ready: vocal part only,
                                    repeats expanded, multi-verse lyrics merged,
                                    punctuation stripped, dummy lyrics inserted.
  projects/<song>/inst.musicxml   — Backing: accompaniment parts only,
                                    repeat structure preserved (FluidSynth /
                                    music21 expands it during MIDI conversion).

Usage:
  python3 scripts/00_convert_ssot.py --song SLUG [--ssot PATH]
      [--vocal-part-id ID ...]

Vocal-part detection priority:
  1. --vocal-part-id on the CLI
  2. ssot.vocal_part_ids in song.json
  3. Heuristic: instrument-sound starting with "voice.", or part-name / abbr
     matching known vocal keywords

Supported repeat constructs:
  - Forward / backward repeat barlines  (|:  :||)
  - Volta brackets, 1st/2nd/Nth endings ([1.  [2.)
  - Simple repeat with times attribute
  - D.C. al Fine, D.C. al Coda
  - D.S. al Fine, D.S. al Coda
  - Segno (𝄋) and Coda (𝄌) markers

Not supported (documented limitation):
  - Nested repeats (a repeat section that contains another repeat section)
  - A second D.C./D.S. jump within the same part (only the first is followed)
"""

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"

# Instrument sounds that identify a vocal part (MusicXML instrument-sound values)
_VOICE_SOUND_PREFIX = "voice."

# Part-name / abbreviation keywords that identify a vocal part
_VOCAL_NAME_RE = re.compile(
    r"(voice|vocal|soprano|mezzo|tenor|baritone|alto|bass|choir|chorus"
    r"|ソプラノ|メゾ|アルト|テノール|バリトン|バス|ボーカル|合唱|歌|唱)",
    re.IGNORECASE,
)

# Punctuation to strip from lyric text
_LYRIC_PUNCT_RE = re.compile(
    r"[、。！？!?「」『』【】〔〕〈〉《》（）()\[\]…‥・〜～,\.;:・]"
)

# Dummy lyric inserted when a sounding note has no lyric
_DUMMY_LYRIC = "あ"

# Sound attributes used for navigation (stripped from expanded output)
_JUMP_SOUND_ATTRS = frozenset(
    {"dacapo", "dalsegno", "segno", "coda", "fine", "tocoda"}
)


# ── Part detection ────────────────────────────────────────────────────────────


def detect_parts(root: ET.Element, override_ids: list[str] | None) -> tuple[list[str], list[str]]:
    """
    Return (vocal_ids, backing_ids) — lists of part-id strings in document order.

    Raises ValueError if no vocal part can be identified.
    """
    part_list = root.find("part-list")
    if part_list is None:
        raise ValueError("No <part-list> element in score")

    all_ids = [sp.get("id", "") for sp in part_list.findall("score-part")]

    if override_ids:
        unknown = set(override_ids) - set(all_ids)
        if unknown:
            raise ValueError(f"Specified part IDs not found in score: {sorted(unknown)}")
        vocal_ids = [pid for pid in all_ids if pid in override_ids]
        backing_ids = [pid for pid in all_ids if pid not in override_ids]
        return vocal_ids, backing_ids

    vocal_ids = []
    for sp in part_list.findall("score-part"):
        pid = sp.get("id", "")
        # Primary: instrument-sound
        found = False
        for inst in sp.findall("score-instrument"):
            sound = inst.findtext("instrument-sound", "").lower()
            if sound.startswith(_VOICE_SOUND_PREFIX):
                vocal_ids.append(pid)
                found = True
                break
        if found:
            continue
        # Fallback: part-name / part-abbreviation
        name = sp.findtext("part-name", "")
        abbr = sp.findtext("part-abbreviation", "")
        if _VOCAL_NAME_RE.search(name) or _VOCAL_NAME_RE.search(abbr):
            vocal_ids.append(pid)

    if not vocal_ids:
        raise ValueError(
            f"No vocal part detected in {all_ids}. "
            "Add 'ssot': {'vocal_part_ids': ['P2']} to song.json "
            "or use --vocal-part-id."
        )

    backing_ids = [pid for pid in all_ids if pid not in vocal_ids]
    return vocal_ids, backing_ids


# ── Repeat / volta / jump expansion ──────────────────────────────────────────


def _parse_ending_nums(s: str) -> set[int]:
    """Parse '1', '1,2', or '1 2' into {1}, {1, 2}, etc."""
    nums: set[int] = set()
    for tok in re.split(r"[,\s]+", str(s)):
        if tok.strip().isdigit():
            nums.add(int(tok.strip()))
    return nums


def _collect_sound_info(measure: ET.Element) -> dict:
    """
    Collect playback-navigation attributes from all <direction><sound> elements.

    Returns a dict:
      segno     set[int]   segno markers defined at this measure
      coda_mark set[int]   coda section markers defined at this measure
      fine      bool       Fine marker
      dacapo    bool       Da Capo (go to measure 1)
      dalsegno  int|None   Dal Segno N
      tocoda    int|None   To Coda N (fires during the return pass)
    """
    info: dict = {
        "segno": set(),
        "coda_mark": set(),
        "fine": False,
        "dacapo": False,
        "dalsegno": None,
        "tocoda": None,
    }
    for direction in measure.findall("direction"):
        sound = direction.find("sound")
        if sound is None:
            continue
        seg = sound.get("segno", "").strip()
        if seg.isdigit():
            info["segno"].add(int(seg))
        cod = sound.get("coda", "").strip()
        if cod.isdigit():
            info["coda_mark"].add(int(cod))
        if sound.get("fine", "").strip().lower() in ("yes", "true", "1"):
            info["fine"] = True
        if sound.get("dacapo", "").strip().lower() in ("yes", "true", "1"):
            info["dacapo"] = True
        ds = sound.get("dalsegno", "").strip()
        if ds.isdigit():
            info["dalsegno"] = int(ds)
        tc = sound.get("tocoda", "").strip()
        if tc.isdigit():
            info["tocoda"] = int(tc)
    return info


def compute_play_sequence(measures: list[ET.Element]) -> list[tuple[int, int]]:
    """
    Return [(orig_measure_index, verse_pass), ...] in performance order.

    verse_pass is 1-indexed: which lyric verse applies to this occurrence.
    Each pass through a backward-repeated section increments the verse counter.

    Handles:
      - Forward / backward repeat barlines
      - Volta brackets (1st / 2nd / Nth endings)
      - D.C. al Fine, D.C. al Coda
      - D.S. al Fine, D.S. al Coda
      - Segno (𝄋) and Coda (𝄌) section markers
      - Fine

    Only one D.C./D.S. jump is followed per part; a second jump in the same
    pass is treated as a no-op (prevents infinite loops).
    """
    n = len(measures)

    # ── Pre-scan: barline events ─────────────────────────────────────────────
    infos: list[dict] = []
    for m in measures:
        info: dict = {
            "fwd": False,
            "bwd": False,
            "bwd_times": 2,
            "volta_start": set(),
            "volta_stop": set(),
        }
        for bl in m.findall("barline"):
            rep = bl.find("repeat")
            if rep is not None:
                d = rep.get("direction", "")
                if d == "forward":
                    info["fwd"] = True
                elif d == "backward":
                    info["bwd"] = True
                    t = rep.get("times")
                    info["bwd_times"] = int(t) if t and t.isdigit() else 2
            for e in bl.findall("ending"):
                nums = _parse_ending_nums(e.get("number", "1"))
                tp = e.get("type", "")
                if tp == "start":
                    info["volta_start"].update(nums)
                elif tp in ("stop", "discontinue"):
                    info["volta_stop"].update(nums)
        infos.append(info)

    # ── Pre-scan: direction / sound events ───────────────────────────────────
    sound_infos = [_collect_sound_info(m) for m in measures]

    # Build navigation target maps (first occurrence wins)
    segno_map: dict[int, int] = {}   # segno number → measure index
    coda_map: dict[int, int] = {}    # coda number  → measure index
    for idx, si in enumerate(sound_infos):
        for s in si["segno"]:
            segno_map.setdefault(s, idx)
        for c in si["coda_mark"]:
            coda_map.setdefault(c, idx)

    # ── Execution ────────────────────────────────────────────────────────────
    result: list[tuple[int, int]] = []
    stack: list[dict] = []   # repeat frames: {"start": int, "remaining": int|None}
    verse = 1
    jumped = False      # True after the first D.C./D.S. jump (prevents re-entry)
    in_return = False   # True during the return pass following a D.C./D.S. jump

    i = 0
    while i < n:
        info = infos[i]
        sound = sound_infos[i]

        # Push a repeat frame at a forward barline
        if info["fwd"] and (not stack or stack[-1]["start"] != i):
            stack.append({"start": i, "remaining": None})

        # Volta skip: if this measure opens a volta that doesn't match the current
        # verse, scan forward to skip the entire volta section.
        if info["volta_start"] and verse not in info["volta_start"]:
            target = info["volta_start"]
            j = i
            found = False
            while j < n:
                if infos[j]["volta_stop"] & target:
                    if infos[j]["bwd"] and stack:
                        stack.pop()
                    i = j + 1
                    found = True
                    break
                j += 1
            if not found:
                i = n
            continue

        # Include this measure in the performance sequence
        result.append((i, verse))

        # ── Backward repeat ──────────────────────────────────────────────────
        if info["bwd"] and stack:
            frame = stack[-1]
            if frame["remaining"] is None:
                frame["remaining"] = info["bwd_times"] - 1
            if frame["remaining"] > 0:
                frame["remaining"] -= 1
                verse += 1
                i = frame["start"]
                continue
            else:
                stack.pop()

        # ── Navigation (Fine / To Coda / D.C. / D.S.) ───────────────────────
        if in_return:
            # Fine: stop playback here (current measure was already included)
            if sound["fine"]:
                break

            # To Coda: jump to the coda section
            tc = sound["tocoda"]
            if tc is not None:
                coda_idx = coda_map.get(tc)
                if coda_idx is not None:
                    in_return = False
                    i = coda_idx
                    continue

        elif not jumped:
            # Da Capo: jump to measure 1
            if sound["dacapo"]:
                jumped = True
                in_return = True
                stack.clear()
                i = 0
                continue

            # Dal Segno: jump to the segno marker
            ds = sound["dalsegno"]
            if ds is not None:
                seg_idx = segno_map.get(ds)
                if seg_idx is not None:
                    jumped = True
                    in_return = True
                    stack.clear()
                    i = seg_idx
                    continue

        i += 1

    return result


# ── Barline / layout / navigation cleanup ─────────────────────────────────────


def _strip_repeat_barlines(measure: ET.Element) -> None:
    """Remove <repeat> and volta <ending> elements; clean up resulting empty barlines."""
    for bl in list(measure.findall("barline")):
        for rep in list(bl.findall("repeat")):
            bl.remove(rep)
        for e in list(bl.findall("ending")):
            bl.remove(e)
        # Remove bar-style that existed only to style a repeat barline
        bs = bl.find("bar-style")
        if bs is not None and bs.text in ("heavy-light", "light-heavy"):
            bl.remove(bs)
        if len(bl) == 0 and bl.get("location") in ("left", "right", None):
            measure.remove(bl)


def _strip_print_elements(measure: ET.Element) -> None:
    """Remove <print> elements (MuseScore layout info, irrelevant for synthesis)."""
    for p in list(measure.findall("print")):
        measure.remove(p)


def _strip_jump_sounds(measure: ET.Element) -> None:
    """
    Remove navigation sound attributes from expanded output.

    After repeat expansion the navigation attributes are meaningless in the
    linear output and can confuse players that honor them.  Remove only the
    navigation keys; preserve other sound attributes (tempo, dynamics, etc.).
    """
    for direction in list(measure.findall("direction")):
        sound = direction.find("sound")
        if sound is None:
            continue
        for attr in _JUMP_SOUND_ATTRS:
            sound.attrib.pop(attr, None)
        # Remove an empty sound element
        if not sound.attrib and len(sound) == 0:
            direction.remove(sound)
        # Remove a direction that contained only a navigation sound with no
        # direction-type children worth keeping (segno/coda symbol visuals)
        dt = direction.find("direction-type")
        if direction.find("sound") is None and dt is not None:
            nav_only = all(
                c.tag in {"segno", "coda"}
                or (
                    c.tag == "words"
                    and any(
                        kw in (c.text or "").lower()
                        for kw in ("d.c.", "d.s.", "fine", "coda", "segno", "al ")
                    )
                )
                for c in dt
            )
            if nav_only:
                measure.remove(direction)


# ── Note cleaning ─────────────────────────────────────────────────────────────


def _pitch_semitones(note: ET.Element) -> float:
    """Return the pitch of a note as a semitone value (higher = higher pitch)."""
    p = note.find("pitch")
    if p is None:
        return float("-inf")
    step_map = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    step = step_map.get(p.findtext("step", "C"), 0)
    octave = int(p.findtext("octave", "4"))
    alter = float(p.findtext("alter", "0") or "0")
    return octave * 12 + step + alter


def resolve_chords(measure: ET.Element) -> None:
    """
    Remove all but the top-pitch note from each chord cluster.
    A chord cluster is a group of consecutive notes where all but the first
    carry a <chord/> element.
    """
    notes = measure.findall("note")
    group: list[ET.Element] = []

    def _flush(g: list[ET.Element]) -> None:
        if len(g) > 1:
            top = max(g, key=_pitch_semitones)
            for n in g:
                if n is not top:
                    measure.remove(n)

    for note in notes:
        if note.find("chord") is not None:
            group.append(note)
        else:
            _flush(group)
            group = [note]
    _flush(group)


def remove_grace_notes(measure: ET.Element) -> None:
    """Remove grace notes (not meaningful for NEUTRINO synthesis)."""
    for note in list(measure.findall("note")):
        if note.find("grace") is not None:
            measure.remove(note)


# ── Slur repair ───────────────────────────────────────────────────────────────


def _has_slur(note: ET.Element, slur_num: int, stype: str) -> bool:
    notations = note.find("notations")
    if notations is None:
        return False
    return any(
        s.get("type") == stype and s.get("number") == str(slur_num)
        for s in notations.findall("slur")
    )


def _add_slur(note: ET.Element, slur_num: int, stype: str) -> None:
    """Append a slur start or stop to a note's notations (idempotent)."""
    if _has_slur(note, slur_num, stype):
        return
    notations = note.find("notations")
    if notations is None:
        notations = ET.SubElement(note, "notations")
    sl = ET.SubElement(notations, "slur")
    sl.set("type", stype)
    sl.set("number", str(slur_num))


def _pad_short_measures(expanded_measures: list[ET.Element]) -> None:
    """
    Prepend a rest to any expanded measure whose total note duration is less
    than what the current time signature requires.

    After repeat expansion, pickup (anacrusis) measures and their complementary
    last measures appear as incomplete measures in the middle of a linear score.
    musicXMLtoLabel warns "Duration of notes in a measure is too short" for each
    such occurrence, and NEUTRINO then fails with "The operation was canceled."
    Filling the gap with a leading rest lets musicXMLtoLabel treat every measure
    as full-length.
    """
    current_divisions = 4
    current_beats = 4
    current_beat_type = 4

    for measure in expanded_measures:
        attrs = measure.find("attributes")
        if attrs is not None:
            d = attrs.findtext("divisions")
            if d:
                current_divisions = int(d)
            b = attrs.findtext("time/beats")
            if b:
                current_beats = int(b)
            bt = attrs.findtext("time/beat-type")
            if bt:
                current_beat_type = int(bt)

        expected = int(current_divisions * current_beats * 4 / current_beat_type)
        total = sum(
            int(n.findtext("duration", "0"))
            for n in measure.findall("note")
            if n.find("chord") is None
        )

        if total >= expected or expected <= 0:
            continue

        gap = expected - total
        rest_note = ET.Element("note")
        ET.SubElement(rest_note, "rest")
        ET.SubElement(rest_note, "duration").text = str(gap)
        ET.SubElement(rest_note, "voice").text = "1"

        # Insert after any leading attributes/print/direction, before the first note
        insert_pos = 0
        for idx, child in enumerate(measure):
            if child.tag in ("attributes", "print", "direction"):
                insert_pos = idx + 1
            else:
                break
        measure.insert(insert_pos, rest_note)


def fix_slurs_across_rests(expanded_measures: list[ET.Element]) -> None:
    """
    Split slurs that cross rest notes.

    For each open slur that is interrupted by a rest:
      - Add <slur type="stop"> to the last sounding note before the rest.
      - Add <slur type="start"> to the first sounding note after the rest.
    The original <slur type="stop"> (wherever it falls) is left intact and
    now correctly terminates the resumed slur.
    """
    open_slurs: dict[int, ET.Element] = {}
    prev_sounding: ET.Element | None = None
    restart_needed: set[int] = set()

    for measure in expanded_measures:
        for note in measure.findall("note"):
            is_rest = note.find("rest") is not None

            if is_rest:
                if prev_sounding is not None:
                    for num in list(open_slurs):
                        _add_slur(prev_sounding, num, "stop")
                        restart_needed.add(num)
                open_slurs.clear()
                continue

            if restart_needed:
                notations = note.find("notations")
                if notations is None:
                    notations = ET.SubElement(note, "notations")
                for num in restart_needed:
                    _add_slur(note, num, "start")
                    open_slurs[num] = note
                restart_needed.clear()

            notations = note.find("notations")
            if notations is not None:
                for slur in notations.findall("slur"):
                    stype = slur.get("type")
                    try:
                        num = int(slur.get("number", "1"))
                    except ValueError:
                        continue
                    if stype == "start":
                        open_slurs[num] = note
                    elif stype == "stop":
                        open_slurs.pop(num, None)
                        restart_needed.discard(num)

            prev_sounding = note


# ── Lyric normalization ───────────────────────────────────────────────────────


def _is_rest(note: ET.Element) -> bool:
    return note.find("rest") is not None


def _is_tie_stop(note: ET.Element) -> bool:
    """Return True if the note is a tied-in continuation (no new lyric needed)."""
    return any(t.get("type") == "stop" for t in note.findall("tie"))


def _select_lyric(note: ET.Element, verse: int) -> ET.Element | None:
    """
    Choose the lyric element for this verse, falling back to verse 1
    when the requested verse is absent (e.g., non-repeated intro/coda).
    Returns None if no lyric elements exist at all.
    """
    lyrics = note.findall("lyric")
    if not lyrics:
        return None

    for l in lyrics:
        try:
            if int(l.get("number", "1")) == verse:
                return l
        except ValueError:
            pass

    # Fall back to verse 1
    for l in lyrics:
        try:
            if int(l.get("number", "1")) == 1:
                return l
        except ValueError:
            pass

    return lyrics[0]


def normalize_note_lyrics(note: ET.Element, verse: int) -> None:
    """
    For a sounding, non-tied note:
      1. Select the appropriate verse lyric (falling back to verse 1).
      2. Rename it to number="1".
      3. Strip punctuation from the lyric text.
      4. Replace empty or missing text with the dummy syllable.

    For rests and tied continuations: remove all lyrics.
    """
    if _is_rest(note) or _is_tie_stop(note):
        for l in list(note.findall("lyric")):
            note.remove(l)
        return

    chosen = _select_lyric(note, verse)

    for l in list(note.findall("lyric")):
        note.remove(l)

    if chosen is not None:
        chosen.set("number", "1")
        text_el = chosen.find("text")
        if text_el is not None and text_el.text:
            cleaned = _LYRIC_PUNCT_RE.sub("", text_el.text)
            text_el.text = cleaned if cleaned else _DUMMY_LYRIC
        else:
            if text_el is None:
                text_el = ET.SubElement(chosen, "text")
            text_el.text = _DUMMY_LYRIC
        note.append(chosen)
    else:
        lyric = ET.Element("lyric", number="1")
        ET.SubElement(lyric, "syllabic").text = "single"
        ET.SubElement(lyric, "text").text = _DUMMY_LYRIC
        note.append(lyric)


# ── Score builders ────────────────────────────────────────────────────────────


def _count_sounding_notes(part: ET.Element) -> int:
    return sum(
        1
        for m in part.findall("measure")
        for n in m.findall("note")
        if n.find("rest") is None and n.find("grace") is None
    )


def build_vocal_score(root: ET.Element, vocal_ids: list[str]) -> ET.Element:
    """
    Return a new score-partwise root containing only the vocal part(s),
    with repeats expanded and lyrics normalised for NEUTRINO synthesis.
    """
    tree = copy.deepcopy(root)

    # Trim <part-list>
    pl = tree.find("part-list")
    assert pl is not None
    for sp in list(pl.findall("score-part")):
        if sp.get("id") not in vocal_ids:
            pl.remove(sp)

    # Remove non-vocal <part> elements
    for part in list(tree.findall("part")):
        if part.get("id") not in vocal_ids:
            tree.remove(part)

    # Expand and clean each vocal part
    for part in tree.findall("part"):
        pid = part.get("id", "?")
        measures = part.findall("measure")
        if not measures:
            continue

        n_sounding = _count_sounding_notes(part)
        if n_sounding == 0:
            print(
                f"  [warn] Part {pid!r} has no sounding notes — "
                f"vocal.musicxml will contain only rests. "
                f"Add vocal notes to the SSoT file to use the full SSoT workflow."
            )

        play_seq = compute_play_sequence(measures)
        if not play_seq:
            print(f"  [warn] Empty play sequence for part {pid!r}; no measures emitted.")
            for m in list(part.findall("measure")):
                part.remove(m)
            continue

        # Build expanded copies
        expanded: list[tuple[ET.Element, int]] = []
        for orig_idx, verse_pass in play_seq:
            m = copy.deepcopy(measures[orig_idx])
            _strip_repeat_barlines(m)
            _strip_print_elements(m)
            _strip_jump_sounds(m)
            remove_grace_notes(m)
            resolve_chords(m)
            expanded.append((m, verse_pass))

        # Normalise lyrics on each expanded measure
        for m_elem, verse_pass in expanded:
            for note in m_elem.findall("note"):
                normalize_note_lyrics(note, verse_pass)

        # Pad pickup/complementary-last measures so every expanded measure fills
        # the full time-signature duration (prevents musicXMLtoLabel warnings).
        _pad_short_measures([m for m, _ in expanded])

        # Fix slurs that cross rests (operates on the expanded list in order)
        fix_slurs_across_rests([m for m, _ in expanded])

        # Replace original measures with expanded set
        for m in list(part.findall("measure")):
            part.remove(m)
        for i, (m_elem, _) in enumerate(expanded, start=1):
            m_elem.set("number", str(i))
            m_elem.attrib.pop("width", None)
            part.append(m_elem)

    return tree


def build_backing_score(root: ET.Element, vocal_ids: list[str]) -> ET.Element:
    """
    Return a new score-partwise root with vocal part(s) removed.

    Repeats are expanded (same play sequence as the vocal) and short measures
    are padded with the same _pad_short_measures pass, so the backing is a
    linear score whose total duration matches the vocal output exactly.
    music21/FluidSynth then processes the backing as a straightforward
    linear score with no repeat barlines.
    """
    tree = copy.deepcopy(root)

    pl = tree.find("part-list")
    assert pl is not None
    for sp in list(pl.findall("score-part")):
        if sp.get("id") in vocal_ids:
            pl.remove(sp)

    for part in list(tree.findall("part")):
        if part.get("id") in vocal_ids:
            tree.remove(part)

    # Expand repeats using the first backing part's structure.
    # All parts in a standard ensemble share the same repeat structure.
    backing_parts = tree.findall("part")
    if not backing_parts:
        return tree

    ref_measures = backing_parts[0].findall("measure")
    play_seq = compute_play_sequence(ref_measures) if ref_measures else []

    for part in backing_parts:
        measures = part.findall("measure")
        if not measures or not play_seq:
            continue

        expanded: list[ET.Element] = []
        for orig_idx, _verse_pass in play_seq:
            if orig_idx >= len(measures):
                continue
            m = copy.deepcopy(measures[orig_idx])
            _strip_repeat_barlines(m)
            _strip_print_elements(m)
            _strip_jump_sounds(m)
            expanded.append(m)

        _pad_short_measures(expanded)

        for m in list(part.findall("measure")):
            part.remove(m)
        for i, m_elem in enumerate(expanded, start=1):
            m_elem.set("number", str(i))
            m_elem.attrib.pop("width", None)
            part.append(m_elem)

    return tree


def inject_tempo(root: ET.Element, bpm: float) -> None:
    """
    Inject a <direction><sound tempo="N"/></direction> into the first measure of
    the first part, unless a <sound tempo> already exists anywhere in the score.

    music21 reads <sound tempo> for MIDI conversion; NEUTRINO's musicXMLtoLabel
    also honours it.  Without this, both default to 120 BPM regardless of the
    song.json bpm value, producing audio that is too fast.
    """
    # Skip if any tempo marking already present
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            for direction in measure.findall("direction"):
                sound = direction.find("sound")
                if sound is not None and sound.get("tempo"):
                    return

    first_part = root.find("part")
    if first_part is None:
        return
    first_measure = first_part.find("measure")
    if first_measure is None:
        return

    direction = ET.Element("direction")
    direction.set("placement", "above")
    dt = ET.SubElement(direction, "direction-type")
    metronome = ET.SubElement(dt, "metronome")
    metronome.set("parentheses", "no")
    ET.SubElement(metronome, "beat-unit").text = "quarter"
    ET.SubElement(metronome, "per-minute").text = str(int(bpm))
    sound = ET.SubElement(direction, "sound")
    sound.set("tempo", str(int(bpm)))

    # Insert after any leading <print> and <attributes> elements
    insert_pos = 0
    for idx, child in enumerate(first_measure):
        if child.tag in ("print", "attributes"):
            insert_pos = idx + 1
        else:
            break
    first_measure.insert(insert_pos, direction)


def _vocal_starts_with_notes(vocal_root: ET.Element) -> bool:
    """Return True when the vocal score's first measure contains sounding notes.

    Used to decide — once, from the vocal score — whether both vocal and backing
    need a prepended rest.  Keeping the decision in one place prevents the
    asymmetry that arises when vocal and backing have different first-measure
    content (e.g. koto-kouka: 10-measure piano intro means the vocal leads with
    rests while the backing leads with notes).
    """
    first_part = vocal_root.find("part")
    if first_part is None:
        return False
    first_m = first_part.find("measure")
    if first_m is None:
        return False
    return any(
        n.find("rest") is None and n.find("grace") is None
        for n in first_m.findall("note")
    )


def _prepend_leading_rest(root: ET.Element) -> None:
    """
    Unconditionally prepend a whole-measure rest to every part.

    Call this only after _vocal_starts_with_notes() has confirmed that a rest
    is needed.  Never call it independently on vocal and backing — both must
    receive the rest (or neither must), otherwise the two tracks are offset by
    one measure.
    """
    parts = root.findall("part")
    if not parts:
        return

    # Read divisions and beat count from the first attributes block
    first_m = parts[0].find("measure")
    divs, beats, beat_type = 4, 4, 4
    if first_m is not None:
        attrs_el = first_m.find("attributes")
        if attrs_el is not None:
            d = attrs_el.findtext("divisions")
            if d:
                divs = int(d)
            b = attrs_el.findtext("time/beats")
            if b:
                beats = int(b)
            bt = attrs_el.findtext("time/beat-type")
            if bt:
                beat_type = int(bt)

    # Duration of one full measure in MusicXML divisions
    # (divisions = quarter-note units, so adjust for non-quarter beat types)
    measure_duration = int(divs * beats * 4 / beat_type)

    for part in parts:
        part_first_m = part.find("measure")
        rest_m = ET.Element("measure")
        rest_m.set("number", "0")

        part_attrs = part_first_m.find("attributes") if part_first_m is not None else None
        if part_attrs is not None:
            rest_m.append(copy.deepcopy(part_attrs))

        rest_note = ET.SubElement(rest_m, "note")
        ET.SubElement(rest_note, "rest").set("measure", "yes")
        ET.SubElement(rest_note, "duration").text = str(measure_duration)
        ET.SubElement(rest_note, "voice").text = "1"

        part.insert(0, rest_m)

    # Re-number measures from 1
    for part in parts:
        for idx, m in enumerate(part.findall("measure"), start=1):
            m.set("number", str(idx))


# ── Variant-level tempo sync ──────────────────────────────────────────────────


def _sync_variant_tempo(root: ET.Element, bpm: float) -> bool:
    """
    Ensure the first <sound tempo> in the score equals `bpm`.
    Returns True if anything was changed.

    Unlike inject_tempo(), this OVERWRITES an existing tempo instead of
    skipping.  This is intentional: variant-level MusicXML overrides may have
    been exported from notation software with a stale or default BPM that
    disagrees with song.json.  song.json is the single source of truth.

    If no <sound tempo> exists, inject_tempo() is called to add one.
    """
    target = str(int(bpm))
    for part in root.findall("part"):
        for measure in part.findall("measure"):
            for direction in measure.findall("direction"):
                sound = direction.find("sound")
                if sound is not None and sound.get("tempo"):
                    if sound.get("tempo") == target:
                        return False  # already correct
                    sound.set("tempo", target)
                    dt = direction.find("direction-type")
                    if dt is not None:
                        metro = dt.find("metronome")
                        if metro is not None:
                            pm = metro.find("per-minute")
                            if pm is not None:
                                pm.text = target
                    return True
    # No tempo found — add one via the normal injection path
    inject_tempo(root, bpm)
    return True


# ── Output ────────────────────────────────────────────────────────────────────


def write_musicxml(root: ET.Element, path: Path) -> None:
    """Write root to path as UTF-8 MusicXML with a clean XML declaration."""
    ET.indent(root, space="  ")
    xml_body = ET.tostring(root, encoding="unicode")
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(xml_body)
        f.write("\n")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert an SSoT MusicXML into NEUTRINO vocal and backing parts."
    )
    ap.add_argument("--song", required=True, help="Song slug (subdirectory of projects/)")
    ap.add_argument(
        "--ssot",
        metavar="PATH",
        help="Path to SSoT MusicXML (default: projects/<song>/full.musicxml)",
    )
    ap.add_argument(
        "--vocal-part-id",
        action="append",
        dest="vocal_part_ids",
        metavar="ID",
        help="Part ID to treat as vocal (may repeat; overrides auto-detection and song.json)",
    )
    args = ap.parse_args()

    song_dir = PROJECTS_DIR / args.song
    if not song_dir.is_dir():
        print(f"ERROR: song directory not found: {song_dir}", file=sys.stderr)
        sys.exit(1)

    ssot_path = Path(args.ssot) if args.ssot else song_dir / "full.musicxml"
    if not ssot_path.exists():
        print(f"ERROR: SSoT file not found: {ssot_path}", file=sys.stderr)
        sys.exit(1)

    # Read optional song.json config
    song_json_path = song_dir / "song.json"
    config_vocal_ids: list[str] | None = None
    song_bpm: float | None = None
    if song_json_path.exists():
        with open(song_json_path, encoding="utf-8") as f:
            song_cfg = json.load(f)
        config_vocal_ids = song_cfg.get("ssot", {}).get("vocal_part_ids")
        bpm_raw = song_cfg.get("bpm")
        if bpm_raw is not None:
            try:
                song_bpm = float(bpm_raw)
            except (TypeError, ValueError):
                pass

    # CLI overrides song.json
    vocal_ids_override = args.vocal_part_ids or config_vocal_ids

    print(f"[convert-ssot] Parsing {ssot_path} ...")
    tree = ET.parse(str(ssot_path))
    root = tree.getroot()

    # Detect parts
    try:
        vocal_ids, backing_ids = detect_parts(root, vocal_ids_override)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[convert-ssot] Vocal: {vocal_ids}  Backing: {backing_ids}")

    # Vocal score
    print("[convert-ssot] Building vocal score ...")
    vocal_root = build_vocal_score(root, vocal_ids)

    # Decide whether a leading rest is needed by inspecting the VOCAL score only.
    # The same decision is then applied to the backing so both tracks share the
    # same t=0 offset.  An independent check per score causes asymmetry when the
    # vocal starts with rests (e.g. piano intro) but the backing starts with notes.
    needs_leading_rest = _vocal_starts_with_notes(vocal_root)
    if needs_leading_rest:
        _prepend_leading_rest(vocal_root)
    if song_bpm is not None:
        inject_tempo(vocal_root, song_bpm)
    vocal_out = song_dir / "vocal.musicxml"
    write_musicxml(vocal_root, vocal_out)
    print(f"[convert-ssot] -> {vocal_out}")

    # Backing score
    if backing_ids:
        print("[convert-ssot] Building backing score ...")
        backing_root = build_backing_score(root, vocal_ids)
        if needs_leading_rest:  # same decision as vocal — not an independent check
            _prepend_leading_rest(backing_root)
        if song_bpm is not None:
            inject_tempo(backing_root, song_bpm)
        inst_out = song_dir / "inst.musicxml"
        write_musicxml(backing_root, inst_out)
        print(f"[convert-ssot] -> {inst_out}")
    else:
        print("[convert-ssot] No backing parts — inst.musicxml not written.")

    # Sync tempo into any variant-level MusicXML overrides.
    # Variant dirs may contain hand-crafted or notation-exported inst.musicxml
    # files whose embedded BPM disagrees with song.json.  song.json is the
    # sole BPM source of truth; ensure all override files agree.
    if song_bpm is not None:
        variants_dir = song_dir / "variants"
        if variants_dir.is_dir():
            for vdir in sorted(variants_dir.iterdir()):
                if not vdir.is_dir():
                    continue
                for override_name in ("inst.musicxml", "vocal.musicxml"):
                    override_path = vdir / override_name
                    if not override_path.exists():
                        continue
                    v_root = ET.parse(str(override_path)).getroot()
                    if _sync_variant_tempo(v_root, song_bpm):
                        write_musicxml(v_root, override_path)
                        print(
                            f"[convert-ssot] tempo synced ({int(song_bpm)} BPM)"
                            f" -> {override_path}"
                        )

    print("[convert-ssot] Done.")


if __name__ == "__main__":
    main()
