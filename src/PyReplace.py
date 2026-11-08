# Copyright (C) 2018-2026 by xcentaurix
# License: GNU General Public License v3.0
#
# The python files of a plugin (<plugin directory>/<dir>/<file>.py, also of a directory in a directory, the "skin" directory excepted) replace the
# files of enigma2 (/usr/lib/enigma2/python/<dir>/<file>.py). This module puts the files in place and puts the originals back. It uses the
# standard library only, so that it runs from the postinst/prerm of the package as well as from the plugin, which has to be the directory that the
# plugin is installed to (this file is copied to it):
#
#     python3 PyReplace.py sync       the files of the plugin are in place, the originals are saved
#     python3 PyReplace.py restore    the originals are back
#     (--legacy-marker TEXT: see below)
#
# The rule: a saved original is only valid as long as the file in enigma2 is the one that this module has put there. The hash of every file that
# is put in place is kept (<state directory>/state.json), and a file with another hash is not ours, it is an original: the image's own, or a newer
# one that an update of enigma2 has installed in the meantime. So
#   - sync saves a file that is not ours as the original (a saved older one is replaced), then puts ours in place;
#   - restore puts the saved original back only if the file is still ours; a file that enigma2 has replaced is the original already and is left
#     alone. The saved originals are deleted in both cases, they are never kept for a later install.
#
# An image that has the .py of a file gets the .py of the plugin (a .py is used before a .pyc of the same name). An image that has only the .pyc
# gets the file compiled to a .pyc, no .py (compiled here, by the python of the box, so it is of the right version; like PluginUpgrade.compilePY
# does, which can't be used here as it needs enigma2). A file with an error is not put in place.
#
# Where the state is lost (or there never was one: earlier versions of the plugins kept the originals as <file>.py.org and <file>.pyc.org) a file
# is ours if it is the file of the plugin (the .pyc as compiled from it), or contains one of the legacy markers (--legacy-marker, a text that is
# in the files of earlier versions of the plugin and not in the ones of enigma2). The .org files are taken over as the originals if the file is
# ours, they are stale otherwise (enigma2 has replaced the file since) and deleted.

import hashlib
import json
import logging
import os
import shutil
import sys
from importlib.util import MAGIC_NUMBER
from marshal import dumps

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.basename(PLUGIN_DIR)
ENIGMA2_DIR = "/usr/lib/enigma2/python"
STATE_DIR = os.path.join("/usr/share/enigma2", PLUGIN)
STATE = os.path.join(STATE_DIR, "state.json")
EXCLUDED_DIRS = ("skin", "__pycache__")

try:
    from .Version import ID  # the logger of the plugin (Debug.py)
except ImportError:  # run as a script
    ID = PLUGIN

logger = logging.getLogger(ID)


def _read(path):
    with open(path, "rb") as file:
        return file.read()


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "wb") as file:
        file.write(data)
    os.replace(temp, path)  # python reads a complete file, the old one or the new one


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _path(name):
    return os.path.join(ENIGMA2_DIR, name)


def _orig(name):
    return os.path.join(STATE_DIR, "orig", name + ".orig")


def _sourceName(name):
    """The .py of the plugin that a file of enigma2 (a .py or a .pyc) is made from."""
    return name[:-1] if name.endswith(".pyc") else name


def _removeFile(path):
    if os.path.isfile(path):
        os.remove(path)


def pluginPYs():
    """The python files of the plugin that are meant for enigma2: the relative paths (<dir>/<file>.py), the skin excepted."""
    pys = []
    for base, directories, files in os.walk(PLUGIN_DIR):
        directories[:] = sorted(d for d in directories if d not in EXCLUDED_DIRS)
        if base != PLUGIN_DIR:  # the .py files in the plugin directory itself are the plugin's own
            pys += [os.path.relpath(os.path.join(base, name), PLUGIN_DIR).replace(os.sep, "/") for name in sorted(files) if name.endswith(".py")]
    return pys


def _loadState():
    """name (<dir>/<file>.py or .pyc) -> {"sha", "source", "magic"} of the files that were put in place."""
    try:
        with open(STATE, encoding="utf-8") as file:
            files = json.load(file).get("files")
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(files, dict):
        return {}
    return {name: record for name, record in files.items() if isinstance(record, dict) and "sha" in record}


def _saveState(files):
    _write(STATE, json.dumps({"files": files}, indent=1, sort_keys=True).encode("utf-8"))


def _code(source, filename):
    return compile(_read(source), filename, "exec", dont_inherit=True)


