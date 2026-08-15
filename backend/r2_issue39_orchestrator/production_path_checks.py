"""No-follow regular-file and plain-directory predicates."""

import stat


def regular_file(path):
    try:
        value = path.lstat()
        return stat.S_ISREG(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & 0x400
        ) and not path.is_symlink()
    except OSError:
        return False


def plain_directory(path):
    try:
        value = path.lstat()
        return stat.S_ISDIR(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & 0x400
        ) and not path.is_symlink() and not path.is_junction()
    except OSError:
        return False
