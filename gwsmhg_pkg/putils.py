# -*- python -*-

### Copyright (C) 2005 Peter Williams <peter_ono@users.sourceforge.net>

### This program is free software; you can redistribute it and/or modify
### it under the terms of the GNU General Public License as published by
### the Free Software Foundation; version 2 of the License only.

### This program is distributed in the hope that it will be useful,
### but WITHOUT ANY WARRANTY; without even the implied warranty of
### MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
### GNU General Public License for more details.

### You should have received a copy of the GNU General Public License
### along with this program; if not, write to the Free Software
### Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# This file provides functions for manipulating patch files

import re, os.path, shutil, tempfile, utils

diffstat_empty = re.compile("^#? 0 files changed$")
diffstat_end = re.compile("^#? (\d+) files? changed(, (\d+) insertions?\(\+\))?(, (\d+) deletions?\(-\))?(, (\d+) modifications?\(\!\))?$")
diffstat_fstats = re.compile("^#? (\S+)\s*\|((binary)|(\s*(\d+)(\s+\+*-*\!*)?))$")

timestamp_re_str = '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{9} [-+]{1}\d{4})'
alt_timestamp_re_str = '([A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2} \d{4} [-+]{1}\d{4})'
either_ts_re = '(%s|%s)' % (timestamp_re_str, alt_timestamp_re_str)
udiff_h1 = re.compile('^--- (.*?)(\s+%s)?$' % either_ts_re)
udiff_h2 = re.compile('^\+\+\+ (.*?)(\s+%s)?$' % either_ts_re)
udiff_pd = re.compile("^@@\s+-(\d+),(\d+)\s+\+(\d+),(\d+)\s+@@\s*(.*)$")

git_hdr_diff = re.compile("^diff --git (.*)$")
git_old_mode = re.compile('^old mode (\d*)$')
git_new_mode = re.compile('^new mode (\d*)$')
git_deleted_file_mode = re.compile('^deleted file mode (\d*)$')
git_new_file_mode = re.compile('^new file mode (\d*)$')
git_copy_from = re.compile('^copy from (.*)$')
git_copy_to = re.compile('^copy to (.*)$')
git_rename_from = re.compile('^rename from (.*)$')
git_rename_to = re.compile('^rename to (.*)$')
git_similarity_index = re.compile('^similarity index (\d*)%$')
git_dissimilarity_index = re.compile('^dissimilarity index (\d*)%$')
git_index = re.compile('^index ([a-fA-F0-9]+)..([a-fA-F0-9]+) (\d*)%$')

git_extras = \
[
    git_old_mode, git_new_mode, git_deleted_file_mode, git_new_file_mode,
    git_copy_from, git_copy_to, git_rename_from, git_rename_to,
    git_similarity_index, git_dissimilarity_index, git_index
]

cdiff_h1 = re.compile("^\*\*\* (\S+)\s*(.*)$")
cdiff_h2 = re.compile("^--- (\S+)\s*(.*)$")
cdiff_h3 = re.compile("^\*+$")
cdiff_chg = re.compile("^\*+\s+(\d+),(\d+)\s+\*+\s*(.*)$")
cdiff_del = re.compile("^-+\s+(\d+),(\d+)\s+-+\s*(.*)$")

hdr_index = re.compile("^Index:\s+(.*)$")
hdr_diff = re.compile("^diff\s+(.*)$")
hdr_sep = re.compile("^==*$")
hdr_rcs1 = re.compile("^RCS file:\s+(.*)$")
hdr_rcs2 = re.compile("^retrieving revision\s+(\d+(\.\d+)*)$")

blank_line = re.compile("^\s*$")
divider_line = re.compile("^---$")

def udiff_starts_at(lines, i):
    if (i + 2) >= len(lines):
        return False
    if not udiff_h1.match(lines[i]):
        return False
    if not udiff_h2.match(lines[i + 1]):
        return False
    return udiff_pd.match(lines[i + 2])

def is_git_extra_line(line):
    for regex in git_extras:
        match = regex.match(line)
        if match:
            return (regex, match)
    return False

def git_diff_starts_at(lines, i):
    if i < len(lines) and git_hdr_diff.match(lines[i]):
        i += 1
    else:
        return False
    extra_count = 0
    while i < len(lines) and is_git_extra_line(lines[i]):
        i += 1
        extra_count += 1
    if extra_count == 0:
        return udiff_starts_at(lines, i)
    elif i < len(lines):
        return git_hdr_diff.match(lines[i]) or udiff_starts_at(lines, i)
    else:
        return True

def cdiff_starts_at(lines, i):
    if (i + 3) >= len(lines):
        return False
    if not cdiff_h1.match(lines[i]):
        return False
    if not cdiff_h2.match(lines[i + 1]):
        return False
    if not cdiff_h3.match(lines[i + 2]):
        return False
    return cdiff_chg.match(lines[i + 3]) or  cdiff_del.match(lines[i + 3])

