"""Call-time PD One site values.

Nothing in this module reads the home directory, config, or environment at
import. One process can serve more than one profile, so every lookup happens
inside the function that needs the value.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

_PACKAGE = Path(__file__).resolve().parent
_TOOLS_DIR = _PACKAGE.parent

# Append, never insert at the front: bare sibling imports resolve, and a
# packaged name cannot shadow the standard library.
_PACKAGE_PATH = str(_PACKAGE)
if _PACKAGE_PATH not in sys.path:
    sys.path.append(_PACKAGE_PATH)


def _config_section() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config_readonly

        cfg = load_config_readonly()
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(cfg, dict):
        return {}
    section = cfg.get("pd_one")
    return section if isinstance(section, dict) else {}


def _lookup(section: dict[str, Any], *keys: str) -> str:
    current: Any = section
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return ""
        current = current[key]
    if current is None:
        return ""
    return str(current)


# Structured config keys. ``pd_one.values.PDONE_*`` and the process environment
# remain fallbacks so a rollout can set either place.
_STRUCTURED: dict[str, tuple[str, ...]] = {
    "PDONE_ADMIN_ALERT_CHANNEL_ID": ("channels", "admin_alert"),
    "PDONE_INTER_DEPT_CHANNEL_ID": ("channels", "inter_dept"),
    "PDONE_WORK_MANUAL_CHANNEL": ("channels", "work_manual"),
    "PDONE_OWNER_MM_USERNAME": ("owner_mm_username",),
    "PDONE_OWNER_MM_USER_ID": ("owner_mm_user_id",),
    "PDONE_OWNER_NAME_EN": ("owner_name_en",),
    "PDONE_OWNER_DISPLAY_NAME": ("owner_display_name",),
    "PDONE_PARENT_FOLDER_ID": ("drive", "parent_folder"),
    "PDONE_SHEET_ID": ("drive", "sheet"),
    "PDONE_SOURCE_DOC_ID": ("drive", "source_doc"),
    "PDONE_SOURCE_SPREADSHEET_ID": ("drive", "source_spreadsheet"),
    "PDONE_SCHEDULING_RULE_W12_NAME": ("scheduling_rule_w12_name",),
    "PDONE_PORTAL_PUBLIC_HOSTS": ("portal_public_hosts",),
    "PDONE_DOCX_REPAIR_TICKET_ID": ("docx_repair_ticket_id",),
}


def _structured_keys(name: str) -> tuple[str, ...]:
    mapped = _STRUCTURED.get(name)
    if mapped:
        return mapped
    if name.startswith("PDONE_EMAIL_"):
        return ("emails", name.removeprefix("PDONE_EMAIL_").lower())
    if name.startswith("PDONE_GDOC_"):
        return ("drive", name.removeprefix("PDONE_").lower())
    if name.startswith("PDONE_APPS_SCRIPT_"):
        return ("apps_script", name.removeprefix("PDONE_APPS_SCRIPT_").lower(), "script_id")
    return ()


def site_text(name: str) -> str:
    """Config value for ``name``, then the same-named environment variable."""
    section = _config_section()
    structured = _structured_keys(name)
    if structured:
        found = _lookup(section, *structured)
        if found:
            return found
    values = section.get("values")
    if isinstance(values, dict) and values.get(name):
        return str(values[name])
    return os.environ.get(name, "") or ""


def profile_tools_enabled() -> bool:
    """Profile ``tools/`` fallback. Off unless ``pd_one.load_profile_tools`` is true."""
    from utils import is_truthy_value

    return is_truthy_value(_config_section().get("load_profile_tools"), default=False)


def _install_root() -> Path:
    """Hermes install root for kanban and other shared state.

    A named profile lives in ``<root>/profiles/<name>``. Shared boards stay on
    the install root. The default profile's home is that root already.
    """
    from hermes_constants import get_hermes_home

    home = get_hermes_home()
    if home.parent.name == "profiles":
        return home.parent.parent
    return home


# The MCP server's HERMES_HOME is the install root. Profile registries live in
# profiles/<name> (pdone unless the runtime or config names another folder).
_DEFAULT_PROFILE_NAME = "pdone"
_PROFILE_HOME_ENVS = ("HERMES_PROFILE_HOME", "PD_ONE_PROFILE_HOME")
_PROFILE_NAME_ENVS = ("HERMES_PROFILE_NAME", "HERMES_PROFILE")


def _named_profile_dir(name: str) -> Path | None:
    """Directory for a profile id. ``default`` names the install root."""
    from hermes_constants import PROFILE_ID_RE
    from hermes_cli.profiles import get_profile_dir

    cleaned = name.strip().lower()
    if not cleaned or cleaned == "default" or PROFILE_ID_RE.match(cleaned) is None:
        return None
    directory = Path(get_profile_dir(cleaned))
    if directory.parent.name != "profiles":
        return None
    return directory


def _explicit_profile_home() -> Path | None:
    for key in _PROFILE_HOME_ENVS:
        raw = os.environ.get(key, "").strip()
        if raw:
            return Path(raw).expanduser()
    return None


def _env_profile_name() -> str:
    for key in _PROFILE_NAME_ENVS:
        raw = os.environ.get(key, "").strip()
        if raw:
            return raw
    return ""


def _active_profile_dir() -> Path | None:
    """Profile directory the runtime already selected, when it named one."""
    pinned = _env_profile_name()
    if pinned:
        found = _named_profile_dir(pinned)
        if found is not None:
            return found
    try:
        from hermes_cli.profiles import get_active_profile, get_active_profile_name
    except ImportError:
        return None
    derived = (get_active_profile_name() or "").strip()
    # ``custom`` is get_active_profile_name's sentinel for a home that is not
    # profiles/<name>. An explicit HERMES_PROFILE=custom still resolves above.
    if derived and derived != "custom":
        found = _named_profile_dir(derived)
        if found is not None:
            return found
    return _named_profile_dir(get_active_profile() or "")


def _is_profile_folder(path: Path) -> bool:
    return path.parent.name == "profiles"


def _configured_profile_name() -> str:
    from hermes_constants import PROFILE_ID_RE

    section = _config_section()
    for key in ("profile", "profile_name"):
        raw = section.get(key)
        if not isinstance(raw, str):
            continue
        name = raw.strip().lower()
        if name and name != "default" and PROFILE_ID_RE.match(name):
            return name
    return _DEFAULT_PROFILE_NAME


def profile_root() -> ProfileRoot:
    """PD One profile folder for this call.

    Capability registries and policies live under the profile folder. The MCP
    server often leaves ``HERMES_HOME`` on the install root. An explicit
    profile-home environment variable wins, then a profile the runtime already
    named, then ``<HERMES_HOME>/profiles/<name>`` (``pd_one.profile``, else
    ``pdone``). A home that is already a profile folder stays that folder.
    """
    explicit = _explicit_profile_home()
    if explicit is not None:
        return ProfileRoot(explicit)
    active = _active_profile_dir()
    if active is not None:
        return ProfileRoot(active)
    from hermes_constants import get_hermes_home

    home = get_hermes_home()
    if _is_profile_folder(home):
        return ProfileRoot(home)
    return ProfileRoot(home / "profiles" / _configured_profile_name())


def kanban_boards_root() -> Path:
    configured = _lookup(_config_section(), "external", "kanban_boards")
    if configured:
        return Path(configured).expanduser()
    return _install_root() / "kanban" / "boards"


def _relocate(relative: str) -> Path | None:
    """Packaged helpers that profile code addresses from the profile root."""
    text = relative.replace("\\", "/").lstrip("/")
    if text == "tools/pd_one_safe_ops.py":
        return _TOOLS_DIR / "pd_one_safe_ops.py"
    if text.startswith("tools/") and text.count("/") == 1:
        candidate = _PACKAGE / text.split("/", 1)[1]
        if candidate.is_file():
            return candidate
    if text == "skills/appsheet-copilot/scripts/appsheet_record_ops.py":
        packaged = _PACKAGE / "appsheet_record_ops.py"
        if packaged.is_file():
            return packaged
    return None


class ProfileRoot(Path):
    """Profile home. ``tools/<packaged file>`` resolves inside this package."""

    def __truediv__(self, key: object) -> Path:
        text = str(key).replace("\\", "/")
        base = profile_root()
        try:
            relative = Path(self).resolve().relative_to(Path(base).resolve())
            target = (Path(relative) / text).as_posix()
        except ValueError:
            target = text
        moved = _relocate(target)
        if moved is not None:
            return moved
        return ProfileRoot(Path(base) / target)


def repo_cli() -> Path:
    return _TOOLS_DIR / "pd_one_safe_ops.py"


def package_file(name: str) -> Path:
    return _PACKAGE / name


_EXTERNAL_FALLBACK_FILES = {
    "office_no_corruption_gate": (
        "skills",
        "pd-one",
        "pd-one-admin",
        "scripts",
        "office_no_corruption_gate.py",
    ),
}


def external_raw(key: str) -> str:
    """Configured path for an out-of-repo dependency. Empty when unset."""
    return _lookup(_config_section(), "external", key)


class ExternalPath:
    """A dependency that stays outside the repo.

    ``exists()`` is false when the path is unset, so status commands can report
    it missing. ``require()`` raises an error that names ``pd_one.external.<key>``.
    """

    def __init__(self, key: str) -> None:
        self.key = key

    def path(self) -> Path | None:
        raw = external_raw(self.key)
        if raw:
            return Path(raw).expanduser()
        parts = _EXTERNAL_FALLBACK_FILES.get(self.key)
        if parts:
            # Profile skills live next to the capability registries.
            return profile_root().joinpath(*parts)
        if self.key == "kanban_boards":
            return kanban_boards_root()
        return None

    def exists(self) -> bool:
        found = self.path()
        return bool(found and found.exists())

    def is_file(self) -> bool:
        found = self.path()
        return bool(found and found.is_file())

    def is_dir(self) -> bool:
        found = self.path()
        return bool(found and found.is_dir())

    def require(self) -> Path:
        found = self.path()
        if found is None or not found.exists():
            raise FileNotFoundError(
                f"PD One external dependency '{self.key}' is missing. "
                f"Set pd_one.external.{self.key} to its path."
            )
        return found

    def __fspath__(self) -> str:
        found = self.path()
        if found is None:
            return f"<unset pd_one.external.{self.key}>"
        return os.fspath(found)

    def __str__(self) -> str:
        return self.__fspath__()

    def __repr__(self) -> str:
        return f"ExternalPath({self.key!r}, {self.__fspath__()!r})"

    def __truediv__(self, key: object) -> Path:
        return self.require() / str(key)

    @property
    def parent(self) -> Path:
        return self.require().parent

    def __getattr__(self, name: str) -> Any:
        return getattr(self.require(), name)


def external_path(key: str) -> ExternalPath:
    return ExternalPath(key)


def load_external_module(key: str, module_name: str) -> Any:
    """Load a configured external module. Missing files name the config key."""
    path = external_path(key).require()
    if key == "sqlsrv_readonly":
        site = external_path("winrm_site_packages").path()
        if site and site.is_dir():
            site_text_path = str(site)
            if site_text_path not in sys.path:
                sys.path.append(site_text_path)
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.append(parent)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"PD One could not load pd_one.external.{key} from {path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ExternalModule:
    """Attribute access loads the configured module, or fails with its config key."""

    def __init__(self, key: str, module_name: str) -> None:
        self._key = key
        self._module_name = module_name
        self._module: Any = None

    def _load(self) -> Any:
        if self._module is None:
            self._module = load_external_module(self._key, self._module_name)
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)


def text_excludes_configured_hosts(text: str, key: str = "PDONE_PORTAL_PUBLIC_HOSTS") -> bool:
    """True when ``text`` contains none of the configured public portal hosts.

    An empty host list does not exclude anything: set ``portal_public_hosts``
    (comma-separated) or a public URL can be classified as the local probe.
    """
    hosts = [item.strip().lower() for item in site_text(key).split(",") if item.strip()]
    if not hosts:
        return True
    lowered = str(text or "").lower()
    return all(host not in lowered for host in hosts)


_PROFILE_MARK = "/profiles/pdone"
_HERMES_MARK = "~/.hermes/"


def resolve_configured_path(text: str) -> Path:
    """Turn a sanitized ``~/...`` path into the active profile or an external path."""
    raw = str(text or "")
    external_key = _EXTERNAL_PATHS.get(raw)
    if external_key:
        return external_path(external_key)
    if raw == "~":
        return Path.home()
    if raw.startswith("~/.hermes/profiles/pdone"):
        rest = raw.split(_PROFILE_MARK, 1)[1].lstrip("/")
        return profile_root() / rest if rest else profile_root()
    if raw.startswith(_HERMES_MARK):
        rest = raw[len(_HERMES_MARK):]
        if rest == "kanban/boards":
            return kanban_boards_root()
        return _install_root() / rest
    if raw.startswith("~/"):
        return Path.home() / raw[2:]
    if raw.startswith("~"):
        return Path(raw).expanduser()
    return Path(raw)


# Sanitized absolute paths that are not part of this repo. The value is the
# ``pd_one.external.<key>`` to consult instead of baking the path in.
_EXTERNAL_PATHS = {
    "~/.hermes/scripts/sqlsrv_readonly.py": "sqlsrv_readonly",
    "~/.hermes/venvs/winrm/bin/python": "winrm_python",
    "~/.hermes/venvs/winrm/lib/python3.12/site-packages": "winrm_site_packages",
    "~/.hermes/releases/pdone-current/.venv/bin/python": "docx_repair_python",
    "~/.hermes/runtime/current/.venv/bin/hermes": "hermes_bin",
    "~/.hermes/profiles/pdone/home/.local/bin/gog": "gog",
    "~/.local/bin/gog": "gog",
    "~/.local/bin/freecadcmd": "freecadcmd",
    "~/.local/bin/FreeCADCmd": "freecadcmd_alt",
    "~/.local/lib": "freecad_lib",
    "~/.config/gogcli/credentials-prodesign-admin.json": "gog_credentials",
    "~/.local/office-visual-qa/apt-debs": "office_deb_root",
    "~/.hermes/skills/pd-one/pd-one-admin/scripts/office_no_corruption_gate.py": "office_no_corruption_gate",
    "~/.hermes/profiles/pdone/skills/appsheet-copilot/references/prodesign-schema-map.json": "schema_map",
    "~/.openclaw/workspace/skills/appsheet-copilot/references/prodesign-schema-map.json": "schema_map",
    "~/.hermes/profiles/pdone/legacy-openclaw/workspace/tools/admin_approval_tickets.py": "admin_approval_tickets",
}


def owner_display_name() -> str:
    """Display label for the profile owner. Falls back to the protocol word Owner."""
    found = site_text("PDONE_OWNER_DISPLAY_NAME").strip()
    return found or "Owner"
