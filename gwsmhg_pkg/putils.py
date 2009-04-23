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

udiff_h1 = re.compile("^--- (\S+)\s*(.*)$")
udiff_h2 = re.compile("^\+\+\+ (\S+)\s*(.*)$")
udiff_pd = re.compile("^@@\s+-(\d+),(\d+)\s+\+(\d+),(\d+)\s+@@\s*(.*)$")

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
    tmpf_name = _lines_to_temp_file(lines + parts[1] + parts[2])
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

def get_patch_files(path, status=True):
    if not utils.which("lsdiff"):
        return (False, "This functionality requires \"lsdiff\" from \"patchutils\"")
    cmd = "lsdiff --strip=1"
    if not status:
        res, so, se = utils.run_cmd("%s %s" % (cmd, path))
        if res == 0:
            return (True, so.splitlines())
        else:
            return (False, so + se)
    else:
        res, so, se = utils.run_cmd("%s -s %s" % (cmd, path))
        if res == 0:
            filelist = []
            for line in so.splitlines():
                if line[0] == "+":
                    filelist.append((line[2:], ADDED, None))
                elif line[0] == "-":
                    filelist.append((line[2:], DELETED, None))
                else:
                    filelist.append((line[2:], EXTANT, None))
            return (True, filelist)
        else:
            return (False, so + se)

