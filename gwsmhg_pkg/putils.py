timestamp_re_str = '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{9} [-+]{1}\d{4})'
alt_timestamp_re_str = '([A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{2}:\d{2}:\d{2} \d{4} [-+]{1}\d{4})'
either_ts_re = '(%s|%s)' % (timestamp_re_str, alt_timestamp_re_str)
udiff_h1 = re.compile('^--- (.*?)(\s+%s)?$' % either_ts_re)
udiff_h2 = re.compile('^\+\+\+ (.*?)(\s+%s)?$' % either_ts_re)
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

        elif git_diff_starts_at(lines, i):
            patch_si = i
            patch_type = 'git'
            break
    comments = [line for line in parts[0] if line.startswith('#')]
    tmpf_name = _lines_to_temp_file(comments + lines + parts[1] + parts[2])
def _file_name_in_diffline(diffline):
    match = re.match('diff --git \w+/(.*) \w+/(.*)', diffline)
    if match:
        return match.group(1)
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