def trisect_patch_lines(lines):
    n = len(lines)
    patch_type = None
    patch_si = None
    diffstat_si = None
    i = 0
    while i < n:
        if diffstat_empty.match(lines[i]): 
            diffstat_si = i
        elif diffstat_fstats.match(lines[i]):
            k = 1
            while (i + k) < n and diffstat_fstats.match(lines[i + k]):
                k += 1
            if (i + k) < n and diffstat_end.match(lines[i + k]):
                diffstat_si = i
                i += k
            else:
                diffstat_si = None
                i += k - 1
        elif git_diff_starts_at(lines, i):
            patch_si = i
            patch_type = 'git'
            break
        elif hdr_index.match(lines[i]) or hdr_diff.match(lines[i]):
            k = i + 1
            if k < n and hdr_sep.match(lines[k]):
                k += 1
            if udiff_starts_at(lines, k):
                patch_si = i
                patch_type = "u"
                break
            elif cdiff_starts_at(lines, k):
                patch_si = i
                patch_type = "c"
                break
            else:
                i = k
                diffstat_si = None
        elif hdr_rcs1.match(lines[i]):
            if (i + 1) < n and hdr_rcs2.match(lines[i]):
                k = i + 1
                if k < n and hdr_sep.match(lines[k]):
                    k += 1
                if udiff_starts_at(lines, k):
                    patch_si = i
                    patch_type = "u"
                    break
                elif cdiff_starts_at(lines, k):
                    patch_si = i
                    patch_type = "c"
                    break
                else:
                    i = k
                    diffstat_si = None
            else:
                diffstat_si = None
        elif udiff_starts_at(lines, i):
            patch_si = i
            patch_type = "u"
            break
        elif cdiff_starts_at(lines, i):
            patch_si = i
            patch_type = "c"
            break
        elif not (blank_line.match(lines[i]) or divider_line.match(lines[i])):
            diffstat_si = None
        i += 1
    if patch_si is None:
        return (diffstat_si, None)
    else:
        return (diffstat_si, (patch_si, patch_type))

def trisect_patch_file(path):
    try:
        f = open(path, 'r')
    except:
        return (False, (None, None, None))
    buf = f.read()
    f.close()
    lines = buf.splitlines()
    diffstat_si, patch = trisect_patch_lines(lines)
    if patch is None:
        if diffstat_si is None:
            res = (lines, [], [])
        else:
            res = (lines[0:diffstat_si], lines[diffstat_si:], [])
    else:
        plines = lines[patch[0]:]
        if diffstat_si is None:
            res = (lines[:patch[0]], [], plines)
        else:
            res = (lines[0:diffstat_si], lines[diffstat_si:patch[0]], plines)
    return ( True,  res)

def get_patch_descr_lines(path):
    try:
        f = open(path, 'r')
    except:
        return (False, None)
    buf = f.read()
    lines = buf.splitlines()
    f.close()
    diffstat_si, patch = trisect_patch_lines(lines)
    if diffstat_si is None:
        if patch is None:
            res = lines
        else:
            res = lines[0:patch[0]]
    else:
        res = lines[0:diffstat_si]
    return ( True,  res)

def get_patch_diff_lines(path):
    try:
        f = open(path, 'r')
    except:
        return (False, None)
    buf = f.read()
    lines = buf.splitlines()
    f.close()
    diffstat_si, patch = trisect_patch_lines(lines)
    if patch is None:
        return (False, [])
    return (True,  lines[patch[0]:])

def get_patch_diff(path, file_list=[]):
    if not file_list:
        res, diff_lines = get_patch_diff_lines(path)
        return (res, os.linesep.join(diff_lines) + os.linesep)
    if not utils.which("filterdiff"):
        return (False, "This functionality requires \"filterdiff\" from \"patchutils\"")
    cmd = "filterdiff -p 1"
    for file in file_list:
        cmd += " -i %s" % file
    res, so, se = utils.run_cmd("%s %s" % (cmd, path))
    if res == 0:
        return (True, so)
    else:
        return (False, so + se)

def append_lines_to_file(file, lines):
    for line in lines:
        file.write(line + os.linesep)

def strip_trailing_ws(lines):
    n = len(lines)
    i = 0
    while i < n:
        lines[i] = lines[i].rstrip()
        i += 1

def _lines_to_temp_file(lines):
    try:
        tmpf_name = tempfile.mktemp()
        tmpf = open(tmpf_name, 'w')
        append_lines_to_file(tmpf, lines)
        tmpf.close()
    except:
        if tmpf_name is not None and os.path.exists(tmpf_name):
            os.remove(tmpf_name)
        return ""
    return tmpf_name

def set_patch_descr_lines(path, lines):
    if os.path.exists(path):
        res, parts = trisect_patch_file(path)
        if not res:
            return False
    else:
        parts = ([], [], [])
    comments = [line for line in parts[0] if line.startswith('#')]
    tmpf_name = _lines_to_temp_file(comments + lines + parts[1] + parts[2])
    if not tmpf_name:
        return False
    try:
        shutil.copyfile(tmpf_name, path)
        ret = True
    except:
        ret = False
    os.remove(tmpf_name)
    return ret

