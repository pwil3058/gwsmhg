'''Provide functions for manipulating patch files and/or text buffers'''

import re
import os.path
import shutil
import tempfile

from gwsmhg_pkg import utils

_DIFFSTAT_EMPTY = re.compile("^#? 0 files changed$")
_DIFFSTAT_END = re.compile("^#? (\d+) files? changed(, (\d+) insertions?\(\+\))?(, (\d+) deletions?\(-\))?(, (\d+) modifications?\(\!\))?$")
_DIFFSTAT_FSTATS = re.compile("^#? (\S+)\s*\|((binary)|(\s*(\d+)(\s+\+*-*\!*)?))$")

_TIMESTAMP_RE_STR = '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{9} [-+]{1}\d{4})'
_ALT_TIMESTAMP_RE_STR = '([A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2} \d{4} [-+]{1}\d{4})'
_EITHER_TS_RE = '(%s|%s)' % (_TIMESTAMP_RE_STR, _ALT_TIMESTAMP_RE_STR)
_UDIFF_H1 = re.compile('^--- (.*?)(\s+%s)?$' % _EITHER_TS_RE)
_UDIFF_H2 = re.compile('^\+\+\+ (.*?)(\s+%s)?$' % _EITHER_TS_RE)
_UDIFF_PD = re.compile("^@@\s+-(\d+),(\d+)\s+\+(\d+),(\d+)\s+@@\s*(.*)$")

_GIT_HDR_DIFF = re.compile("^diff --git (.*)$")
_GIT_OLD_MODE = re.compile('^old mode (\d*)$')
_GIT_NEW_MODE = re.compile('^new mode (\d*)$')
_GIT_DELETED_FILE_MODE = re.compile('^deleted file mode (\d*)$')
_GIT_NEW_FILE_MODE = re.compile('^new file mode (\d*)$')
_GIT_COPY_FROM = re.compile('^copy from (.*)$')
_GIT_COPY_TO = re.compile('^copy to (.*)$')
_GIT_RENAME_FROM = re.compile('^rename from (.*)$')
_GIT_RENAME_TO = re.compile('^rename to (.*)$')
_GIT_SIMILARITY_INDEX = re.compile('^similarity index (\d*)%$')
_GIT_DISSIMILARITY_INDEX = re.compile('^dissimilarity index (\d*)%$')
_GIT_INDEX = re.compile('^index ([a-fA-F0-9]+)..([a-fA-F0-9]+) (\d*)%$')

_GIT_EXTRAS = \
    _GIT_OLD_MODE, _GIT_NEW_MODE, _GIT_DELETED_FILE_MODE, _GIT_NEW_FILE_MODE,
    _GIT_COPY_FROM, _GIT_COPY_TO, _GIT_RENAME_FROM, _GIT_RENAME_TO,
    _GIT_SIMILARITY_INDEX, _GIT_DISSIMILARITY_INDEX, _GIT_INDEX
_CDIFF_H1 = re.compile("^\*\*\* (\S+)\s*(.*)$")
_CDIFF_H2 = re.compile("^--- (\S+)\s*(.*)$")
_CDIFF_H3 = re.compile("^\*+$")
_CDIFF_CHG = re.compile("^\*+\s+(\d+),(\d+)\s+\*+\s*(.*)$")
_CDIFF_DEL = re.compile("^-+\s+(\d+),(\d+)\s+-+\s*(.*)$")

_HDR_INDEX = re.compile("^Index:\s+(.*)$")
_HDR_DIFF = re.compile("^diff\s+(.*)$")
_HDR_SEP = re.compile("^==*$")
_HDR_RCS1 = re.compile("^RCS file:\s+(.*)$")
_HDR_RCS2 = re.compile("^retrieving revision\s+(\d+(\.\d+)*)$")

_BLANK_LINE = re.compile("^\s*$")
_DIVIDER_LINE = re.compile("^---$")

def _udiff_starts_at(lines, i):
    """
    Return whether the ith line in lines is the start of a unified diff

    Arguments:
    lines -- the list of lines to be examined
    i     -- the line number to be examined
    """
    if not _UDIFF_H1.match(lines[i]):
    if not _UDIFF_H2.match(lines[i + 1]):
    return _UDIFF_PD.match(lines[i + 2])

def _is_git_extra_line(line):
    """
    Return whether the line is a git diff "extra" line
    Argument:
    line -- theline to be examined
    """
    for regex in _GIT_EXTRAS:
def _git_diff_starts_at(lines, i):
    """
    Return whether the ith line in lines is the start of a git diff

    Arguments:
    lines -- the list of lines to be examined
    i     -- the line number to be examined
    """
    if i < len(lines) and _GIT_HDR_DIFF.match(lines[i]):
    while i < len(lines) and _is_git_extra_line(lines[i]):
        return _udiff_starts_at(lines, i)
        return _GIT_HDR_DIFF.match(lines[i]) or _udiff_starts_at(lines, i)