def _pyc(code, source):
    """The bytes of a .pyc: magic number, flags, time and size of the source, the code."""
    info = os.stat(source)
    return MAGIC_NUMBER + (0).to_bytes(4, "little") + (int(info.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little") + (info.st_size & 0xFFFFFFFF).to_bytes(4, "little") + dumps(code)


def _isOurs(name, files, markers):
    """The file in enigma2 is the one that was put there. Without a record the content tells."""
    data = _read(_path(name))
    if name in files:
        return _sha(data) == files[name]["sha"]
    if any(marker in data for marker in markers):
        return True
    source = os.path.join(PLUGIN_DIR, _sourceName(name))
    if not os.path.isfile(source):
        return False
    if name.endswith(".pyc"):
        try:
            return data == _pyc(_code(source, _path(_sourceName(name))), source)
        except (SyntaxError, ValueError):
            return False
    return data == _read(source)


def _importLegacy(files, markers):
    """Takes over the .org files of earlier versions (see above), and deletes the list of the replaced files that they kept."""
    _removeFile(os.path.join(STATE_DIR, "replaced.list"))
    for rel in pluginPYs():
        for name in (rel, rel + "c"):
            legacy = _path(name) + ".org"
            if not os.path.isfile(legacy):
                continue
            if name not in files and not os.path.isfile(_orig(name)) and os.path.isfile(_path(name)) and _isOurs(name, files, markers):
                _write(_orig(name), _read(legacy))
                files[name] = {"sha": _sha(_read(_path(name))), "source": None, "magic": None}
                logger.info("%s: original of an earlier version taken over", name)
            os.remove(legacy)


def _restoreFile(name, files, markers):
    """Puts the original back if the file is ours (a .py without an original is deleted, the image had only the .pyc), otherwise leaves it.
    The saved original is deleted either way. True if the file was changed."""
    path = _path(name)
    changed = False
    if os.path.isfile(path) and _isOurs(name, files, markers):
        if os.path.isfile(_orig(name)):
            _write(path, _read(_orig(name)))
            logger.info("%s: original restored", name)
            changed = True
        elif name.endswith(".py") and os.path.isfile(path + "c"):
            os.remove(path)
            logger.info("%s: removed, the image had only the .pyc", name)
            changed = True
        else:
            logger.error("%s: no original saved, left as it is", name)
    elif name in files:
        logger.info("%s: replaced by enigma2 in the meantime, left as it is", name)
    _removeFile(_orig(name))
    files.pop(name, None)
    return changed


def _syncFile(rel, files, markers):
    """The file of the plugin is in place, the original is saved. True if the file in enigma2 was changed."""
    source = os.path.join(PLUGIN_DIR, rel)
    try:
        code = _code(source, _path(rel))  # the error of a file is found before the original is touched
    except (SyntaxError, ValueError) as err:
        logger.error("%s has an error, not replaced: %s", rel, err)
        return False

    # the image with a .py gets our .py, the one with only a .pyc gets our .pyc (a .py of ours without a saved original is of an earlier version
    # of the plugin: the image has no .py)
    hasPy = os.path.isfile(_path(rel)) and (not _isOurs(rel, files, markers) or os.path.isfile(_orig(rel)))
    name, other = (rel, rel + "c") if hasPy else (rel + "c", rel)
    changed = _restoreFile(other, files, markers)  # the other kind of file is not needed (any more)

    # a file that is not ours is an original: the first install, or an update of enigma2 since the last sync
    path = _path(name)
    if not os.path.isfile(path):
        logger.info("%s is not in enigma2, not replaced", rel)
        files.pop(name, None)
        _removeFile(_orig(name))
        return changed
    if _isOurs(name, files, markers):
        files.setdefault(name, {"sha": _sha(_read(path)), "source": None, "magic": None})
    else:
        _write(_orig(name), _read(path))
        files.pop(name, None)
        logger.info("%s: original saved", name)

    sourceSha = _sha(_read(source))
    magic = MAGIC_NUMBER.hex()
    record = files.get(name)
    if record and record["source"] == sourceSha and (name == rel or record["magic"] == magic):
        return changed  # in place and up to date
    data = _read(source) if name == rel else _pyc(code, source)
    if not os.path.isfile(path) or _read(path) != data:
        _write(path, data)
        changed = True
        logger.info("%s: replaced", name)
    files[name] = {"sha": _sha(data), "source": sourceSha, "magic": magic}
    return changed


def sync(legacyMarkers=()):
    """The python files of the plugin are in place, the originals are saved. True if a file of enigma2 was changed (enigma2 has to restart to
    use it)."""
    markers = [marker.encode("utf-8") if isinstance(marker, str) else marker for marker in legacyMarkers]
    files = _loadState()
    changed = False
    try:
        _importLegacy(files, markers)
        rels = pluginPYs()
        for name in sorted(files):
            if _sourceName(name) not in rels:  # a file that the plugin doesn't have any more
                changed |= _restoreFile(name, files, markers)
        for rel in rels:
            try:
                changed |= _syncFile(rel, files, markers)
            except OSError as err:
                logger.error("%s not replaced: %s", rel, err)
        if files or os.path.isfile(STATE):
            _saveState(files)
    except OSError as err:
        logger.error("python files of enigma2: %s", err)
    return changed


def restore(legacyMarkers=()):
    """The original python files are back, as far as the files are still ours. True if a file of enigma2 was changed."""
    markers = [marker.encode("utf-8") if isinstance(marker, str) else marker for marker in legacyMarkers]
    files = _loadState()
    changed = False
    try:
        _importLegacy(files, markers)
        names = set(files)
        for rel in pluginPYs():
            names |= {rel, rel + "c"}
        for name in sorted(names):
            try:
                changed |= _restoreFile(name, files, markers)
            except OSError as err:
                logger.error("%s not restored: %s", name, err)
        shutil.rmtree(os.path.join(STATE_DIR, "orig"), ignore_errors=True)
        _removeFile(STATE)
        if os.path.isdir(STATE_DIR) and not os.listdir(STATE_DIR):
            os.rmdir(STATE_DIR)
    except OSError as err:
        logger.error("python files of enigma2: %s", err)
    return changed


def main(argv):
    logging.basicConfig(level=logging.INFO, format=PLUGIN + ": %(message)s")
    commands = {"sync": sync, "restore": restore}
    args = argv[1:]
    markers = []
    while len(args) >= 2 and args[-2] == "--legacy-marker":
        markers.append(args[-1])
        args = args[:-2]
    if len(args) != 1 or args[0] not in commands:
        print("usage: PyReplace.py sync|restore [--legacy-marker TEXT]...")
        return 1
    commands[args[0]](markers)
    return 0  # never fails: an install or a removal of the package must not be stopped


if __name__ == "__main__":
    sys.exit(main(sys.argv))
