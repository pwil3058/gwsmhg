### Copyright (C) 2009 Peter Williams <peter_ono@users.sourceforge.net>

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

ALWAYS_AVAILABLE = "gwsm_always_avail"
IN_VALID_SCM_REPO = "gwsm_in_valid_repo"
NOT_IN_VALID_SCM_REPO = "gwsm_not_in_valid_repo"
IN_VALID_SCM_REPO_NOT_PMIC = "gwsm_in_valid_repo_not_pmic"

GWSM_CONDITIONS = [ALWAYS_AVAILABLE,
                   IN_VALID_SCM_REPO,
                   NOT_IN_VALID_SCM_REPO,
                   IN_VALID_SCM_REPO_NOT_PMIC,
                  ]

NO_SELECTION = "sel_none"
UNIQUE_SELECTION = "sel_unique"
SELECTION = "sel_made"
SELECTION_INDIFFERENT = "sel_indifferent"

NO_SELECTION_NOT_PMIC = "sel_none_not_patched"
SELECTION_NOT_PMIC = "sel_made_not_patched"

FILE_CONDITIONS = [NO_SELECTION,
                   UNIQUE_SELECTION,
                   SELECTION,
                   SELECTION_INDIFFERENT,
                   NO_SELECTION_NOT_PMIC,
                   SELECTION_NOT_PMIC,
                  ]