def _cdiff_starts_at(lines, i):
    """
    Return whether the ith line in lines is the start of a combined diff

    Arguments:
    lines -- the list of lines to be examined
    i     -- the line number to be examined
    """
    if not _CDIFF_H1.match(lines[i]):
    if not _CDIFF_H2.match(lines[i + 1]):
    if not _CDIFF_H3.match(lines[i + 2]):
    return _CDIFF_CHG.match(lines[i + 3]) or  _CDIFF_DEL.match(lines[i + 3])

def _trisect_patch_lines(lines):
    """
    Return indices splitting lines into comments, stats and diff parts

    Arguments:
    lines -- the list of lines to be trisected
    Return a two tuple indicating start of stats and diff parts.
    For stats part provide integer index of first stats line or None if
    the stats part is not present.
    For diff part provide a two tuple (index of first diff line, diff type)
    or None if the diff part is not present.
    """
        if _DIFFSTAT_EMPTY.match(lines[i]):
        elif _DIFFSTAT_FSTATS.match(lines[i]):
            while (i + k) < n and _DIFFSTAT_FSTATS.match(lines[i + k]):
            if (i + k) < n and _DIFFSTAT_END.match(lines[i + k]):
        elif _git_diff_starts_at(lines, i):
        elif _HDR_INDEX.match(lines[i]) or _HDR_DIFF.match(lines[i]):
            if k < n and _HDR_SEP.match(lines[k]):
            if _udiff_starts_at(lines, k):
            elif _cdiff_starts_at(lines, k):
        elif _HDR_RCS1.match(lines[i]):
            if (i + 1) < n and _HDR_RCS2.match(lines[i]):
                if k < n and _HDR_SEP.match(lines[k]):
                if _udiff_starts_at(lines, k):
                elif _cdiff_starts_at(lines, k):
        elif _udiff_starts_at(lines, i):
        elif _cdiff_starts_at(lines, i):
        elif not (_BLANK_LINE.match(lines[i]) or _DIVIDER_LINE.match(lines[i])):
def _trisect_patch_file(path):
    except IOError:
    diffstat_si, patch = _trisect_patch_lines(lines)
    return (True,  res)
    except IOError:
    diffstat_si, patch = _trisect_patch_lines(lines)
def get_patch_diff_fm_text(textbuf):
    lines = textbuf.splitlines()
    _, patch = _trisect_patch_lines(lines)
        return (False, '')
    return (True, os.linesep.join(lines[patch[0]:]) + os.linesep)
def get_patch_diff(path, file_list=None):
        try:
            f = open(path, 'r')
        except IOError:
            return (False, None)
        buf = f.read()
        f.close()
        return get_patch_diff_fm_text(buf)
    for filename in file_list:
        cmd += " -i %s" % filename
    res, sout, serr = utils.run_cmd("%s %s" % (cmd, path))
        return (True, sout)
        return (False, sout + serr)
def _append_lines_to_file(f, lines):
        f.write(line + os.linesep)
def _strip_trailing_ws(lines):
        _append_lines_to_file(tmpf, lines)
    except IOError:
        res, parts = _trisect_patch_file(path)
    except IOError:
def _rediff_lines(lines, orig_lines=None):
    if orig_lines and len(orig_lines):
        res, sout, _ = utils.run_cmd("rediff %s" % lines_tf)
        res, sout, _ = utils.run_cmd("rediff %s %s" % (orig_lines_tf, lines_tf))
        return sout.splitlines()
        res, parts = _trisect_patch_file(path)
    lines = _rediff_lines(lines, orig_lines=parts[2])
    except IOError:
    assert _GIT_HDR_DIFF.match(lines[i])
        match_data = _is_git_extra_line(lines[i])
        if regex is _GIT_COPY_FROM:
        elif regex is _GIT_COPY_TO:
        elif regex is _GIT_RENAME_FROM:
        elif regex is _GIT_RENAME_TO:
        elif regex is _GIT_NEW_FILE_MODE:
        elif regex is _GIT_DELETED_FILE_MODE:
            match = _UDIFF_H1.match(lines[i])
    while i < len(lines) and not _GIT_HDR_DIFF.match(lines[i]):
        match = _UDIFF_H2.match(lines[i])
def _get_git_diff_files(lines, i):
        while i < len(lines) and not _git_diff_starts_at(lines, i):
def _get_unified_diff_files(lines, i):
        match1 = _UDIFF_H1.match(lines[i])
            match2 = _UDIFF_H2.match(lines[i])
def _get_combined_diff_files(lines, i):
    while i < len(lines):
        pass
    except IOError:
    _, patch = _trisect_patch_lines(lines)
        files = _get_git_diff_files(lines, patch[0])
        files = _get_unified_diff_files(lines, patch[0])
        files = _get_combined_diff_files(lines, patch[0])