"""module for reading lang files."""
import os

LANGS_FNS = ('lang', 'langs', '.lang', '.langs')


def read_lang_files(lang_roots, path):
    """
    Read the lang files and parse languages.
    lang_roots is a dictionary to cache paths and languages to avoid
    reparsing the same language files.
    """
    if path not in lang_roots:
        lang_roots[path] = set()
        for fn in LANGS_FNS:
            langpath = os.path.join(path, fn)
            if os.path.exists(langpath):
                newlangs = set()
                with open(langpath, "r") as langfile:
                    for line in langfile:
                        linelangs = set(line.strip().split(","))
                        newlangs = newlangs.union(linelangs)
                lang_roots[path] = lang_roots[path].union(newlangs)

    return lang_roots[path]


def get_langs(root_path, path, lang_roots, cli_args):
    """Get the languages from this dir and parent dirs."""
    langs = set(cli_args.language)

    while True:
        new_langs = read_lang_files(lang_roots, path)
        langs = langs.union(new_langs)
        if path == root_path:
            break
        path = os.path.dirname(path)
    return langs