def rediff_lines(lines, orig_lines=[]):
    if not utils.which("rediff"):
        return lines
    lines_tf = _lines_to_temp_file(lines)
    if not lines_tf:
        return lines
    if len(orig_lines):
        orig_lines_tf = _lines_to_temp_file(orig_lines)
    else:
        orig_lines_tf = None
    if not orig_lines_tf:
        res, so, se = utils.run_cmd("rediff %s" % lines_tf)
    else:
        res, so, se = utils.run_cmd("rediff %s %s" % (orig_lines_tf, lines_tf))
        os.remove(orig_lines_tf)
    os.remove(lines_tf)
    if res == 0:
        return so.splitlines()
    else:
        return lines

def set_patch_diff_lines(path, lines):
    if os.path.exists(path):
        res, parts = trisect_patch_file(path)
        if not res:
            return False
    else:
        parts = ([], [], [])
    lines = rediff_lines(lines, orig_lines=parts[2])
    tmpf_name = _lines_to_temp_file(parts[0] + parts[1] + lines)
    if not tmpf_name:
        return False
    try:
        shutil.copyfile(tmpf_name, path)
        ret = True
    except:
        ret = False
    os.remove(tmpf_name)
    return ret

ADDED = "A"
EXTANT = "M"
DELETED = "R"

def _file_name_in_diffline(diffline):
    match = re.match('diff --git \w+/(.*) \w+/(.*)', diffline)
    if match:
        return match.group(1)
    else:
        return None

def _get_git_diff_file_data(lines, i):
    assert git_hdr_diff.match(lines[i])
    diffline = lines[i]
    i += 1
    new_file = False
    deleted_file = False
    copy_from = None
    copy_to = None
    rename_from = None
    rename_to = None
    while i < len(lines):
        match_data = is_git_extra_line(lines[i])
        if not match_data:
            break
        else:
            i += 1
            regex, match = match_data
        if regex is git_copy_from:
            copy_from = match.group(1)
        elif regex is git_copy_to:
            copy_to = match.group(1)
        elif regex is git_rename_from:
            rename_from = match.group(1)
        elif regex is git_rename_to:
            rename_from = match.group(1)
        elif regex is git_new_file_mode:
            new_file = True
        elif regex is git_deleted_file_mode:
            deleted_file = True
    if copy_to:
        return [i, [(copy_to, ADDED, copy_from)]]
    if rename_to:
        return [i, [(rename_to, ADDED, rename_from), (rename_from, DELETED, None)]]
    if deleted_file:
        while i < len(lines):
            match = udiff_h1.match(lines[i])
            i += 1
            if match:
                filename = match.group(1)[2:]
                return [i, [(filename, DELETED, None)]]
    while i < len(lines) and not git_hdr_diff.match(lines[i]):
        match = udiff_h2.match(lines[i])
        i += 1
        if match:
            filename = match.group(1)[2:]
            if new_file:
                return [i, [(filename, ADDED, None)]]
            else:
                return [i, [(filename, EXTANT, None)]]
    filename = _file_name_in_diffline(diffline)
    if new_file:
        return (i, [[filename, ADDED, None]])
    else:
        return (i, [[filename, EXTANT, None]])

def get_git_diff_files(lines, i):
    files = []
    while i < len(lines):
        i, files_data = _get_git_diff_file_data(lines, i)
        files += files_data
        while i < len(lines) and not git_diff_starts_at(lines, i):
            i += 1
    return files

def get_unified_diff_files(lines, i):
    files = []
    while i < len(lines):
        match1 = udiff_h1.match(lines[i])
        i += 1
        if match1:
            match2 = udiff_h2.match(lines[i])
            i += 1
            file1 = match1.group(1)
            if file1 == '/dev/null':
                files.append((match2.group(1).split('/', 1)[1], ADDED, None))
            else:
                file2 = match2.group(1)
                if file2 == '/dev/null' :
                    files.append((file1.split('/', 1)[1], DELETED, None))
                else:
                    files.append((file2.split('/', 1)[1], EXTANT, None))
    return files

def get_combined_diff_files(lines, i):
    files = []
    return files

def get_patch_files(path, status=True, decorated=False):
    try:
        f = open(path, 'r')
    except:
        return (False, 'Problem(s) open file "%s" not found' % path)
    buf = f.read()
    f.close()
    lines = buf.splitlines()
    diffstat_si, patch = trisect_patch_lines(lines)
    if patch is None:
        return (True, [])
    if patch[1] == 'git':
        files = get_git_diff_files(lines, patch[0])
    elif patch[1] == 'u':
        files = get_unified_diff_files(lines, patch[0])
    else:
        files = get_combined_diff_files(lines, patch[0])
    if decorated:
        filelist = []
        for file_data in files:
            filelist.append(' '.join([file_data[1], file_data[0]]))
            if file_data[1] == ADDED and file_data[2]:
                filelist.append('  %s' % file_data[2])
        return (True, filelist)
    elif status:
        return (True, files)
    return (True, [file_data[0] for file_data in files])
